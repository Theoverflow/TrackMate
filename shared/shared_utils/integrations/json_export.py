"""JSON export integration for local file storage."""
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from .base import BaseIntegration, IntegrationConfig

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)  # type: ignore


class JSONExportIntegration(BaseIntegration):
    """
    JSON export integration for local file storage.
    
    Writes events to JSON files (one event per line - JSONL format).
    
    Configuration:
        - output_dir: Directory for JSON files (default: /var/log/wafer-monitor)
        - rotation: Rotation strategy (daily, hourly, none)
        - pretty_print: Pretty print JSON (default: False)
        - compression: Enable gzip compression (default: False)
    """
    
    def __init__(self, config: IntegrationConfig):
        """Initialize JSON export integration."""
        super().__init__(config)
        self.output_dir = Path(self.get_config('output_dir', '/var/log/wafer-monitor'))
        self.rotation = self.get_config('rotation', 'daily')
        self.pretty_print = self.get_config('pretty_print', False)
        self.compression = self.get_config('compression', False)
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """Create output directory if it doesn't exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._initialized = True
        logger.info(
            "json_export_initialized",
            name=self.name,
            output_dir=str(self.output_dir),
            rotation=self.rotation
        )
    
    def _get_json_filename(self) -> Path:
        """Get current JSON filename based on rotation strategy."""
        now = datetime.utcnow()
        
        if self.rotation == 'hourly':
            suffix = now.strftime('%Y%m%d_%H')
        elif self.rotation == 'daily':
            suffix = now.strftime('%Y%m%d')
        else:
            suffix = 'events'
        
        ext = '.jsonl.gz' if self.compression else '.jsonl'
        return self.output_dir / f'wafer_events_{suffix}{ext}'
    
    async def send_event(self, event: Dict[str, Any]) -> bool:
        """Append event to JSON file."""
        try:
            async with self._lock:
                filename = self._get_json_filename()
                
                # Use thread executor for file I/O
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._write_json_sync,
                    filename,
                    event
                )
                
                logger.debug("event_written_to_json", filename=filename.name)
                return True
        except Exception as e:
            logger.error("json_write_failed", error=str(e))
            return False
    
    def _write_json_sync(self, filename: Path, event: Dict[str, Any]) -> None:
        """Synchronous JSON write."""
        if self.compression:
            import gzip
            with gzip.open(filename, 'at', encoding='utf-8') as f:
                json.dump(event, f, indent=2 if self.pretty_print else None)
                f.write('\n')
        else:
            with open(filename, 'a', encoding='utf-8') as f:
                json.dump(event, f, indent=2 if self.pretty_print else None)
                f.write('\n')
    
    async def send_batch(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """Append batch of events to JSON file."""
        try:
            async with self._lock:
                filename = self._get_json_filename()
                
                # Use thread executor for file I/O
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._write_json_batch_sync,
                    filename,
                    events
                )
                
                logger.info(
                    "batch_written_to_json",
                    filename=filename.name,
                    count=len(events)
                )
                return {'success': len(events), 'failed': 0}
        except Exception as e:
            logger.error("json_batch_write_failed", error=str(e))
            return {'success': 0, 'failed': len(events)}
    
    def _write_json_batch_sync(self, filename: Path, events: List[Dict[str, Any]]) -> None:
        """Synchronous JSON batch write."""
        if self.compression:
            import gzip
            with gzip.open(filename, 'at', encoding='utf-8') as f:
                for event in events:
                    json.dump(event, f, indent=2 if self.pretty_print else None)
                    f.write('\n')
        else:
            with open(filename, 'a', encoding='utf-8') as f:
                for event in events:
                    json.dump(event, f, indent=2 if self.pretty_print else None)
                    f.write('\n')
    
    async def health_check(self) -> Dict[str, Any]:
        """Check JSON export health."""
        try:
            # Check if directory is writable
            test_file = self.output_dir / '.health_check'
            test_file.write_text('ok')
            test_file.unlink()
            
            return {
                'status': 'healthy',
                'integration': self.name,
                'backend': 'json_export',
                'output_dir': str(self.output_dir),
                'compression': self.compression,
                'writable': True
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'integration': self.name,
                'backend': 'json_export',
                'error': str(e),
                'writable': False
            }
    
    async def close(self) -> None:
        """Cleanup (nothing to close for JSON)."""
        logger.info("json_export_closed", name=self.name)

