"""
Main Sidecar Application
High-performance monitoring sidecar with TCP socket listener
"""

import asyncio
import signal
import logging
import sys
from pathlib import Path

from .config import SidecarConfig
from .tcp_listener import TCPListener
from .correlation_engine import CorrelationEngine
from .routing_engine import RoutingEngine

sys.path.insert(0, str(Path(__file__).parent.parent))
from protocol.messages import Message

logger = logging.getLogger(__name__)


class MonitoringSidecar:
    """
    Main sidecar application
    
    Components:
    - TCP Listener: Receives messages from SDKs
    - Correlation Engine: Buffers and correlates messages
    - Routing Engine: Routes messages to backends
    """
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = None
        self.listener = None
        self.correlation_engine = None
        self.routing_engine = None
        self.running = False
        
        logger.info(f"Initializing sidecar with config: {config_path}")
    
    async def start(self):
        """Start sidecar"""
        # Load configuration
        self.config = SidecarConfig.from_file(self.config_path)
        
        # Validate configuration
        errors = self.config.validate()
        if errors:
            for error in errors:
                logger.error(f"Config error: {error}")
            raise ValueError("Invalid configuration")
        
        logger.info("Configuration loaded and validated")
        
        # Initialize routing engine
        self.routing_engine = RoutingEngine(self.config)
        
        # Initialize correlation engine
        self.correlation_engine = CorrelationEngine(
            on_flush=self.routing_engine.route,
            flush_batch_size=self.config.buffers.flush_batch_size,
            flush_interval=self.config.buffers.flush_interval
        )
        await self.correlation_engine.start()
        
        # Initialize TCP listener
        self.listener = TCPListener(
            host=self.config.tcp.host,
            port=self.config.tcp.port,
            max_connections=self.config.tcp.max_connections,
            on_message=self._handle_message
        )
        
        self.running = True
        logger.info(f"✓ Sidecar started on {self.config.tcp.host}:{self.config.tcp.port}")
        
        # Start listening
        await self.listener.start()
    
    async def stop(self):
        """Stop sidecar gracefully"""
        logger.info("Stopping sidecar...")
        self.running = False
        
        # Stop listener
        if self.listener:
            await self.listener.stop()
        
        # Stop correlation engine (flushes buffers)
        if self.correlation_engine:
            await self.correlation_engine.stop()
        
        # Close routing engine (closes backends)
        if self.routing_engine:
            await self.routing_engine.close()
        
        logger.info("✓ Sidecar stopped")
    
    async def _handle_message(self, message: Message, handler):
        """Handle incoming message from TCP listener"""
        # Pass to correlation engine for buffering
        await self.correlation_engine.process_message(message)
    
    def get_stats(self) -> dict:
        """Get sidecar statistics"""
        stats = {
            'running': self.running,
            'config_file': self.config_path
        }
        
        if self.listener:
            stats['listener'] = self.listener.get_stats()
        
        if self.correlation_engine:
            stats['correlation'] = self.correlation_engine.get_stats()
        
        if self.routing_engine:
            stats['routing'] = self.routing_engine.get_stats()
        
        return stats


async def main():
    """Main entry point"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Get config path from args
    if len(sys.argv) < 2:
        print("Usage: python -m sidecar.main <config.yaml>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    
    # Create sidecar
    sidecar = MonitoringSidecar(config_path)
    
    # Setup signal handlers
    loop = asyncio.get_running_loop()
    
    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(sidecar.stop())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
    
    # Start sidecar
    try:
        await sidecar.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Failed to start sidecar: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete")

