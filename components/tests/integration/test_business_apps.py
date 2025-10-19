"""
Integration tests for realistic business applications.

Tests multiprocess/multithread jobs across Python, Java, C, and Perl.
"""
import pytest
import asyncio
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch
import asyncpg

# Add apps to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "apps"))

from monitoring_sdk import AppRef, SidecarEmitter
from monitoring_sdk.context import Monitored


@pytest.fixture
async def mock_sidecar_events():
    """Mock sidecar to capture events."""
    events = []
    
    class MockEmitter:
        def __init__(self, base_url=None):
            self.base_url = base_url or "http://localhost:17000"
        
        def send(self, event):
            events.append(event.model_dump())
        
        def send_batch(self, batch):
            for event in batch:
                events.append(event.model_dump())
    
    return events, MockEmitter


@pytest.fixture
def project_root():
    """Get project root directory."""
    return Path(__file__).parent.parent.parent


class TestPythonMultiprocessJob:
    """Test Python multiprocess job."""
    
    def test_import_python_job(self, project_root):
        """Test that Python job module can be imported."""
        job_path = project_root / "examples" / "business_apps" / "python_multiprocess_job.py"
        assert job_path.exists(), f"Python job not found at {job_path}"
        
        # Check key functions exist
        import importlib.util
        spec = importlib.util.spec_from_file_location("python_job", job_path)
        module = importlib.util.module_from_spec(spec)
        
        assert hasattr(module, 'run_multiprocess_job')
        assert hasattr(module, 'subjob_worker')
        assert hasattr(module, 'process_file_data')
    
    @pytest.mark.asyncio
    async def test_python_job_with_mock_sidecar(
        self,
        project_root,
        mock_sidecar_events,
        tmp_path
    ):
        """Test Python multiprocess job with mocked sidecar."""
        events, MockEmitter = mock_sidecar_events
        
        # Import the job module
        job_path = project_root / "examples" / "business_apps" / "python_multiprocess_job.py"
        
        import importlib.util
        spec = importlib.util.spec_from_file_location("python_job", job_path)
        python_job = importlib.util.module_from_spec(spec)
        
        # Patch the SidecarEmitter
        with patch('monitoring_sdk.emitter.SidecarEmitter', MockEmitter):
            spec.loader.exec_module(python_job)
            
            # Run job with small number of subjobs for testing
            result = python_job.run_multiprocess_job(
                num_subjobs=5,  # Small for fast testing
                site_id='test-site',
                data_dir=tmp_path / "test-data"
            )
            
            # Verify result
            assert result['total_subjobs'] == 5
            assert result['successful'] >= 4  # At least 80% success
            assert result['failed'] <= 1
            assert result['total_elapsed_s'] > 0
            assert result['avg_processing_time_s'] > 0
            
            # Verify monitoring events were sent
            assert len(events) >= 6  # 1 parent + 5 subjobs (start + finish each)
            
            # Check parent job event
            parent_events = [e for e in events if e['entity']['type'] == 'job']
            assert len(parent_events) >= 2  # start + finish
            
            # Check subjob events
            subjob_events = [e for e in events if e['entity']['type'] == 'subjob']
            assert len(subjob_events) >= 5
    
    def test_file_generation(self, project_root, tmp_path):
        """Test file generation produces correct size."""
        job_path = project_root / "examples" / "business_apps" / "python_multiprocess_job.py"
        
        import importlib.util
        spec = importlib.util.spec_from_file_location("python_job", job_path)
        python_job = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(python_job)
        
        test_file = tmp_path / "test.dat"
        python_job.generate_test_file(test_file, size_mb=1)
        
        assert test_file.exists()
        file_size_mb = test_file.stat().st_size / (1024 * 1024)
        assert 0.95 <= file_size_mb <= 1.05  # Within 5% tolerance
    
    def test_file_processing(self, project_root, tmp_path):
        """Test file data processing."""
        job_path = project_root / "examples" / "business_apps" / "python_multiprocess_job.py"
        
        import importlib.util
        spec = importlib.util.spec_from_file_location("python_job", job_path)
        python_job = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(python_job)
        
        # Generate test file
        test_file = tmp_path / "test.dat"
        python_job.generate_test_file(test_file, size_mb=1)
        
        # Process it
        result = python_job.process_file_data(test_file)
        
        assert result['file_size_mb'] > 0.95
        assert result['file_size_mb'] < 1.05
        assert len(result['md5']) == 32
        assert len(result['sha256']) == 64
        assert result['processing_time_s'] >= 0.9  # ~1 second
        assert result['byte_sum'] > 0


class TestPythonJobEndToEnd:
    """End-to-end tests requiring running sidecar."""
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_python_job_real_execution(self, project_root, tmp_path):
        """Test actual execution of Python job (requires sidecar)."""
        job_script = project_root / "examples" / "business_apps" / "python_multiprocess_job.py"
        
        # Run with minimal subjobs
        result = subprocess.run(
            [
                sys.executable,
                str(job_script),
                '--num-subjobs', '3',
                '--site-id', 'test-site',
                '--data-dir', str(tmp_path / "test-data")
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Check execution
        assert result.returncode == 0, f"Job failed: {result.stderr}"
        
        # Check output
        assert "JOB SUMMARY" in result.stdout
        assert "Total Subjobs: 3" in result.stdout
        assert "Successful:" in result.stdout


class TestMonitoringSDKIntegration:
    """Test monitoring SDK with realistic scenarios."""
    
    @pytest.mark.asyncio
    async def test_parent_child_relationship(self, mock_sidecar_events):
        """Test parent-child job relationship tracking."""
        events, MockEmitter = mock_sidecar_events
        
        from uuid import uuid4
        
        with patch('monitoring_sdk.emitter.SidecarEmitter', MockEmitter):
            app = AppRef(app_id=uuid4(), name='test-app', version='1.0.0')
            emitter = MockEmitter()
            
            # Parent job
            with Monitored(
                site_id='site1',
                app=app,
                entity_type='job',
                business_key='parent',
                emitter=emitter
            ) as parent:
                parent_job_id = str(parent.entity_ref.entity_id)
                
                # Child subjobs
                for i in range(3):
                    with Monitored(
                        site_id='site1',
                        app=app,
                        entity_type='subjob',
                        business_key=f'child-{i}',
                        emitter=emitter,
                        parent_job_id=parent_job_id
                    ) as child:
                        time.sleep(0.1)  # Simulate work
            
            # Verify events
            assert len(events) >= 8  # 2 parent + 6 children (start+finish each)
            
            # Check parent events
            parent_events = [e for e in events if e['entity']['business_key'] == 'parent']
            assert len(parent_events) == 2
            
            # Check child events have parent reference
            child_events = [e for e in events if 'child-' in e['entity']['business_key']]
            for child_event in child_events:
                if 'metadata' in child_event['event']:
                    assert child_event['event']['metadata'].get('parent_job_id') == parent_job_id
    
    @pytest.mark.asyncio
    async def test_progress_reporting(self, mock_sidecar_events):
        """Test progress reporting in jobs."""
        events, MockEmitter = mock_sidecar_events
        
        from uuid import uuid4
        
        with patch('monitoring_sdk.emitter.SidecarEmitter', MockEmitter):
            app = AppRef(app_id=uuid4(), name='test-app', version='1.0.0')
            emitter = MockEmitter()
            
            with Monitored(
                site_id='site1',
                app=app,
                entity_type='job',
                business_key='progress-test',
                emitter=emitter
            ) as job:
                # Report progress
                job.progress(current=25, total=100, message="25% complete")
                job.progress(current=50, total=100, message="50% complete")
                job.progress(current=75, total=100, message="75% complete")
                job.progress(current=100, total=100, message="Complete")
            
            # Verify progress events
            progress_events = [e for e in events if e['event']['kind'] == 'progress']
            assert len(progress_events) == 4
            
            # Check progress values
            assert progress_events[0]['event']['metrics']['progress_pct'] == 25
            assert progress_events[1]['event']['metrics']['progress_pct'] == 50
            assert progress_events[2]['event']['metrics']['progress_pct'] == 75
            assert progress_events[3]['event']['metrics']['progress_pct'] == 100
    
    @pytest.mark.asyncio
    async def test_error_handling(self, mock_sidecar_events):
        """Test error handling in monitored jobs."""
        events, MockEmitter = mock_sidecar_events
        
        from uuid import uuid4
        
        with patch('monitoring_sdk.emitter.SidecarEmitter', MockEmitter):
            app = AppRef(app_id=uuid4(), name='test-app', version='1.0.0')
            emitter = MockEmitter()
            
            # Job that fails
            with pytest.raises(ValueError):
                with Monitored(
                    site_id='site1',
                    app=app,
                    entity_type='job',
                    business_key='failing-job',
                    emitter=emitter
                ) as job:
                    raise ValueError("Test error")
            
            # Verify error was recorded
            finish_events = [e for e in events if e['event']['kind'] == 'finished']
            assert len(finish_events) == 1
            assert finish_events[0]['event']['status'] == 'failed'


class TestPerformanceMetrics:
    """Test performance metrics collection."""
    
    @pytest.mark.asyncio
    async def test_cpu_metrics_collected(self, mock_sidecar_events):
        """Test CPU metrics are collected."""
        events, MockEmitter = mock_sidecar_events
        
        from uuid import uuid4
        import math
        
        with patch('monitoring_sdk.emitter.SidecarEmitter', MockEmitter):
            app = AppRef(app_id=uuid4(), name='test-app', version='1.0.0')
            emitter = MockEmitter()
            
            with Monitored(
                site_id='site1',
                app=app,
                entity_type='job',
                business_key='cpu-test',
                emitter=emitter
            ):
                # Do some CPU work
                result = sum(math.sqrt(i) for i in range(100000))
            
            # Check finish event has CPU metrics
            finish_events = [e for e in events if e['event']['kind'] == 'finished']
            assert len(finish_events) == 1
            
            metrics = finish_events[0]['event']['metrics']
            assert 'cpu_user_s' in metrics
            assert 'cpu_system_s' in metrics
            assert metrics['cpu_user_s'] >= 0
    
    @pytest.mark.asyncio
    async def test_memory_metrics_collected(self, mock_sidecar_events):
        """Test memory metrics are collected."""
        events, MockEmitter = mock_sidecar_events
        
        from uuid import uuid4
        
        with patch('monitoring_sdk.emitter.SidecarEmitter', MockEmitter):
            app = AppRef(app_id=uuid4(), name='test-app', version='1.0.0')
            emitter = MockEmitter()
            
            with Monitored(
                site_id='site1',
                app=app,
                entity_type='job',
                business_key='mem-test',
                emitter=emitter
            ):
                # Allocate some memory
                data = [0] * 1000000  # ~8MB
                _ = sum(data)
            
            # Check finish event has memory metrics
            finish_events = [e for e in events if e['event']['kind'] == 'finished']
            assert len(finish_events) == 1
            
            metrics = finish_events[0]['event']['metrics']
            assert 'mem_max_mb' in metrics
            assert metrics['mem_max_mb'] > 0


class TestScalability:
    """Test system scalability with many subjobs."""
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_many_subjobs(self, mock_sidecar_events, tmp_path):
        """Test handling many concurrent subjobs."""
        events, MockEmitter = mock_sidecar_events
        
        from uuid import uuid4
        import multiprocessing as mp
        
        with patch('monitoring_sdk.emitter.SidecarEmitter', MockEmitter):
            app = AppRef(app_id=uuid4(), name='test-app', version='1.0.0')
            emitter = MockEmitter()
            
            num_subjobs = 50  # More realistic load
            
            with Monitored(
                site_id='site1',
                app=app,
                entity_type='job',
                business_key='scalability-test',
                emitter=emitter
            ) as parent:
                parent_job_id = str(parent.entity_ref.entity_id)
                
                def worker(i):
                    with Monitored(
                        site_id='site1',
                        app=app,
                        entity_type='subjob',
                        business_key=f'subjob-{i}',
                        emitter=emitter,
                        parent_job_id=parent_job_id
                    ):
                        time.sleep(0.01)  # Minimal work
                    return i
                
                # Use thread pool for testing (faster than processes)
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=10) as executor:
                    results = list(executor.map(worker, range(num_subjobs)))
                
                assert len(results) == num_subjobs
            
            # Verify all subjobs reported
            subjob_events = [e for e in events if e['entity']['type'] == 'subjob']
            assert len(subjob_events) >= num_subjobs  # At least start events


@pytest.mark.integration
class TestDatabaseIntegration:
    """Test database integration (requires running database)."""
    
    @pytest.mark.asyncio
    async def test_events_stored_in_database(self):
        """Test that events are properly stored in database."""
        # This test requires a running database and local API
        pytest.skip("Requires running database - enable for full integration tests")
        
        # Example implementation:
        # 1. Send events via API
        # 2. Query database
        # 3. Verify events are stored with correct relationships


# Pytest configuration
def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

