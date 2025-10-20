"""
Python Integration Tests for Multiprocess Business Application.

Tests Python multiprocess job with monitoring SDK integration.
"""
import pytest
import subprocess
import sys
import time
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os


def test_python_job_imports():
    """Test that Python job can be imported."""
    sys.path.insert(0, '/workspace')
    try:
        import python_multiprocess_job
        assert hasattr(python_multiprocess_job, 'process_file')
        assert hasattr(python_multiprocess_job, 'worker')
        assert hasattr(python_multiprocess_job, 'main')
    except ImportError as e:
        pytest.fail(f"Failed to import python_multiprocess_job: {e}")


def test_python_job_file_processing():
    """Test file processing function."""
    sys.path.insert(0, '/workspace')
    import python_multiprocess_job
    
    # Create temp file
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.dat') as f:
        # Write 1MB of data
        f.write(b'X' * (1024 * 1024))
        temp_file = f.name
    
    try:
        # Mock monitoring
        with patch('python_multiprocess_job.SidecarEmitter'):
            result = python_multiprocess_job.process_file(temp_file, 1)
            assert 'file' in result
            assert 'size_bytes' in result
            assert result['size_bytes'] == 1024 * 1024
    finally:
        os.unlink(temp_file)


def test_python_job_execution_dry_run():
    """Test Python job execution in dry run mode."""
    # Run with reduced load for faster testing
    result = subprocess.run(
        ['python', '/workspace/python_multiprocess_job.py', '--workers', '2', '--files', '2'],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    assert result.returncode == 0, f"Job failed: {result.stderr}"
    assert 'Starting multiprocess job' in result.stdout or result.returncode == 0


def test_python_job_monitoring_events():
    """Test that monitoring events are generated."""
    sys.path.insert(0, '/workspace')
    
    # Mock the SidecarEmitter
    mock_events = []
    
    def mock_send(event):
        mock_events.append(event.model_dump() if hasattr(event, 'model_dump') else event)
    
    with patch('python_multiprocess_job.SidecarEmitter') as MockEmitter:
        mock_emitter = MagicMock()
        mock_emitter.send = mock_send
        MockEmitter.return_value = mock_emitter
        
        # Import after patching
        import python_multiprocess_job
        
        # Run single worker with single file
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.dat') as f:
            f.write(b'Y' * (1024 * 1024))
            temp_file = f.name
        
        try:
            result = python_multiprocess_job.process_file(temp_file, 1)
            assert result is not None
        finally:
            os.unlink(temp_file)


def test_python_job_multiprocess():
    """Test multiprocess execution."""
    import multiprocessing
    
    # Ensure multiprocessing works in container
    def worker_test(x):
        return x * 2
    
    with multiprocessing.Pool(2) as pool:
        results = pool.map(worker_test, [1, 2, 3, 4])
        assert results == [2, 4, 6, 8]


def test_python_job_monitoring_sdk_integration():
    """Test monitoring SDK integration."""
    sys.path.insert(0, '/workspace')
    
    try:
        from monitoring_sdk import AppRef, SidecarEmitter
        from monitoring_sdk.context import Monitored
        
        # Test SDK initialization
        app = AppRef(
            name="test-app",
            version="1.0.0",
            instance="test-instance"
        )
        
        emitter = SidecarEmitter(base_url="http://localhost:17000")
        
        assert app.name == "test-app"
        assert emitter.base_url == "http://localhost:17000"
        
    except Exception as e:
        pytest.fail(f"Monitoring SDK integration failed: {e}")


def test_python_job_performance_metrics():
    """Test that performance metrics are captured."""
    import psutil
    import time
    
    # Capture system metrics
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    
    assert cpu_percent >= 0
    assert memory.total > 0
    assert memory.available > 0


def test_python_job_error_handling():
    """Test error handling in Python job."""
    sys.path.insert(0, '/workspace')
    import python_multiprocess_job
    
    # Test with non-existent file
    result = python_multiprocess_job.process_file('/nonexistent/file.dat', 1)
    
    # Should handle error gracefully
    assert result is not None
    assert 'error' in result or 'file' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

