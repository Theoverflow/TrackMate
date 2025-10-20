"""S3 backend - uploads events to AWS S3 or compatible storage."""

import json
import io
from typing import Dict, Any, List
from datetime import datetime

from .base import Backend, BackendResult, BackendStatus

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
    logger.warning("boto3 not installed, S3Backend will not work")


class S3Backend(Backend):
    """
    S3 backend implementation.
    
    Uploads events to AWS S3 or S3-compatible storage (MinIO, etc.).
    Events are batched and uploaded as JSON files.
    
    Configuration:
        bucket: S3 bucket name (required)
        region: AWS region (default: us-east-1)
        prefix: Key prefix for objects (default: events/)
        access_key_id: AWS access key (optional, uses IAM role if not provided)
        secret_access_key: AWS secret key (optional)
        endpoint_url: Custom S3 endpoint for S3-compatible storage (optional)
        batch_size: Number of events per file (default: 100)
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        if not HAS_BOTO3:
            raise ImportError("boto3 is required for S3Backend. Install with: pip install boto3")
        
        self.bucket = config.get('bucket')
        if not self.bucket:
            raise ValueError("S3Backend requires 'bucket' in configuration")
        
        self.region = config.get('region', 'us-east-1')
        self.prefix = config.get('prefix', 'events/')
        self.access_key_id = config.get('access_key_id')
        self.secret_access_key = config.get('secret_access_key')
        self.endpoint_url = config.get('endpoint_url')
        self.batch_size = config.get('batch_size', 100)
        self._s3_client = None
        self._pending_events = []
    
    def initialize(self) -> None:
        """Initialize S3 client."""
        session_config = {}
        
        if self.access_key_id and self.secret_access_key:
            session_config['aws_access_key_id'] = self.access_key_id
            session_config['aws_secret_access_key'] = self.secret_access_key
        
        if self.endpoint_url:
            session_config['endpoint_url'] = self.endpoint_url
        
        self._s3_client = boto3.client('s3', region_name=self.region, **session_config)
        
        # Verify bucket exists
        try:
            self._s3_client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                raise ValueError(f"S3 bucket '{self.bucket}' does not exist")
            elif error_code == '403':
                raise ValueError(f"Access denied to S3 bucket '{self.bucket}'")
            else:
                raise
        
        self._initialized = True
        logger.info("s3_backend_initialized", bucket=self.bucket, region=self.region)
    
    def _upload_events(self, events: List[Dict[str, Any]]) -> BackendResult:
        """Upload events to S3."""
        try:
            # Generate S3 key
            now = datetime.now()
            key = f"{self.prefix}{now.strftime('%Y/%m/%d/%H%M%S')}-{len(events)}.json"
            
            # Create JSON content
            content = json.dumps({
                'events': events,
                'count': len(events),
                'timestamp': now.isoformat()
            }, indent=2)
            
            # Upload to S3
            self._s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content.encode('utf-8'),
                ContentType='application/json'
            )
            
            logger.debug("events_uploaded_to_s3", key=key, count=len(events))
            
            return BackendResult(
                status=BackendStatus.SUCCESS,
                message=f"Uploaded {len(events)} events to S3",
                events_sent=len(events)
            )
        
        except (ClientError, BotoCoreError) as e:
            logger.error(
                "s3_upload_failed",
                error=str(e),
                count=len(events)
            )
            return BackendResult(
                status=BackendStatus.FAILED,
                message=f"S3 error: {str(e)}",
                events_failed=len(events),
                error=e
            )
        
        except Exception as e:
            logger.error(
                "s3_upload_error",
                error=str(e),
                error_type=type(e).__name__
            )
            return BackendResult(
                status=BackendStatus.FAILED,
                message=f"Error: {str(e)}",
                events_failed=len(events),
                error=e
            )
    
    def send_event(self, event: Dict[str, Any]) -> BackendResult:
        """
        Queue event for S3 upload (batched).
        
        Args:
            event: Event dictionary
            
        Returns:
            BackendResult with operation status
        """
        if not self._initialized:
            self.initialize()
        
        self._pending_events.append(event)
        
        # Upload if batch is full
        if len(self._pending_events) >= self.batch_size:
            result = self._upload_events(self._pending_events)
            self._pending_events = []
            return result
        
        return BackendResult(
            status=BackendStatus.SUCCESS,
            message="Event queued for upload",
            events_sent=1
        )
    
    def send_batch(self, events: List[Dict[str, Any]]) -> BackendResult:
        """
        Upload a batch of events to S3.
        
        Args:
            events: List of event dictionaries
            
        Returns:
            BackendResult with operation status
        """
        if not self._initialized:
            self.initialize()
        
        # Upload pending events first
        if self._pending_events:
            self._upload_events(self._pending_events)
            self._pending_events = []
        
        # Upload batch
        return self._upload_events(events)
    
    def health_check(self) -> bool:
        """Check if S3 bucket is accessible."""
        if not self._initialized:
            return False
        
        try:
            self._s3_client.head_bucket(Bucket=self.bucket)
            return True
        except Exception:
            return False
    
    def close(self) -> None:
        """Flush pending events and close."""
        if self._pending_events:
            self._upload_events(self._pending_events)
            self._pending_events = []
        
        self._initialized = False
        logger.info("s3_backend_closed")

