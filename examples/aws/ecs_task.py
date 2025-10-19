"""Example ECS task with wafer monitoring."""
import sys
import time
from monitoring_sdk import AppRef, Monitored
from monitoring_sdk.aws_helpers import create_aws_emitter, get_ecs_metadata
from uuid import uuid4


def process_data(data):
    """Simulate data processing."""
    time.sleep(0.1)
    return {'processed': True, 'data': data}


def main():
    """Main ECS task logic with monitoring."""
    # Create app reference
    app = AppRef(
        app_id=uuid4(),
        name="wafer-ecs-task",
        version="1.0.0"
    )
    
    # Create emitter with AWS metadata
    emitter = create_aws_emitter()
    
    # Get ECS metadata
    ecs_metadata = get_ecs_metadata()
    print(f"Running on ECS: {ecs_metadata}")
    print(f"Task ID: {ecs_metadata.get('task_id')}")
    print(f"Cluster: {ecs_metadata.get('cluster')}")
    
    # Monitor the task
    with Monitored(
        site_id='site1',
        app=app,
        entity_type='ecs-task',
        business_key=ecs_metadata.get('task_id', 'unknown'),
        emitter=emitter,
        metadata=ecs_metadata,
        enable_logging=True
    ) as mon:
        print("Starting ECS task processing...")
        
        # Example: Process messages from a queue or stream
        messages = range(100)
        
        for idx, message in enumerate(messages):
            # Process message
            result = process_data(message)
            
            # Report progress every 10 messages
            if (idx + 1) % 10 == 0:
                mon.progress(current=idx + 1, total=len(messages))
                print(f"Processed {idx + 1}/{len(messages)} messages")
        
        print("ECS task completed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())

