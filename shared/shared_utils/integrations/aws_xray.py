"""AWS X-Ray integration for distributed tracing."""
import boto3
import time
from typing import Dict, Any, List
from datetime import datetime
from .base import BaseIntegration, IntegrationConfig

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)  # type: ignore


class AWSXRayIntegration(BaseIntegration):
    """
    Integration with AWS X-Ray for distributed tracing.
    
    Sends job execution traces to X-Ray for visualization and analysis.
    
    Configuration:
        - aws_region: AWS region
        - service_name: Service name for traces
        - aws_access_key_id: Optional AWS access key
        - aws_secret_access_key: Optional AWS secret key
    """
    
    def __init__(self, config: IntegrationConfig):
        """Initialize AWS X-Ray integration."""
        super().__init__(config)
        self.aws_region = self.get_config('aws_region', 'us-east-1')
        self.service_name = self.get_config('service_name', 'wafer-monitor')
        self.aws_access_key = self.get_config('aws_access_key_id')
        self.aws_secret_key = self.get_config('aws_secret_access_key')
        
        self.xray_client = None
        self.pending_segments = {}
    
    async def initialize(self) -> None:
        """Initialize X-Ray client."""
        session_params = {'region_name': self.aws_region}
        if self.aws_access_key and self.aws_secret_key:
            session_params['aws_access_key_id'] = self.aws_access_key
            session_params['aws_secret_access_key'] = self.aws_secret_key
        
        session = boto3.Session(**session_params)
        self.xray_client = session.client('xray')
        
        self._initialized = True
        logger.info(
            "aws_xray_initialized",
            name=self.name,
            region=self.aws_region,
            service=self.service_name
        )
    
    def _create_trace_id(self) -> str:
        """Generate X-Ray trace ID."""
        import random
        hex_time = hex(int(time.time()))[2:]
        hex_random = format(random.getrandbits(96), 'x')
        return f"1-{hex_time}-{hex_random}"
    
    def _create_segment_id(self) -> str:
        """Generate X-Ray segment ID."""
        import random
        return format(random.getrandbits(64), 'x')
    
    def _event_to_xray_segment(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert monitoring event to X-Ray segment.
        
        Args:
            event: Monitoring event
            
        Returns:
            X-Ray segment document
        """
        entity = event.get('entity', {})
        event_data = event.get('event', {})
        metrics_data = event_data.get('metrics', {})
        app = event.get('app', {})
        entity_id = entity.get('id')
        
        # Check if this is start or end of trace
        if event_data.get('kind') == 'started':
            # Start new segment
            trace_id = self._create_trace_id()
            segment_id = self._create_segment_id()
            
            segment = {
                'id': segment_id,
                'trace_id': trace_id,
                'name': f"{app.get('name', 'unknown')}.{entity.get('type', 'job')}",
                'start_time': datetime.fromisoformat(event_data.get('at')).timestamp(),
                'in_progress': True,
                'service': {
                    'name': self.service_name
                },
                'metadata': {
                    'wafer_monitor': {
                        'site_id': event.get('site_id'),
                        'app_name': app.get('name'),
                        'app_version': app.get('version'),
                        'entity_type': entity.get('type'),
                        'entity_id': entity_id,
                        'business_key': entity.get('business_key')
                    }
                }
            }
            
            # Store pending segment
            self.pending_segments[entity_id] = segment
            return None  # Don't send yet
        
        elif event_data.get('kind') == 'finished':
            # Complete segment
            if entity_id in self.pending_segments:
                segment = self.pending_segments.pop(entity_id)
                segment['end_time'] = datetime.fromisoformat(event_data.get('at')).timestamp()
                segment['in_progress'] = False
                
                # Add status
                status = event_data.get('status')
                if status == 'failed':
                    segment['error'] = True
                    segment['fault'] = True
                    segment['cause'] = {
                        'exceptions': [{
                            'message': event_data.get('metadata', {}).get('error', 'Unknown error'),
                            'type': event_data.get('metadata', {}).get('error_type', 'Error')
                        }]
                    }
                
                # Add annotations (indexed by X-Ray)
                segment['annotations'] = {
                    'site_id': event.get('site_id'),
                    'app_name': app.get('name'),
                    'status': status,
                    'entity_type': entity.get('type')
                }
                
                # Add metadata (not indexed)
                segment['metadata']['wafer_monitor'].update({
                    'duration_s': metrics_data.get('duration_s'),
                    'cpu_user_s': metrics_data.get('cpu_user_s'),
                    'cpu_system_s': metrics_data.get('cpu_system_s'),
                    'mem_max_mb': metrics_data.get('mem_max_mb'),
                    'status': status
                })
                
                return segment
        
        return None
    
    async def send_event(self, event: Dict[str, Any]) -> bool:
        """Send event to X-Ray."""
        try:
            segment = self._event_to_xray_segment(event)
            
            if segment:
                import json
                segment_document = json.dumps(segment)
                
                self.xray_client.put_trace_segments(
                    TraceSegmentDocuments=[segment_document]
                )
                
                logger.debug(
                    "trace_sent_to_xray",
                    trace_id=segment['trace_id'],
                    segment_id=segment['id']
                )
            
            return True
        
        except Exception as e:
            logger.error(
                "xray_send_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            return False
    
    async def send_batch(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """Send batch of events to X-Ray."""
        segments = []
        
        for event in events:
            try:
                segment = self._event_to_xray_segment(event)
                if segment:
                    segments.append(segment)
            except Exception as e:
                logger.warning("segment_conversion_failed", error=str(e))
        
        if not segments:
            return {'success': len(events), 'failed': 0}
        
        try:
            import json
            segment_documents = [json.dumps(seg) for seg in segments]
            
            # X-Ray accepts up to 50 segments per request
            for i in range(0, len(segment_documents), 50):
                batch = segment_documents[i:i+50]
                self.xray_client.put_trace_segments(
                    TraceSegmentDocuments=batch
                )
            
            logger.info(
                "traces_batch_sent_to_xray",
                count=len(segments)
            )
            return {'success': len(events), 'failed': 0}
        
        except Exception as e:
            logger.error("xray_batch_failed", error=str(e))
            return {'success': 0, 'failed': len(events)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check X-Ray connectivity."""
        try:
            # Try to get service graph (requires permissions)
            response = self.xray_client.get_service_graph(
                StartTime=datetime.utcnow().timestamp() - 3600,
                EndTime=datetime.utcnow().timestamp()
            )
            
            return {
                'status': 'healthy',
                'integration': self.name,
                'backend': 'aws_xray',
                'region': self.aws_region,
                'service': self.service_name,
                'services_in_graph': len(response.get('Services', []))
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'integration': self.name,
                'backend': 'aws_xray',
                'error': str(e)
            }
    
    async def close(self) -> None:
        """Close X-Ray client."""
        # Send any pending segments as incomplete
        if self.pending_segments:
            logger.warning(
                "closing_with_pending_segments",
                count=len(self.pending_segments)
            )
        
        logger.info("aws_xray_closed", name=self.name)

