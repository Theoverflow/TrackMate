"""CSV export integration for local file storage."""
import csv
import os
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import asyncio
from .base import BaseIntegration, IntegrationConfig

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)  # type: ignore


class CSVExportIntegration(BaseIntegration):
    """
    CSV export integration for local file storage.
    
    Writes events to CSV files with rotation by date.
    
    Configuration:
        - output_dir: Directory for CSV files (default: /var/log/wafer-monitor)
        - rotation: Rotation strategy (daily, hourly, none)
        - include_headers: Include CSV headers (default: True)
        - delimiter: CSV delimiter (default: ,)
    """
    
    def __init__(self, config: IntegrationConfig):
        """Initialize CSV export integration."""
        super().__init__(config)
        self.output_dir = Path(self.get_config('output_dir', '/var/log/wafer-monitor'))
        self.rotation = self.get_config('rotation', 'daily')
        self.include_headers = self.get_config('include_headers', True)
        self.delimiter = self.get_config('delimiter', ',')
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """Create output directory if it doesn't exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._initialized = True
        logger.info(
            "csv_export_initialized",
            name=self.name,
            output_dir=str(self.output_dir),
            rotation=self.rotation
        )
    
    def _get_csv_filename(self) -> Path:
        """Get current CSV filename based on rotation strategy."""
        now = datetime.utcnow()
        
        if self.rotation == 'hourly':
            suffix = now.strftime('%Y%m%d_%H')
        elif self.rotation == 'daily':
            suffix = now.strftime('%Y%m%d')
        else:
            suffix = 'events'
        
        return self.output_dir / f'wafer_events_{suffix}.csv'
    
    def _flatten_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten nested event structure for CSV."""
        entity = event.get('entity', {})
        event_data = event.get('event', {})
        metrics = event_data.get('metrics', {})
        app = event.get('app', {})
        metadata = event_data.get('metadata', {})
        
        return {
            'timestamp': event_data.get('at'),
            'idempotency_key': event.get('idempotency_key'),
            'site_id': event.get('site_id'),
            'app_id': app.get('app_id'),
            'app_name': app.get('name'),
            'app_version': app.get('version'),
            'entity_type': entity.get('type'),
            'entity_id': entity.get('id'),
            'parent_id': entity.get('parent_id', ''),
            'business_key': entity.get('business_key', ''),
            'sub_key': entity.get('sub_key', ''),
            'event_kind': event_data.get('kind'),
            'status': event_data.get('status'),
            'duration_s': metrics.get('duration_s', ''),
            'cpu_user_s': metrics.get('cpu_user_s', ''),
            'cpu_system_s': metrics.get('cpu_system_s', ''),
            'mem_max_mb': metrics.get('mem_max_mb', ''),
            'metadata_json': str(metadata) if metadata else ''
        }
    
    async def send_event(self, event: Dict[str, Any]) -> bool:
        """Append event to CSV file."""
        try:
            async with self._lock:
                filename = self._get_csv_filename()
                file_exists = filename.exists()
                
                flattened = self._flatten_event(event)
                
                # Use thread executor for file I/O
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._write_csv_sync,
                    filename,
                    flattened,
                    file_exists
                )
                
                logger.debug("event_written_to_csv", filename=filename.name)
                return True
        except Exception as e:
            logger.error("csv_write_failed", error=str(e))
            return False
    
    def _write_csv_sync(self, filename: Path, data: Dict[str, Any], file_exists: bool) -> None:
        """Synchronous CSV write (called in thread executor)."""
        mode = 'a' if file_exists else 'w'
        
        with open(filename, mode, newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=data.keys(), delimiter=self.delimiter)
            
            if not file_exists and self.include_headers:
                writer.writeheader()
            
            writer.writerow(data)
    
    async def send_batch(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """Append batch of events to CSV file."""
        try:
            async with self._lock:
                filename = self._get_csv_filename()
                file_exists = filename.exists()
                
                flattened_events = [self._flatten_event(e) for e in events]
                
                # Use thread executor for file I/O
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._write_csv_batch_sync,
                    filename,
                    flattened_events,
                    file_exists
                )
                
                logger.info(
                    "batch_written_to_csv",
                    filename=filename.name,
                    count=len(events)
                )
                return {'success': len(events), 'failed': 0}
        except Exception as e:
            logger.error("csv_batch_write_failed", error=str(e))
            return {'success': 0, 'failed': len(events)}
    
    def _write_csv_batch_sync(
        self,
        filename: Path,
        data_list: List[Dict[str, Any]],
        file_exists: bool
    ) -> None:
        """Synchronous CSV batch write."""
        mode = 'a' if file_exists else 'w'
        
        with open(filename, mode, newline='', encoding='utf-8') as f:
            if data_list:
                writer = csv.DictWriter(
                    f,
                    fieldnames=data_list[0].keys(),
                    delimiter=self.delimiter
                )
                
                if not file_exists and self.include_headers:
                    writer.writeheader()
                
                writer.writerows(data_list)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check CSV export health."""
        try:
            # Check if directory is writable
            test_file = self.output_dir / '.health_check'
            test_file.write_text('ok')
            test_file.unlink()
            
            return {
                'status': 'healthy',
                'integration': self.name,
                'backend': 'csv_export',
                'output_dir': str(self.output_dir),
                'writable': True
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'integration': self.name,
                'backend': 'csv_export',
                'error': str(e),
                'writable': False
            }
    
    async def close(self) -> None:
        """Cleanup (nothing to close for CSV)."""
        logger.info("csv_export_closed", name=self.name)

