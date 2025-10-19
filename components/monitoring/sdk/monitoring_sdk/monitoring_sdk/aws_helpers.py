"""AWS-specific helpers for monitoring jobs on EC2, ECS, and Lambda."""
import os
import json
from typing import Optional, Dict, Any
from .models import AppRef
from .emitter import SidecarEmitter


def get_ec2_metadata() -> Dict[str, str]:
    """
    Get EC2 instance metadata.
    
    Returns:
        Dictionary with instance metadata
    """
    try:
        import requests
        
        # EC2 instance metadata endpoint
        metadata_url = "http://169.254.169.254/latest/meta-data/"
        
        instance_id = requests.get(f"{metadata_url}instance-id", timeout=1).text
        instance_type = requests.get(f"{metadata_url}instance-type", timeout=1).text
        availability_zone = requests.get(f"{metadata_url}placement/availability-zone", timeout=1).text
        
        return {
            'instance_id': instance_id,
            'instance_type': instance_type,
            'availability_zone': availability_zone,
            'compute_platform': 'ec2'
        }
    except Exception:
        return {
            'instance_id': os.getenv('EC2_INSTANCE_ID', 'unknown'),
            'instance_type': os.getenv('EC2_INSTANCE_TYPE', 'unknown'),
            'availability_zone': os.getenv('AWS_AVAILABILITY_ZONE', 'unknown'),
            'compute_platform': 'ec2'
        }


def get_ecs_metadata() -> Dict[str, str]:
    """
    Get ECS task metadata.
    
    Returns:
        Dictionary with ECS task metadata
    """
    try:
        import requests
        
        # ECS task metadata endpoint v4
        metadata_uri = os.getenv('ECS_CONTAINER_METADATA_URI_V4')
        if not metadata_uri:
            metadata_uri = os.getenv('ECS_CONTAINER_METADATA_URI')
        
        if metadata_uri:
            task_response = requests.get(f"{metadata_uri}/task", timeout=1)
            task_data = task_response.json()
            
            container_response = requests.get(metadata_uri, timeout=1)
            container_data = container_response.json()
            
            return {
                'task_arn': task_data.get('TaskARN', 'unknown'),
                'task_id': task_data.get('TaskARN', '').split('/')[-1],
                'cluster': task_data.get('Cluster', 'unknown'),
                'container_name': container_data.get('Name', 'unknown'),
                'container_id': container_data.get('DockerId', 'unknown'),
                'availability_zone': task_data.get('AvailabilityZone', 'unknown'),
                'compute_platform': 'ecs'
            }
    except Exception:
        pass
    
    return {
        'task_id': os.getenv('ECS_TASK_ID', 'unknown'),
        'cluster': os.getenv('ECS_CLUSTER', 'unknown'),
        'container_name': os.getenv('CONTAINER_NAME', 'unknown'),
        'compute_platform': 'ecs'
    }


def get_lambda_metadata() -> Dict[str, str]:
    """
    Get Lambda function metadata.
    
    Returns:
        Dictionary with Lambda metadata
    """
    return {
        'function_name': os.getenv('AWS_LAMBDA_FUNCTION_NAME', 'unknown'),
        'function_version': os.getenv('AWS_LAMBDA_FUNCTION_VERSION', 'unknown'),
        'function_memory_mb': os.getenv('AWS_LAMBDA_FUNCTION_MEMORY_SIZE', 'unknown'),
        'log_group': os.getenv('AWS_LAMBDA_LOG_GROUP_NAME', 'unknown'),
        'log_stream': os.getenv('AWS_LAMBDA_LOG_STREAM_NAME', 'unknown'),
        'request_id': os.getenv('AWS_REQUEST_ID', 'unknown'),
        'region': os.getenv('AWS_REGION', 'unknown'),
        'compute_platform': 'lambda'
    }


def detect_compute_platform() -> str:
    """
    Auto-detect the compute platform (EC2, ECS, or Lambda).
    
    Returns:
        Platform name: 'ec2', 'ecs', 'lambda', or 'unknown'
    """
    # Check for Lambda
    if os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
        return 'lambda'
    
    # Check for ECS
    if os.getenv('ECS_CONTAINER_METADATA_URI_V4') or os.getenv('ECS_CONTAINER_METADATA_URI'):
        return 'ecs'
    
    # Check for EC2 (try to reach metadata endpoint)
    try:
        import requests
        response = requests.get(
            "http://169.254.169.254/latest/meta-data/instance-id",
            timeout=1
        )
        if response.status_code == 200:
            return 'ec2'
    except Exception:
        pass
    
    return 'unknown'


def get_aws_metadata() -> Dict[str, str]:
    """
    Get metadata for current AWS compute platform.
    
    Returns:
        Dictionary with platform-specific metadata
    """
    platform = detect_compute_platform()
    
    if platform == 'ec2':
        return get_ec2_metadata()
    elif platform == 'ecs':
        return get_ecs_metadata()
    elif platform == 'lambda':
        return get_lambda_metadata()
    else:
        return {'compute_platform': 'unknown'}


def create_aws_emitter(
    sidecar_url: Optional[str] = None,
    auto_detect_platform: bool = True
) -> SidecarEmitter:
    """
    Create a SidecarEmitter with AWS metadata automatically included.
    
    Args:
        sidecar_url: Optional sidecar URL (uses SIDECAR_URL env var if not provided)
        auto_detect_platform: Whether to auto-detect and include AWS platform metadata
        
    Returns:
        Configured SidecarEmitter
    """
    emitter = SidecarEmitter(base_url=sidecar_url)
    
    # Add AWS metadata as attribute for easy access
    if auto_detect_platform:
        emitter.aws_metadata = get_aws_metadata()
    
    return emitter


def enrich_event_with_aws_metadata(event_dict: Dict[str, Any], metadata: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Enrich an event dictionary with AWS compute metadata.
    
    Args:
        event_dict: Event dictionary
        metadata: Optional metadata dict (will auto-detect if not provided)
        
    Returns:
        Enriched event dictionary
    """
    if metadata is None:
        metadata = get_aws_metadata()
    
    # Add AWS metadata to event metadata
    if 'event' in event_dict and 'metadata' in event_dict['event']:
        event_dict['event']['metadata'].update({
            'aws': metadata
        })
    
    return event_dict


# Lambda-specific decorator
def monitored_lambda_handler(site_id: str, app: AppRef):
    """
    Decorator for AWS Lambda handlers to automatically monitor execution.
    
    Usage:
        @monitored_lambda_handler('site1', app_ref)
        def lambda_handler(event, context):
            # Your lambda code
            return response
    """
    from functools import wraps
    from .context import Monitored
    
    def decorator(handler_func):
        @wraps(handler_func)
        def wrapper(event, context):
            # Get Lambda metadata
            metadata = get_lambda_metadata()
            metadata['lambda_request_id'] = context.request_id if hasattr(context, 'request_id') else 'unknown'
            
            # Monitor execution
            emitter = create_aws_emitter()
            
            with Monitored(
                site_id=site_id,
                app=app,
                entity_type='job',
                business_key=metadata.get('function_name'),
                emitter=emitter,
                metadata=metadata
            ):
                return handler_func(event, context)
        
        return wrapper
    return decorator


# Example usage helpers
def get_aws_enriched_app_ref(name: str, version: str) -> AppRef:
    """
    Create an AppRef with AWS platform information.
    
    Args:
        name: Application name
        version: Application version
        
    Returns:
        AppRef with AWS metadata in name
    """
    from uuid import uuid4
    
    platform = detect_compute_platform()
    enriched_name = f"{name}-{platform}"
    
    return AppRef(
        app_id=uuid4(),
        name=enriched_name,
        version=version
    )

