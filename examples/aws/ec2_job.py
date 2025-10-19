"""Example job running on EC2 with wafer monitoring."""
import sys
from monitoring_sdk import AppRef, Monitored
from monitoring_sdk.aws_helpers import create_aws_emitter, get_ec2_metadata
from uuid import uuid4


def main():
    """Main job logic with monitoring."""
    # Create app reference
    app = AppRef(
        app_id=uuid4(),
        name="wafer-ec2-processor",
        version="1.0.0"
    )
    
    # Create emitter with AWS metadata
    emitter = create_aws_emitter()
    
    # Get EC2 metadata
    ec2_metadata = get_ec2_metadata()
    print(f"Running on EC2: {ec2_metadata}")
    
    # Monitor the job
    with Monitored(
        site_id='site1',
        app=app,
        entity_type='batch-job',
        business_key='daily-processing',
        emitter=emitter,
        metadata=ec2_metadata,
        enable_logging=True
    ) as mon:
        print("Starting batch processing...")
        
        # Simulate batch processing
        total_items = 1000
        batch_size = 100
        
        for i in range(0, total_items, batch_size):
            # Process batch
            batch_end = min(i + batch_size, total_items)
            print(f"Processing items {i} to {batch_end}")
            
            # Your processing logic here
            # ...
            
            # Report progress
            mon.progress(current=batch_end, total=total_items)
        
        print("Batch processing completed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())

