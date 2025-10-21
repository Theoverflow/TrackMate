"""
Filesystem Backend
Writes messages to local or NFS filesystem
"""

import json
import aiofiles
from pathlib import Path
from typing import List
from datetime import datetime
import logging

from .base import BaseBackend, BackendResult
import sys
sys.path.insert(0, str(__file__ + '/../../../'))
from protocol.messages import Message

logger = logging.getLogger(__name__)


class FileSystemBackend(BaseBackend):
    """
    Writes messages to filesystem in JSONL format
    """
    
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        
        self.base_path = Path(config['base_path'])
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Rotation settings
        self.rotate_size_mb = config.get('rotate_size_mb', 100)
        self.rotate_daily = config.get('rotate_daily', True)
        
        logger.info(f"FileSystem backend '{name}' initialized: {self.base_path}")
    
    async def send(self, messages: List[Message]) -> BackendResult:
        """Write messages to file"""
        start_time = datetime.now()
        
        try:
            # Group messages by source
            by_source = {}
            for msg in messages:
                if msg.src not in by_source:
                    by_source[msg.src] = []
                by_source[msg.src].append(msg)
            
            # Write each source to its own file
            for source, source_messages in by_source.items():
                file_path = self._get_file_path(source)
                
                async with aiofiles.open(file_path, 'a') as f:
                    for msg in source_messages:
                        # Convert message to dict and write as JSONL
                        msg_dict = {
                            'v': msg.v,
                            'src': msg.src,
                            'ts': msg.ts,
                            'type': msg.type,
                            'data': msg.data
                        }
                        if msg.tid:
                            msg_dict['tid'] = msg.tid
                        if msg.sid:
                            msg_dict['sid'] = msg.sid
                        if msg.pid:
                            msg_dict['pid'] = msg.pid
                        
                        await f.write(json.dumps(msg_dict) + '\n')
            
            # Calculate latency
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            result = BackendResult(
                success=True,
                messages_sent=len(messages),
                latency_ms=latency_ms
            )
            
            self._update_stats(result)
            return result
            
        except Exception as e:
            logger.error(f"FileSystem backend error: {e}", exc_info=True)
            
            result = BackendResult(
                success=False,
                messages_sent=len(messages),
                error=str(e)
            )
            
            self._update_stats(result)
            return result
    
    def _get_file_path(self, source: str) -> Path:
        """Get file path for source"""
        if self.rotate_daily:
            # Daily rotation: source-2025-10-20.jsonl
            date_str = datetime.now().strftime('%Y-%m-%d')
            filename = f"{source}-{date_str}.jsonl"
        else:
            # No rotation: source.jsonl
            filename = f"{source}.jsonl"
        
        return self.base_path / filename
    
    async def close(self):
        """Close backend (nothing to close for filesystem)"""
        logger.info(f"FileSystem backend '{self.name}' closed")

