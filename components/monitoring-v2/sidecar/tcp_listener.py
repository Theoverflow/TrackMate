"""
TCP Socket Listener
High-performance async TCP server for receiving monitoring messages
"""

import asyncio
import logging
from typing import Callable, Optional
from collections import defaultdict
from datetime import datetime

import sys
sys.path.insert(0, str(__file__ + '/../../'))

from protocol.messages import MessageParser, Message, MessageType

logger = logging.getLogger(__name__)


class ConnectionHandler:
    """
    Handles a single TCP connection from a client (SDK)
    """
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, 
                 on_message: Callable, connection_id: str):
        self.reader = reader
        self.writer = writer
        self.on_message = on_message
        self.connection_id = connection_id
        self.source = "unknown"
        self.messages_received = 0
        self.bytes_received = 0
        self.connected_at = datetime.now()
        self.last_message_at = None
        self.parser = MessageParser()
        
        # Get peer address
        try:
            peername = writer.get_extra_info('peername')
            self.peer_address = f"{peername[0]}:{peername[1]}" if peername else "unknown"
        except:
            self.peer_address = "unknown"
        
        logger.info(f"[{self.connection_id}] New connection from {self.peer_address}")
    
    async def handle(self):
        """Handle incoming messages from this connection"""
        try:
            while True:
                # Read line-delimited message
                line = await self.reader.readline()
                
                if not line:
                    # Connection closed
                    logger.info(f"[{self.connection_id}] Connection closed by client")
                    break
                
                # Update stats
                self.bytes_received += len(line)
                self.last_message_at = datetime.now()
                
                # Parse message
                try:
                    line_str = line.decode('utf-8')
                    message = self.parser.parse(line_str)
                    
                    if message:
                        # Validate message
                        if not self.parser.validate_message(message):
                            logger.warning(f"[{self.connection_id}] Invalid message: {line_str[:100]}")
                            continue
                        
                        # Update source from first message
                        if self.source == "unknown":
                            self.source = message.src
                            logger.info(f"[{self.connection_id}] Identified source: {self.source}")
                        
                        # Update stats
                        self.messages_received += 1
                        
                        # Handle goodbye message
                        if message.type == MessageType.GOODBYE:
                            logger.info(f"[{self.connection_id}] Received goodbye from {self.source}")
                            break
                        
                        # Pass to message handler
                        await self.on_message(message, self)
                    
                except ValueError as e:
                    logger.warning(f"[{self.connection_id}] Parse error: {e}")
                    continue
                except Exception as e:
                    logger.error(f"[{self.connection_id}] Message handling error: {e}", exc_info=True)
                    continue
        
        except asyncio.CancelledError:
            logger.info(f"[{self.connection_id}] Connection cancelled")
            raise
        
        except Exception as e:
            logger.error(f"[{self.connection_id}] Connection error: {e}", exc_info=True)
        
        finally:
            # Close connection
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except:
                pass
            
            logger.info(f"[{self.connection_id}] Connection closed. " +
                       f"Messages: {self.messages_received}, Bytes: {self.bytes_received}")
    
    def get_stats(self):
        """Get connection statistics"""
        uptime = (datetime.now() - self.connected_at).total_seconds()
        return {
            'connection_id': self.connection_id,
            'source': self.source,
            'peer_address': self.peer_address,
            'messages_received': self.messages_received,
            'bytes_received': self.bytes_received,
            'uptime_seconds': uptime,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None
        }


class TCPListener:
    """
    Async TCP listener for monitoring messages
    
    Accepts multiple concurrent connections and processes messages asynchronously.
    """
    
    def __init__(self, host: str = '127.0.0.1', port: int = 17000, 
                 max_connections: int = 100, on_message: Optional[Callable] = None):
        self.host = host
        self.port = port
        self.max_connections = max_connections
        self.on_message = on_message or self._default_message_handler
        
        self.server = None
        self.connections = {}  # connection_id -> ConnectionHandler
        self.connection_counter = 0
        self.running = False
        
        # Statistics
        self.total_connections = 0
        self.total_messages = 0
        self.messages_by_source = defaultdict(int)
        self.messages_by_type = defaultdict(int)
        
        logger.info(f"TCP Listener initialized: {host}:{port}")
    
    async def start(self):
        """Start listening for connections"""
        self.running = True
        
        self.server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port
        )
        
        addr = self.server.sockets[0].getsockname()
        logger.info(f"TCP Listener started on {addr[0]}:{addr[1]}")
        
        async with self.server:
            await self.server.serve_forever()
    
    async def stop(self):
        """Stop listener and close all connections"""
        logger.info("Stopping TCP Listener...")
        self.running = False
        
        # Close server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # Close all connections
        for conn_id, handler in list(self.connections.items()):
            try:
                handler.writer.close()
                await handler.writer.wait_closed()
            except:
                pass
        
        self.connections.clear()
        logger.info("TCP Listener stopped")
    
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle new client connection"""
        # Check connection limit
        if len(self.connections) >= self.max_connections:
            logger.warning(f"Connection limit reached ({self.max_connections}), rejecting connection")
            writer.close()
            await writer.wait_closed()
            return
        
        # Create connection handler
        self.connection_counter += 1
        connection_id = f"conn-{self.connection_counter}"
        self.total_connections += 1
        
        handler = ConnectionHandler(reader, writer, self._handle_message, connection_id)
        self.connections[connection_id] = handler
        
        try:
            await handler.handle()
        finally:
            # Remove from active connections
            if connection_id in self.connections:
                del self.connections[connection_id]
    
    async def _handle_message(self, message: Message, handler: ConnectionHandler):
        """Handle incoming message"""
        # Update statistics
        self.total_messages += 1
        self.messages_by_source[message.src] += 1
        self.messages_by_type[message.type] += 1
        
        # Call user-provided handler
        await self.on_message(message, handler)
    
    async def _default_message_handler(self, message: Message, handler: ConnectionHandler):
        """Default message handler (just log)"""
        logger.debug(f"[{handler.connection_id}] {message.src} {message.type}: {message.data}")
    
    def get_stats(self):
        """Get listener statistics"""
        active_connections = []
        for handler in self.connections.values():
            active_connections.append(handler.get_stats())
        
        return {
            'running': self.running,
            'address': f"{self.host}:{self.port}",
            'active_connections': len(self.connections),
            'total_connections': self.total_connections,
            'total_messages': self.total_messages,
            'messages_by_source': dict(self.messages_by_source),
            'messages_by_type': dict(self.messages_by_type),
            'connections': active_connections
        }


# Example usage
async def example_handler(message: Message, handler: ConnectionHandler):
    """Example message handler"""
    print(f"[{handler.source}] {message.type}: {message.data}")


async def main():
    """Example main function"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    listener = TCPListener(
        host='127.0.0.1',
        port=17000,
        on_message=example_handler
    )
    
    try:
        await listener.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await listener.stop()


if __name__ == '__main__':
    asyncio.run(main())

