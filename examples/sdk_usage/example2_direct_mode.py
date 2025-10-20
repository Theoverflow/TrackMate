"""
Example 2: Using SDK in Direct Mode

This example shows how to use the SDK with direct backend routing,
bypassing the sidecar and writing directly to multiple backends.
"""

import sys
from pathlib import Path

# Add SDK to path
sdk_path = Path(__file__).parent.parent.parent / "components/monitoring/sdk/python"
sys.path.insert(0, str(sdk_path))

from monitoring_sdk import (
    configure,
    BackendRouter,
    get_config
)

def main():
    print("=" * 70)
    print("Example 2: SDK in Direct Mode")
    print("=" * 70)
    print()
    
    # Load configuration from YAML file
    config_file = Path(__file__).parent / "example2_direct_mode.yaml"
    
    print("1. Loading configuration from file...")
    print(f"   Config: {config_file}")
    configure(config_file)
    
    config = get_config()
    print(f"   Mode: {config.mode.value}")
    print(f"   Backends: {len(config.direct_backends)}")
    for backend in config.get_active_backends():
        print(f"     - {backend.type.value} (priority {backend.priority})")
    print()
    
    # Create router
    print("2. Initializing backend router...")
    with BackendRouter(config) as router:
        print("   Router initialized")
        print()
        
        # Send a single event
        print("3. Sending event directly to backends...")
        event = {
            "idempotency_key": "event-001",
            "site_id": config.app.site_id,
            "app": {
                "name": config.app.name,
                "version": config.app.version
            },
            "entity": {
                "type": "job",
                "id": "job-123"
            },
            "event": {
                "kind": "finished",
                "at": "2025-10-20T12:00:00Z",
                "metrics": {
                    "duration_ms": 1500,
                    "cpu_percent": 75.5
                },
                "status": "success",
                "metadata": {
                    "wafer_id": "W456",
                    "result": "passed"
                }
            }
        }
        
        results = router.send_event(event)
        
        print()
        print("   Results:")
        for backend_name, result in results.items():
            status = "✅" if result.success else "❌"
            print(f"   {status} {backend_name}: {result.message}")
            if result.error:
                print(f"      Error: {result.error}")
        print()
        
        # Check health
        print("4. Checking backend health...")
        health = router.health_check()
        for backend_name, is_healthy in health.items():
            status = "✅" if is_healthy else "❌"
            print(f"   {status} {backend_name}")
    
    print()
    print("=" * 70)
    print("✅ Example 2 Complete")
    print("=" * 70)
    print()
    print("Events were sent to:")
    print("  1. Local filesystem: /tmp/monitoring-events/")
    print("  2. S3 bucket: wafer-monitoring-events")
    print("  3. Elasticsearch: http://elasticsearch:9200/monitoring")


if __name__ == "__main__":
    main()

