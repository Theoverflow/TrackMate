#!/usr/bin/env python3
"""
Python SDK Example
Demonstrates monitoring instrumentation
"""

import time
import random
from monitoring_sdk import MonitoringSDK

def main():
    print("=== Python SDK Example ===\n")
    
    # Create SDK with context manager (auto-cleanup)
    with MonitoringSDK(source='python-service', debug=True) as sdk:
        
        # Log service start
        sdk.log_event('info', 'Python service starting')
        
        # Simulate processing items
        items = ['item-001', 'item-002', 'item-003', 'item-004', 'item-005']
        
        # Generate job ID for trace correlation
        job_id = f"job-{int(time.time())}"
        sdk.set_trace_id(job_id)
        
        # Start overall span
        main_span = sdk.start_span('process_batch', job_id)
        
        sdk.log_event('info', f'Processing {len(items)} items', {'job_id': job_id})
        
        for i, item in enumerate(items):
            # Per-item span
            item_span = sdk.start_span(f'process_item')
            
            sdk.log_event('info', f'Processing {item}', {'index': i})
            
            # Simulate work
            time.sleep(random.uniform(0.1, 0.3))
            
            # Log progress
            percent = int((i + 1) / len(items) * 100)
            sdk.log_progress(job_id, percent, 'processing')
            
            # Log item metric
            processing_time = random.uniform(50, 200)
            sdk.log_metric('item_processing_time_ms', processing_time, 'milliseconds',
                          {'item': item})
            
            # End item span
            sdk.end_span(item_span, 'success', {'item': item})
        
        # Log resource usage
        sdk.log_resource(
            cpu_percent=random.uniform(30, 60),
            memory_mb=random.uniform(512, 1024),
            disk_io_mb=random.uniform(10, 50),
            network_io_mb=random.uniform(5, 20)
        )
        
        # Complete
        sdk.log_progress(job_id, 100, 'completed')
        sdk.log_event('info', 'Batch processing completed', {'job_id': job_id})
        
        # End main span
        sdk.end_span(main_span, 'success')
        
        # Show statistics
        stats = sdk.get_stats()
        print(f"\n📊 SDK Statistics:")
        print(f"   State: {stats['state']}")
        print(f"   Messages sent: {stats['messages_sent']}")
        print(f"   Messages buffered: {stats['messages_buffered']}")
        print(f"   Messages dropped: {stats['messages_dropped']}")
        print(f"   Buffer size: {stats['buffer_size']}")
        print(f"   Reconnections: {stats['reconnect_count']}")
    
    print("\n✓ Python service finished\n")


if __name__ == '__main__':
    main()

