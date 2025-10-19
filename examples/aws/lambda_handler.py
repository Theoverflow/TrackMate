"""Example AWS Lambda handler with wafer monitoring."""
import sys
import os

# Add SDK to path (if deployed as Lambda layer)
sys.path.insert(0, '/opt/python/lib/python3.11/site-packages')

from monitoring_sdk import AppRef
from monitoring_sdk.aws_helpers import monitored_lambda_handler, get_aws_metadata
from uuid import uuid4


# Define app reference
app_ref = AppRef(
    app_id=uuid4(),
    name="wafer-lambda-processor",
    version="1.0.0"
)


@monitored_lambda_handler('site1', app_ref)
def lambda_handler(event, context):
    """
    Lambda handler with automatic monitoring.
    
    The decorator will:
    - Auto-detect Lambda environment
    - Create monitoring events (start, finish)
    - Send to configured integrations (CloudWatch, X-Ray)
    - Track execution time and resource usage
    - Report errors automatically
    """
    # Your Lambda logic here
    print(f"Processing event: {event}")
    
    # Example processing
    records = event.get('Records', [])
    processed = []
    
    for record in records:
        # Process each record
        result = {
            'record_id': record.get('messageId'),
            'status': 'processed'
        }
        processed.append(result)
    
    return {
        'statusCode': 200,
        'body': {
            'processed': len(processed),
            'results': processed
        }
    }


# Alternative: Manual monitoring for more control
def manual_lambda_handler(event, context):
    """Lambda handler with manual monitoring control."""
    from monitoring_sdk import Monitored
    from monitoring_sdk.aws_helpers import create_aws_emitter
    
    emitter = create_aws_emitter()
    metadata = get_aws_metadata()
    
    with Monitored(
        site_id='site1',
        app=app_ref,
        entity_type='lambda-job',
        business_key=f"request-{context.request_id}",
        emitter=emitter,
        metadata=metadata
    ) as mon:
        # Your Lambda logic
        records = event.get('Records', [])
        
        # Report progress
        for i, record in enumerate(records):
            mon.progress(current=i+1, total=len(records))
            # Process record
            pass
        
        return {
            'statusCode': 200,
            'body': {'processed': len(records)}
        }

