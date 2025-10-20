"""
Runtime Configuration and Hot-Reloading for Python SDK

Enables dynamic configuration updates without application restart:
- Load config from YAML/JSON files
- Watch for config file changes
- Hot-swap backends without dropping events
- Fault-tolerant config reloading
"""

import asyncio
import time
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import yaml
import json

from .config import MonitoringConfig, configure, get_config
from .router import BackendRouter

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class ConfigFileHandler(FileSystemEventHandler):
    """Handles file system events for config file changes."""
    
    def __init__(self, config_path: Path, reload_callback: Callable):
        self.config_path = config_path
        self.reload_callback = reload_callback
        self._last_reload = 0
        self._min_reload_interval = 1.0  # Minimum 1 second between reloads
    
    def on_modified(self, event):
        if event.src_path == str(self.config_path):
            # Debounce: prevent multiple rapid reloads
            current_time = time.time()
            if current_time - self._last_reload >= self._min_reload_interval:
                self._last_reload = current_time
                # Small delay to ensure file write is complete
                time.sleep(0.1)
                self.reload_callback()


class RuntimeConfigManager:
    """
    Manages runtime configuration with hot-reloading support.
    
    Example usage:
        >>> manager = RuntimeConfigManager(
        ...     config_file_path="monitoring_config.yaml",
        ...     default_config=default_config,
        ...     auto_reload=True,
        ...     on_reload=lambda success, msg: print(f"Reload: {msg}")
        ... )
        >>> manager.initialize()
        >>> # Config changes are automatically detected and applied
        >>> # ... application runs ...
        >>> manager.shutdown()
    """
    
    def __init__(
        self,
        config_file_path: str,
        default_config: Optional[MonitoringConfig] = None,
        auto_reload: bool = True,
        on_reload: Optional[Callable[[bool, str], None]] = None,
        use_fallback: bool = True
    ):
        """
        Initialize runtime config manager.
        
        Args:
            config_file_path: Path to configuration file (YAML or JSON)
            default_config: Default config to use as fallback
            auto_reload: Enable automatic config reloading
            on_reload: Callback function(success: bool, message: str)
            use_fallback: Use default config if file not found/invalid
        """
        self.config_file_path = Path(config_file_path)
        self.default_config = default_config
        self.auto_reload = auto_reload
        self.on_reload = on_reload
        self.use_fallback = use_fallback
        
        self.current_config: Optional[MonitoringConfig] = None
        self.router: Optional[BackendRouter] = None
        
        self._observer: Optional[Observer] = None
        self._lock = threading.RLock()
        self._initialized = False
        self._last_reload_time = 0
        self._last_reload_success = False
    
    def initialize(self) -> bool:
        """
        Initialize the runtime config manager.
        
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            if self._initialized:
                logger.warning("Runtime config manager already initialized")
                return True
            
            # Try to load config from file
            config = self._load_config_from_file()
            
            if config is None and self.use_fallback and self.default_config:
                # Use default config as fallback
                config = self.default_config
                logger.info("Using default config as fallback")
            elif config is None:
                logger.error("Failed to load config and no fallback available")
                return False
            
            # Configure the SDK
            try:
                configure(**config.model_dump())
                self.current_config = config
                logger.info("SDK configured successfully", 
                           config_file=str(self.config_file_path))
            except Exception as e:
                logger.error("Failed to configure SDK", error=str(e))
                if self.on_reload:
                    self.on_reload(False, f"Config failed: {str(e)}")
                return False
            
            # Start file watcher if auto-reload enabled
            if self.auto_reload:
                self._start_file_watcher()
            
            self._initialized = True
            self._last_reload_success = True
            self._last_reload_time = time.time()
            
            if self.on_reload:
                self.on_reload(True, "Initial configuration loaded")
            
            return True
    
    def reload(self) -> bool:
        """
        Manually trigger configuration reload.
        
        Returns:
            True if reload successful, False otherwise
        """
        with self._lock:
            if not self._initialized:
                logger.error("Runtime config manager not initialized")
                return False
            
            logger.info("Manually reloading configuration")
            return self._reload_config()
    
    def shutdown(self):
        """Shutdown the runtime config manager."""
        with self._lock:
            if self._observer:
                self._observer.stop()
                self._observer.join()
                self._observer = None
            
            self._initialized = False
            logger.info("Runtime config manager shut down")
    
    def get_reload_status(self) -> Dict[str, Any]:
        """
        Get the status of the last config reload.
        
        Returns:
            Dictionary with reload status information
        """
        with self._lock:
            return {
                "last_reload_time": self._last_reload_time,
                "last_reload_success": self._last_reload_success,
                "config_file": str(self.config_file_path),
                "auto_reload": self.auto_reload,
                "initialized": self._initialized
            }
    
    def set_auto_reload(self, enabled: bool):
        """
        Enable or disable automatic config reloading.
        
        Args:
            enabled: True to enable, False to disable
        """
        with self._lock:
            if enabled and not self.auto_reload:
                self.auto_reload = True
                if self._initialized and not self._observer:
                    self._start_file_watcher()
                logger.info("Auto-reload enabled")
            elif not enabled and self.auto_reload:
                self.auto_reload = False
                if self._observer:
                    self._observer.stop()
                    self._observer.join()
                    self._observer = None
                logger.info("Auto-reload disabled")
    
    # Private methods
    
    def _load_config_from_file(self) -> Optional[MonitoringConfig]:
        """Load configuration from file."""
        if not self.config_file_path.exists():
            logger.warning("Config file not found", path=str(self.config_file_path))
            return None
        
        try:
            with open(self.config_file_path, 'r') as f:
                # Determine file type by extension
                if self.config_file_path.suffix in ['.yaml', '.yml']:
                    config_dict = yaml.safe_load(f)
                elif self.config_file_path.suffix == '.json':
                    config_dict = json.load(f)
                else:
                    logger.error("Unsupported config file format", 
                               suffix=self.config_file_path.suffix)
                    return None
            
            # Validate and create config object
            config = MonitoringConfig(**config_dict)
            logger.info("Config loaded from file", path=str(self.config_file_path))
            return config
            
        except Exception as e:
            logger.error("Failed to load config file", 
                        path=str(self.config_file_path), 
                        error=str(e))
            return None
    
    def _reload_config(self) -> bool:
        """Internal method to reload configuration."""
        logger.info("Reloading configuration from file")
        
        new_config = self._load_config_from_file()
        
        if new_config is None:
            self._last_reload_success = False
            self._last_reload_time = time.time()
            
            msg = "Failed to load config file"
            logger.error(msg)
            if self.on_reload:
                self.on_reload(False, msg)
            return False
        
        try:
            # Apply new configuration
            configure(**new_config.model_dump())
            self.current_config = new_config
            
            self._last_reload_success = True
            self._last_reload_time = time.time()
            
            msg = "Configuration reloaded successfully"
            logger.info(msg)
            if self.on_reload:
                self.on_reload(True, msg)
            
            return True
            
        except Exception as e:
            self._last_reload_success = False
            self._last_reload_time = time.time()
            
            msg = f"Failed to apply new config: {str(e)}"
            logger.error(msg)
            if self.on_reload:
                self.on_reload(False, msg)
            
            return False
    
    def _start_file_watcher(self):
        """Start watching config file for changes."""
        if self._observer:
            return
        
        try:
            event_handler = ConfigFileHandler(
                self.config_file_path,
                self._reload_config
            )
            
            self._observer = Observer()
            self._observer.schedule(
                event_handler,
                str(self.config_file_path.parent),
                recursive=False
            )
            self._observer.start()
            
            logger.info("File watcher started", path=str(self.config_file_path))
            
        except Exception as e:
            logger.error("Failed to start file watcher", error=str(e))


# Convenience function for common use case
def init_with_runtime_config(
    config_file_path: str,
    default_config: Optional[Dict[str, Any]] = None,
    auto_reload: bool = True,
    on_reload: Optional[Callable[[bool, str], None]] = None
) -> RuntimeConfigManager:
    """
    Initialize SDK with runtime configuration support.
    
    Args:
        config_file_path: Path to config file (YAML or JSON)
        default_config: Default configuration dict
        auto_reload: Enable automatic config reloading
        on_reload: Callback for reload events
    
    Returns:
        RuntimeConfigManager instance
    
    Example:
        >>> def reload_callback(success, message):
        ...     print(f"Config reload: {message}")
        >>> 
        >>> manager = init_with_runtime_config(
        ...     "monitoring_config.yaml",
        ...     default_config={
        ...         "mode": "sidecar",
        ...         "app": {
        ...             "name": "my-app",
        ...             "version": "1.0.0",
        ...             "site_id": "fab1"
        ...         },
        ...         "sidecar": {
        ...             "url": "http://localhost:17000"
        ...         }
        ...     },
        ...     auto_reload=True,
        ...     on_reload=reload_callback
        ... )
        >>> manager.initialize()
    """
    default_config_obj = None
    if default_config:
        default_config_obj = MonitoringConfig(**default_config)
    
    manager = RuntimeConfigManager(
        config_file_path=config_file_path,
        default_config=default_config_obj,
        auto_reload=auto_reload,
        on_reload=on_reload,
        use_fallback=True
    )
    
    manager.initialize()
    return manager

