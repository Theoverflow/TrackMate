#!/usr/bin/env python3
"""
Simple test runner for business applications.
Runs tests without requiring pytest installation.
"""
import sys
import os
import time
from pathlib import Path
import subprocess

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "apps"))


def test_python_job_import():
    """Test that Python job can be imported."""
    print("Test: Python job import...", end=" ")
    
    try:
        import importlib.util
        job_path = Path(__file__).parent / "python_multiprocess_job.py"
        
        spec = importlib.util.spec_from_file_location("python_job", job_path)
        module = importlib.util.module_from_spec(spec)
        
        assert hasattr(module, 'run_multiprocess_job')
        assert hasattr(module, 'subjob_worker')
        assert hasattr(module, 'process_file_data')
        
        print("✓ PASS")
        return True
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False


def test_file_generation():
    """Test file generation."""
    print("Test: File generation...", end=" ")
    
    try:
        import importlib.util
        import tempfile
        
        job_path = Path(__file__).parent / "python_multiprocess_job.py"
        spec = importlib.util.spec_from_file_location("python_job", job_path)
        python_job = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(python_job)
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            test_file = Path(tmp.name)
        
        python_job.generate_test_file(test_file, size_mb=1)
        
        file_size_mb = test_file.stat().st_size / (1024 * 1024)
        assert 0.95 <= file_size_mb <= 1.05
        
        test_file.unlink()
        
        print("✓ PASS")
        return True
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False


def test_file_processing():
    """Test file processing."""
    print("Test: File processing...", end=" ")
    
    try:
        import importlib.util
        import tempfile
        
        job_path = Path(__file__).parent / "python_multiprocess_job.py"
        spec = importlib.util.spec_from_file_location("python_job", job_path)
        python_job = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(python_job)
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            test_file = Path(tmp.name)
        
        python_job.generate_test_file(test_file, size_mb=1)
        result = python_job.process_file_data(test_file)
        
        assert result['file_size_mb'] > 0.95
        assert result['file_size_mb'] < 1.05
        assert len(result['md5']) == 32
        assert len(result['sha256']) == 64
        assert result['processing_time_s'] >= 0.9
        
        test_file.unlink()
        
        print("✓ PASS")
        return True
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False


def test_monitoring_sdk():
    """Test monitoring SDK basic functionality."""
    print("Test: Monitoring SDK...", end=" ")
    
    try:
        from monitoring_sdk import AppRef, Monitored
        from uuid import uuid4
        
        app = AppRef(app_id=uuid4(), name='test', version='1.0.0')
        
        # Mock emitter
        class MockEmitter:
            def __init__(self):
                self.events = []
            
            def send(self, event):
                self.events.append(event)
        
        emitter = MockEmitter()
        
        # Test monitored context
        with Monitored(
            site_id='test',
            app=app,
            entity_type='job',
            business_key='test',
            emitter=emitter
        ) as mon:
            time.sleep(0.1)
        
        # Should have sent events
        assert len(emitter.events) >= 2  # start + finish
        
        print("✓ PASS")
        return True
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False


def test_python_job_execution():
    """Test actual Python job execution (quick version)."""
    print("Test: Python job execution (3 subjobs)...", end=" ")
    
    try:
        import tempfile
        
        job_script = Path(__file__).parent / "python_multiprocess_job.py"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(job_script),
                    '--num-subjobs', '3',
                    '--site-id', 'test',
                    '--data-dir', tmpdir
                ],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            assert result.returncode == 0, f"Job failed: {result.stderr}"
            assert "JOB SUMMARY" in result.stdout
            assert "Total Subjobs: 3" in result.stdout
        
        print("✓ PASS")
        return True
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 70)
    print("Business Applications Test Suite")
    print("=" * 70)
    print()
    
    tests = [
        test_python_job_import,
        test_file_generation,
        test_file_processing,
        test_monitoring_sdk,
        test_python_job_execution,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        if test():
            passed += 1
        else:
            failed += 1
    
    print()
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

