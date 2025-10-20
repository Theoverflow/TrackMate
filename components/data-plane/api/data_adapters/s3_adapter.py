"""
S3 adapter for reading monitoring events from object storage.
"""

import time
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import aiobotocore.session
import os

from .base import DataAdapter, AdapterResult

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class S3Adapter(DataAdapter):
    """
    Adapter for reading events from S3 (or compatible object storage).
    Events are stored as JSONL files with timestamps in the key.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.bucket_name = config.get("bucket_name", "")
        self.prefix = config.get("prefix", "monitoring_events")
        self.region_name = config.get("region_name", os.getenv("AWS_REGION", "us-east-1"))
        self.endpoint_url = config.get("endpoint_url", os.getenv("AWS_ENDPOINT_URL"))
        self.aws_access_key_id = config.get("aws_access_key_id", os.getenv("AWS_ACCESS_KEY_ID"))
        self.aws_secret_access_key = config.get("aws_secret_access_key", os.getenv("AWS_SECRET_ACCESS_KEY"))
        
        self.session = aiobotocore.session.get_session()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize S3 adapter."""
        if not self.bucket_name:
            raise ValueError("S3 adapter requires 'bucket_name' in configuration")
        
        self._initialized = True
        logger.info("S3 adapter initialized", adapter=self.name, bucket=self.bucket_name)
    
    async def close(self) -> None:
        """Close S3 adapter."""
        self._initialized = False
        logger.info("S3 adapter closed", adapter=self.name)
    
    async def query_events(
        self,
        filters: Optional[Dict[str, Any]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> AdapterResult:
        """Query events from S3 JSONL files."""
        if not self._initialized:
            return AdapterResult(
                success=False,
                data=[],
                source=self.name,
                count=0,
                error="Adapter not initialized"
            )
        
        start = time.time()
        
        try:
            # List objects in the time range
            async with self.session.create_client(
                "s3",
                region_name=self.region_name,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                endpoint_url=self.endpoint_url
            ) as client:
                # List objects with prefix
                paginator = client.get_paginator('list_objects_v2')
                
                all_events = []
                
                async for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.prefix):
                    if 'Contents' not in page:
                        continue
                    
                    # Sort objects by LastModified (most recent first)
                    objects = sorted(page['Contents'], key=lambda x: x['LastModified'], reverse=True)
                    
                    for obj in objects:
                        # Filter by time range if specified
                        if start_time and obj['LastModified'].replace(tzinfo=None) < start_time:
                            continue
                        if end_time and obj['LastModified'].replace(tzinfo=None) > end_time:
                            continue
                        
                        # Read and parse the JSONL file
                        response = await client.get_object(Bucket=self.bucket_name, Key=obj['Key'])
                        async with response['Body'] as stream:
                            content = await stream.read()
                        
                        # Parse JSONL
                        lines = content.decode('utf-8').strip().split('\n')
                        for line in lines:
                            if line:
                                try:
                                    event = json.loads(line)
                                    
                                    # Apply filters
                                    if filters:
                                        if 'site_id' in filters and event.get('site_id') != filters['site_id']:
                                            continue
                                        if 'app_name' in filters and event.get('app_name') != filters['app_name']:
                                            continue
                                        if 'entity_id' in filters and event.get('entity_id') != filters['entity_id']:
                                            continue
                                    
                                    # Apply time range filters
                                    event_time = datetime.fromtimestamp(event.get('timestamp', 0))
                                    if start_time and event_time < start_time:
                                        continue
                                    if end_time and event_time > end_time:
                                        continue
                                    
                                    all_events.append(event)
                                    
                                    # Stop if we have enough events
                                    if len(all_events) >= (limit + offset):
                                        break
                                        
                                except json.JSONDecodeError as e:
                                    logger.warning("Failed to parse event JSON", error=str(e), line=line[:100])
                                    continue
                        
                        if len(all_events) >= (limit + offset):
                            break
                    
                    if len(all_events) >= (limit + offset):
                        break
                
                # Sort by timestamp (most recent first)
                all_events.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
                
                # Apply offset and limit
                paginated_events = all_events[offset:offset + limit]
                
                query_time = (time.time() - start) * 1000
                
                logger.debug("S3 query completed",
                            adapter=self.name,
                            count=len(paginated_events),
                            total_found=len(all_events),
                            query_time_ms=query_time)
                
                return AdapterResult(
                    success=True,
                    data=paginated_events,
                    source=self.name,
                    count=len(paginated_events),
                    query_time_ms=query_time
                )
        
        except Exception as e:
            query_time = (time.time() - start) * 1000
            logger.error("S3 query failed", adapter=self.name, error=str(e))
            return AdapterResult(
                success=False,
                data=[],
                source=self.name,
                count=0,
                error=str(e),
                query_time_ms=query_time
            )
    
    async def health_check(self) -> bool:
        """Check if S3 bucket is accessible."""
        if not self._initialized:
            return False
        
        try:
            async with self.session.create_client(
                "s3",
                region_name=self.region_name,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                endpoint_url=self.endpoint_url
            ) as client:
                await client.head_bucket(Bucket=self.bucket_name)
            logger.debug("S3 health check passed", adapter=self.name)
            return True
        except Exception as e:
            logger.warning("S3 health check failed", adapter=self.name, error=str(e))
            return False

