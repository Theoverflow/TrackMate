"""FileSystem backend - writes events to local or network filesystem."""

import json
import os
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from threading import Lock

from .base import Backend, BackendResult, BackendStatus

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class FileSystemBackend(Backend):
    """
    FileSystem backend implementation.
    
    Writes events to files in JSON Lines format (one JSON object per line).
    Supports local filesystem and network filesystems (NFS, SMB, etc.).
    
    Configuration:
        path: Directory path for event files (default: /data/monitoring)
        format: File format - jsonl or json (default: jsonl)
        rotate_size_mb: Rotate file when it reaches this size in MB (default: 100)
        filename_pattern: File naming pattern (default: events-{date}-{time}.jsonl)
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.path = Path(config.get('path', '/data/monitoring'))
        self.format = config.get('format', 'jsonl')
        self.rotate_size_mb = config.get('rotate_size_mb', 100)
        self.filename_pattern = config.get('filename_pattern', 'events-{date}-{time}.jsonl')
        self._current_file = None
        self._file_lock = Lock()
        self._current_size = 0
    
    def initialize(self) -> None:
        """Initialize filesystem backend."""
        # Create directory if it doesn't exist
        self.path.mkdir(parents=True, exist_ok=True)
        
        # Create initial file
        self._rotate_file()
        
        self._initialized = True
        logger.info("filesystem_backend_initialized", path=str(self.path))
    
    def _rotate_file(self) -> None:
        """Rotate to a new file."""
        if self._current_file and not self._current_file.closed:
            self._current_file.close()
        
        # Generate filename
        now = datetime.now()
        filename = self.filename_pattern.format(
            date=now.strftime('%Y%m%d'),
            time=now.strftime('%H%M%S'),
            timestamp=now.timestamp()
        )
        
        filepath = self.path / filename
        self._current_file = open(filepath, 'a')
        self._current_size = filepath.stat().st_size if filepath.exists() else 0
        
        logger.debug("file_rotated", filepath=str(filepath))
    
    def _check_rotation(self) -> None:
        """Check if file needs rotation."""
        max_size = self.rotate_size_mb * 1024 * 1024
        if self._current_size >= max_size:
            self._rotate_file()
    
    def send_event(self, event: Dict[str, Any]) -> BackendResult:
        """
        Write a single event to filesystem.
        
        Args:
            event: Event dictionary
            
        Returns:
            BackendResult with operation status
        """
        if not self._initialized:
            self.initialize()
        
        try:
            with self._file_lock:
                self._check_rotation()
                
                if self.format == 'jsonl':
                    # JSON Lines format (one object per line)
                    line = json.dumps(event) + '\n'
                    self._current_file.write(line)
                    self._current_size += len(line.encode('utf-8'))
                else:
                    # Pretty JSON format
                    json.dump(event, self._current_file, indent=2)
                    self._current_file.write('\n')
                
                self._current_file.flush()
            
            logger.debug("event_written_to_file", event_id=event.get('idempotency_key'))
            
            return BackendResult(
                status=BackendStatus.SUCCESS,
                message="Event written to filesystem",
                events_sent=1
            )
        
        except Exception as e:
            logger.error(
                "filesystem_write_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            return BackendResult(
                status=BackendStatus.FAILED,
                message=f"Error: {str(e)}",
                events_failed=1,
                error=e
            )
    
    def send_batch(self, events: List[Dict[str, Any]]) -> BackendResult:
        """
        Write a batch of events to filesystem.
        
        Args:
            events: List of event dictionaries
            
        Returns:
            BackendResult with operation status
        """
        if not self._initialized:
            self.initialize()
        
        try:
            with self._file_lock:
                self._check_rotation()
                
                for event in events:
                    if self.format == 'jsonl':
                        line = json.dumps(event) + '\n'
                        self._current_file.write(line)
                        self._current_size += len(line.encode('utf-8'))
                    else:
                        json.dump(event, self._current_file, indent=2)
                        self._current_file.write('\n')
                    
                    self._check_rotation()
                
                self._current_file.flush()
            
            logger.debug("batch_written_to_file", count=len(events))
            
            return BackendResult(
                status=BackendStatus.SUCCESS,
                message=f"Batch of {len(events)} events written to filesystem",
                events_sent=len(events)
            )
        
        except Exception as e:
            logger.error(
                "filesystem_batch_write_failed",
                error=str(e),
                count=len(events)
            )
            return BackendResult(
                status=BackendStatus.FAILED,
                message=f"Error: {str(e)}",
                events_failed=len(events),
                error=e
            )
    
    def health_check(self) -> bool:
        """Check if filesystem is accessible."""
        try:
            # Try to write a test file
            test_file = self.path / '.health_check'
            test_file.write_text('ok')
            test_file.unlink()
            return True
        except Exception:
            return False
    
    def close(self) -> None:
        """Close current file."""
        if self._current_file and not self._current_file.closed:
            self._current_file.close()
            self._initialized = False
            logger.info("filesystem_backend_closed")

