#!/usr/bin/env python3
"""
Runtime Configuration Example

Demonstrates:
- Loading config from YAML file
- Automatic config reloading
- Adding backends without restart
- Fault-tolerant config updates
"""

import time
import signal
import sys
from pathlib import Path

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from monitoring_sdk.runtime_config import init_with_runtime_config

# Global flag for graceful shutdown
running = True

def signal_handler(sig, frame):
    global running
    print("\n\nShutting down gracefully...")
    running = False

def config_reload_callback(success: bool, message: str):
    """Callback for config reload events."""
    if success:
        print(f"✓ Config reloaded: {message}")
    else:
        print(f"✗ Config reload failed: {message}")

def main():
    global running
    
    print("=== Python SDK Runtime Configuration Example ===\n")
    
    # Setup signal handling
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    config_file = "monitoring_config.yaml"
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    
    print(f"Using config file: {config_file}\n")
    
    # Default configuration (fallback)
    default_config = {
        "mode": "sidecar",
        "app": {
            "name": "runtime-config-example",
            "version": "1.0.0",
            "site_id": "fab1"
        },
        "sidecar": {
            "url": "http://localhost:17000",
            "timeout": 5.0,
            "max_retries": 3
        }
    }
    
    # Initialize with runtime config
    manager = init_with_runtime_config(
        config_file_path=config_file,
        default_config=default_config,
        auto_reload=True,
        on_reload=config_reload_callback
    )
    
    print("✓ SDK initialized with runtime config")
    print(f"✓ Config file: {config_file}")
    print("✓ Auto-reload: enabled\n")
    
    print("Running application...")
    print(f"Try editing '{config_file}' while this runs!")
    print("Add/remove backends and see them activated without restart.")
    print("Press Ctrl+C to stop.\n")
    
    # Import SDK functions after initialization
    from monitoring_sdk import MonitoringSDK
    
    # Simulate long-running application
    event_count = 0
    
    while running:
        try:
            # Send periodic events
            event_count += 1
            entity_id = f"event-{event_count}"
            
            ctx = MonitoringSDK.start("periodic-job", entity_id)
            if ctx:
                ctx.progress(50, "processing")
                ctx.add_metric("event_number", event_count)
                ctx.finish()
                
                print(f"[{event_count}] Sent event to active backends")
            
            # Display reload status
            status = manager.get_reload_status()
            if status['last_reload_time'] > 0:
                elapsed = time.time() - status['last_reload_time']
                print(f"    Last reload: {elapsed:.0f}s ago "
                      f"({'success' if status['last_reload_success'] else 'failed'})")
            
            time.sleep(5)  # Wait between events
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)
    
    print("\n✓ Shutting down...")
    manager.shutdown()
    
    print(f"✓ Application stopped\n")
    print(f"Summary:")
    print(f"  - Events sent: {event_count}")
    print(f"  - Config file: {config_file}")
    print(f"  - Final status: {manager.get_reload_status()}\n")

if __name__ == "__main__":
    main()

