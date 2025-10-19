"""AWS CloudWatch integration for monitoring compute jobs."""
import boto3
from typing import Dict, Any, List
from datetime import datetime
from .base import BaseIntegration, IntegrationConfig

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)  # type: ignore


class AWSCloudWatchIntegration(BaseIntegration):
    """
    Integration with AWS CloudWatch for monitoring EC2, ECS, and Lambda jobs.
    
    Features:
    - Send custom metrics to CloudWatch
    - Log job events to CloudWatch Logs
    - Support for EC2, ECS, and Lambda compute platforms
    - Automatic metric aggregation
    
    Configuration:
        - aws_region: AWS region (e.g., us-east-1)
        - log_group_name: CloudWatch Logs group name
        - namespace: CloudWatch metrics namespace (default: WaferMonitor)
        - aws_access_key_id: Optional AWS access key
        - aws_secret_access_key: Optional AWS secret key
        - compute_platform: ec2, ecs, or lambda
        - instance_id: EC2 instance ID or ECS task ID (optional)
    """
    
    def __init__(self, config: IntegrationConfig):
        """Initialize AWS CloudWatch integration."""
        super().__init__(config)
        self.aws_region = self.get_config('aws_region', 'us-east-1')
        self.log_group_name = self.get_config('log_group_name', '/wafer-monitor/jobs')
        self.namespace = self.get_config('namespace', 'WaferMonitor')
        self.compute_platform = self.get_config('compute_platform', 'ec2')
        self.instance_id = self.get_config('instance_id')
        
        # AWS credentials (optional, will use IAM role if not provided)
        self.aws_access_key = self.get_config('aws_access_key_id')
        self.aws_secret_key = self.get_config('aws_secret_access_key')
        
        self.cloudwatch_client = None
        self.logs_client = None
        self.log_stream_name = None
    
    async def initialize(self) -> None:
        """Initialize AWS clients."""
        # Create session with credentials if provided
        session_params = {'region_name': self.aws_region}
        if self.aws_access_key and self.aws_secret_key:
            session_params['aws_access_key_id'] = self.aws_access_key
            session_params['aws_secret_access_key'] = self.aws_secret_key
        
        session = boto3.Session(**session_params)
        
        # Create clients
        self.cloudwatch_client = session.client('cloudwatch')
        self.logs_client = session.client('logs')
        
        # Create log group if it doesn't exist
        try:
            self.logs_client.create_log_group(logGroupName=self.log_group_name)
            logger.info("cloudwatch_log_group_created", log_group=self.log_group_name)
        except self.logs_client.exceptions.ResourceAlreadyExistsException:
            pass
        except Exception as e:
            logger.warning("failed_to_create_log_group", error=str(e))
        
        # Create log stream
        self.log_stream_name = f"{self.compute_platform}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        try:
            self.logs_client.create_log_stream(
                logGroupName=self.log_group_name,
                logStreamName=self.log_stream_name
            )
        except Exception as e:
            logger.warning("failed_to_create_log_stream", error=str(e))
        
        self._initialized = True
        logger.info(
            "aws_cloudwatch_initialized",
            name=self.name,
            region=self.aws_region,
            namespace=self.namespace,
            platform=self.compute_platform
        )
    
    def _event_to_cloudwatch_metrics(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Convert monitoring event to CloudWatch metrics.
        
        Args:
            event: Monitoring event
            
        Returns:
            List of CloudWatch metric data
        """
        entity = event.get('entity', {})
        event_data = event.get('event', {})
        metrics_data = event_data.get('metrics', {})
        app = event.get('app', {})
        
        # Base dimensions
        dimensions = [
            {'Name': 'SiteId', 'Value': event.get('site_id', 'unknown')},
            {'Name': 'AppName', 'Value': app.get('name', 'unknown')},
            {'Name': 'EntityType', 'Value': entity.get('type', 'unknown')},
            {'Name': 'ComputePlatform', 'Value': self.compute_platform}
        ]
        
        # Add instance/task ID if available
        if self.instance_id:
            dimensions.append({'Name': 'InstanceId', 'Value': self.instance_id})
        
        # Create metrics
        cw_metrics = []
        
        # Job status metric
        if event_data.get('kind') == 'finished':
            status = event_data.get('status', 'unknown')
            cw_metrics.append({
                'MetricName': 'JobCompleted',
                'Dimensions': dimensions + [{'Name': 'Status', 'Value': status}],
                'Value': 1,
                'Unit': 'Count',
                'Timestamp': datetime.fromisoformat(event_data.get('at'))
            })
        
        # Duration metric
        if 'duration_s' in metrics_data:
            cw_metrics.append({
                'MetricName': 'JobDuration',
                'Dimensions': dimensions,
                'Value': metrics_data['duration_s'],
                'Unit': 'Seconds',
                'Timestamp': datetime.fromisoformat(event_data.get('at'))
            })
        
        # CPU metrics
        if 'cpu_user_s' in metrics_data:
            cw_metrics.append({
                'MetricName': 'CPUUserTime',
                'Dimensions': dimensions,
                'Value': metrics_data['cpu_user_s'],
                'Unit': 'Seconds',
                'Timestamp': datetime.fromisoformat(event_data.get('at'))
            })
        
        if 'cpu_system_s' in metrics_data:
            cw_metrics.append({
                'MetricName': 'CPUSystemTime',
                'Dimensions': dimensions,
                'Value': metrics_data['cpu_system_s'],
                'Unit': 'Seconds',
                'Timestamp': datetime.fromisoformat(event_data.get('at'))
            })
        
        # Memory metric
        if 'mem_max_mb' in metrics_data:
            cw_metrics.append({
                'MetricName': 'MemoryMaxMB',
                'Dimensions': dimensions,
                'Value': metrics_data['mem_max_mb'],
                'Unit': 'Megabytes',
                'Timestamp': datetime.fromisoformat(event_data.get('at'))
            })
        
        return cw_metrics
    
    def _event_to_log_message(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert monitoring event to CloudWatch log message.
        
        Args:
            event: Monitoring event
            
        Returns:
            CloudWatch log event
        """
        entity = event.get('entity', {})
        event_data = event.get('event', {})
        
        # Create structured log message
        log_message = {
            'timestamp': event_data.get('at'),
            'level': 'INFO' if event_data.get('status') in ['succeeded', 'running'] else 'ERROR',
            'site_id': event.get('site_id'),
            'app': event.get('app', {}).get('name'),
            'entity_type': entity.get('type'),
            'entity_id': entity.get('id'),
            'event_kind': event_data.get('kind'),
            'status': event_data.get('status'),
            'metrics': event_data.get('metrics', {}),
            'metadata': event_data.get('metadata', {}),
            'compute_platform': self.compute_platform,
            'instance_id': self.instance_id
        }
        
        import json
        return {
            'timestamp': int(datetime.fromisoformat(event_data.get('at')).timestamp() * 1000),
            'message': json.dumps(log_message)
        }
    
    async def send_event(self, event: Dict[str, Any]) -> bool:
        """Send event to CloudWatch metrics and logs."""
        try:
            # Send metrics
            metrics = self._event_to_cloudwatch_metrics(event)
            if metrics:
                self.cloudwatch_client.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=metrics
                )
                logger.debug(
                    "metrics_sent_to_cloudwatch",
                    count=len(metrics),
                    namespace=self.namespace
                )
            
            # Send log event
            log_event = self._event_to_log_message(event)
            try:
                self.logs_client.put_log_events(
                    logGroupName=self.log_group_name,
                    logStreamName=self.log_stream_name,
                    logEvents=[log_event]
                )
                logger.debug(
                    "log_sent_to_cloudwatch",
                    log_group=self.log_group_name,
                    log_stream=self.log_stream_name
                )
            except self.logs_client.exceptions.InvalidSequenceTokenException as e:
                # Retry with correct sequence token
                token = e.response['Error']['Message'].split('sequenceToken: ')[-1]
                self.logs_client.put_log_events(
                    logGroupName=self.log_group_name,
                    logStreamName=self.log_stream_name,
                    logEvents=[log_event],
                    sequenceToken=token
                )
            
            logger.info(
                "event_sent_to_cloudwatch",
                metrics_count=len(metrics),
                namespace=self.namespace
            )
            return True
        
        except Exception as e:
            logger.error(
                "cloudwatch_send_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            return False
    
    async def send_batch(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """Send batch of events to CloudWatch."""
        success = 0
        failed = 0
        
        # Collect all metrics
        all_metrics = []
        log_events = []
        
        for event in events:
            try:
                metrics = self._event_to_cloudwatch_metrics(event)
                all_metrics.extend(metrics)
                log_events.append(self._event_to_log_message(event))
            except Exception as e:
                logger.warning("event_conversion_failed", error=str(e))
                failed += 1
        
        # Send metrics in batches (CloudWatch limit: 20 metrics per request)
        try:
            for i in range(0, len(all_metrics), 20):
                batch = all_metrics[i:i+20]
                self.cloudwatch_client.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=batch
                )
            
            logger.info(
                "metrics_batch_sent_to_cloudwatch",
                total_metrics=len(all_metrics),
                namespace=self.namespace
            )
        except Exception as e:
            logger.error("cloudwatch_metrics_batch_failed", error=str(e))
            failed += len(events)
            return {'success': 0, 'failed': failed}
        
        # Send log events (CloudWatch limit: 10,000 events per request)
        try:
            for i in range(0, len(log_events), 10000):
                batch = log_events[i:i+10000]
                # Sort by timestamp
                batch.sort(key=lambda x: x['timestamp'])
                
                self.logs_client.put_log_events(
                    logGroupName=self.log_group_name,
                    logStreamName=self.log_stream_name,
                    logEvents=batch
                )
            
            success = len(events) - failed
            logger.info(
                "logs_batch_sent_to_cloudwatch",
                total_events=success,
                log_group=self.log_group_name
            )
        except Exception as e:
            logger.error("cloudwatch_logs_batch_failed", error=str(e))
            failed = len(events)
            success = 0
        
        return {'success': success, 'failed': failed}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check CloudWatch connectivity."""
        try:
            # Try to describe log streams
            response = self.logs_client.describe_log_streams(
                logGroupName=self.log_group_name,
                limit=1
            )
            
            # Try to list metrics
            metrics_response = self.cloudwatch_client.list_metrics(
                Namespace=self.namespace,
                MaxRecords=1
            )
            
            return {
                'status': 'healthy',
                'integration': self.name,
                'backend': 'aws_cloudwatch',
                'region': self.aws_region,
                'namespace': self.namespace,
                'log_group': self.log_group_name,
                'compute_platform': self.compute_platform,
                'metrics_available': len(metrics_response.get('Metrics', []))
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'integration': self.name,
                'backend': 'aws_cloudwatch',
                'error': str(e)
            }
    
    async def close(self) -> None:
        """Close AWS clients (boto3 handles connection pooling)."""
        logger.info("aws_cloudwatch_closed", name=self.name)

