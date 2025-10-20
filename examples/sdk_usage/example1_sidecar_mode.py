"""
Example 1: Using SDK in Sidecar Mode

This example shows how to use the enhanced monitoring SDK
with sidecar routing (traditional flow).
"""

import sys
from pathlib import Path

# Add SDK to path
sdk_path = Path(__file__).parent.parent.parent / "components/monitoring/sdk/python"
sys.path.insert(0, str(sdk_path))

from monitoring_sdk import (
    configure,
    SDKMode,
    Monitored,
    BackendRouter,
    get_config
)

def main():
    print("=" * 70)
    print("Example 1: SDK in Sidecar Mode")
    print("=" * 70)
    print()
    
    # Configure SDK for sidecar mode
    print("1. Configuring SDK...")
    configure(
        mode=SDKMode.SIDECAR,
        sidecar_url="http://localhost:17000",
        app_name="example-wafer-processor",
        app_version="1.0.0",
        site_id="fab1"
    )
    
    config = get_config()
    print(f"   Mode: {config.mode.value}")
    print(f"   Sidecar URL: {config.sidecar.url}")
    print(f"   App: {config.app.name} v{config.app.version}")
    print()
    
    # Use monitored context (traditional way)
    print("2. Processing wafer with monitoring...")
    
    try:
        with Monitored(
            "process-wafer-123",
            metadata={
                "wafer_id": "W123",
                "lot": "LOT-001",
                "step": "lithography"
            }
        ) as ctx:
            print("   - Started processing")
            
            # Simulate work
            import time
            time.sleep(0.5)
            
            # Report progress
            ctx.report_progress(
                {"progress": 50, "stage": "exposure"}
            )
            print("   - Progress: 50%")
            
            time.sleep(0.5)
            
            print("   - Completed processing")
    
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    print("3. Events sent to sidecar at http://localhost:17000")
    print("   Sidecar will route to configured backends")
    print()
    print("=" * 70)
    print("✅ Example 1 Complete")
    print("=" * 70)


if __name__ == "__main__":
    main()

