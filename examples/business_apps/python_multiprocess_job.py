"""
Realistic Python multiprocess job processing file data.

Business Scenario:
- Parent job spawns 20+ subjobs (multiprocessing)
- Each subjob processes 1MB file data
- Tasks take ~1 minute average (simulated)
- Full monitoring with parent-child relationship
"""
import sys
import os
import time
import multiprocessing as mp
from pathlib import Path
from uuid import uuid4
import hashlib
import json

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "apps"))

try:
    from monitoring_sdk import AppRef, Monitored, SidecarEmitter
except ImportError:
    # Alternative: add SDK to path if not installed
    import sys
    from pathlib import Path
    sdk_path = Path(__file__).parent.parent.parent / "components" / "monitoring" / "sdk" / "python"
    sys.path.insert(0, str(sdk_path))
    from monitoring_sdk import AppRef, Monitored, SidecarEmitter


def generate_test_file(file_path: Path, size_mb: int = 1) -> None:
    """Generate a test file of specified size."""
    with open(file_path, 'wb') as f:
        # Write 1MB of pseudo-random data
        data = os.urandom(size_mb * 1024 * 1024)
        f.write(data)


def process_file_data(file_path: Path) -> dict:
    """
    Simulate processing file data.
    - Read file
    - Compute hash
    - Perform transformation
    - Return metrics
    """
    start_time = time.time()
    
    # Read file
    with open(file_path, 'rb') as f:
        data = f.read()
    
    file_size = len(data)
    
    # Compute hash (CPU intensive)
    hash_md5 = hashlib.md5(data).hexdigest()
    hash_sha256 = hashlib.sha256(data).hexdigest()
    
    # Simulate data transformation (sleep to simulate ~1 min processing)
    # For testing, we'll use 1 second instead of 60
    processing_time = 1.0  # In production: 60.0
    time.sleep(processing_time)
    
    # Simulate some computation
    byte_sum = sum(data[:1000])  # Sample first 1000 bytes
    
    elapsed = time.time() - start_time
    
    return {
        'file_path': str(file_path),
        'file_size_bytes': file_size,
        'file_size_mb': file_size / (1024 * 1024),
        'md5': hash_md5,
        'sha256': hash_sha256,
        'byte_sum': byte_sum,
        'processing_time_s': elapsed
    }


def subjob_worker(
    subjob_id: int,
    file_path: Path,
    site_id: str,
    app: AppRef,
    parent_job_id: str,
    sidecar_url: str
) -> dict:
    """
    Worker function for subjob processing.
    Runs in separate process with full monitoring.
    """
    emitter = SidecarEmitter(base_url=sidecar_url)
    
    # Monitor this subjob
    with Monitored(
        site_id=site_id,
        app=app,
        entity_type='subjob',
        business_key=f'subjob-{subjob_id:03d}',
        emitter=emitter,
        parent_job_id=parent_job_id,
        enable_logging=True
    ) as mon:
        try:
            # Process the file
            result = process_file_data(file_path)
            result['subjob_id'] = subjob_id
            
            # Report progress milestones
            mon.progress(current=50, total=100, message="Processing file data")
            mon.progress(current=100, total=100, message="Processing complete")
            
            return {
                'success': True,
                'subjob_id': subjob_id,
                'result': result
            }
        
        except Exception as e:
            return {
                'success': False,
                'subjob_id': subjob_id,
                'error': str(e)
            }


def run_multiprocess_job(
    num_subjobs: int = 20,
    site_id: str = 'site1',
    data_dir: Path = None,
    sidecar_url: str = None
) -> dict:
    """
    Main job that spawns multiple subjobs.
    
    Args:
        num_subjobs: Number of subjobs to spawn
        site_id: Site identifier
        data_dir: Directory for test files
        sidecar_url: Sidecar agent URL
        
    Returns:
        Job results summary
    """
    if data_dir is None:
        data_dir = Path('/tmp/wafer-test-data')
    
    if sidecar_url is None:
        sidecar_url = os.getenv('SIDECAR_URL', 'http://localhost:17000')
    
    # Create data directory
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Create app reference
    app = AppRef(
        app_id=uuid4(),
        name='python-multiprocess-job',
        version='1.0.0'
    )
    
    emitter = SidecarEmitter(base_url=sidecar_url)
    
    # Monitor the main job
    with Monitored(
        site_id=site_id,
        app=app,
        entity_type='job',
        business_key='multiprocess-batch',
        emitter=emitter,
        enable_logging=True,
        metadata={'num_subjobs': num_subjobs, 'language': 'python'}
    ) as main_mon:
        
        parent_job_id = str(main_mon.entity_ref.entity_id)
        
        # Generate test files
        print(f"Generating {num_subjobs} test files (1MB each)...")
        file_paths = []
        for i in range(num_subjobs):
            file_path = data_dir / f'test_file_{i:03d}.dat'
            generate_test_file(file_path, size_mb=1)
            file_paths.append(file_path)
        
        main_mon.progress(
            current=1,
            total=3,
            message=f"Generated {num_subjobs} test files"
        )
        
        # Spawn subjobs using multiprocessing
        print(f"Spawning {num_subjobs} subjobs...")
        
        # Use process pool for parallel execution
        pool = mp.Pool(processes=min(num_subjobs, mp.cpu_count()))
        
        # Create tasks
        tasks = [
            (i, file_paths[i], site_id, app, parent_job_id, sidecar_url)
            for i in range(num_subjobs)
        ]
        
        # Execute subjobs in parallel
        start_time = time.time()
        results = pool.starmap(subjob_worker, tasks)
        pool.close()
        pool.join()
        
        elapsed = time.time() - start_time
        
        main_mon.progress(
            current=2,
            total=3,
            message=f"All {num_subjobs} subjobs completed"
        )
        
        # Analyze results
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        
        # Calculate statistics
        processing_times = [
            r['result']['processing_time_s']
            for r in results if r['success']
        ]
        
        avg_processing_time = (
            sum(processing_times) / len(processing_times)
            if processing_times else 0
        )
        
        total_data_mb = sum(
            r['result']['file_size_mb']
            for r in results if r['success']
        )
        
        summary = {
            'total_subjobs': num_subjobs,
            'successful': successful,
            'failed': failed,
            'total_elapsed_s': elapsed,
            'avg_processing_time_s': avg_processing_time,
            'total_data_mb': total_data_mb,
            'throughput_mb_per_s': total_data_mb / elapsed if elapsed > 0 else 0,
            'parallel_efficiency': (
                (avg_processing_time * num_subjobs) / elapsed
                if elapsed > 0 else 0
            )
        }
        
        main_mon.progress(
            current=3,
            total=3,
            message="Job completed successfully"
        )
        
        print("\n" + "="*60)
        print("JOB SUMMARY")
        print("="*60)
        print(f"Total Subjobs: {summary['total_subjobs']}")
        print(f"Successful: {summary['successful']}")
        print(f"Failed: {summary['failed']}")
        print(f"Total Elapsed: {summary['total_elapsed_s']:.2f}s")
        print(f"Avg Processing Time: {summary['avg_processing_time_s']:.2f}s")
        print(f"Total Data Processed: {summary['total_data_mb']:.2f} MB")
        print(f"Throughput: {summary['throughput_mb_per_s']:.2f} MB/s")
        print(f"Parallel Efficiency: {summary['parallel_efficiency']:.2%}")
        print("="*60)
        
        # Cleanup test files
        for file_path in file_paths:
            file_path.unlink(missing_ok=True)
        
        return summary


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Python multiprocess job with monitoring'
    )
    parser.add_argument(
        '--num-subjobs',
        type=int,
        default=20,
        help='Number of subjobs to spawn (default: 20)'
    )
    parser.add_argument(
        '--site-id',
        type=str,
        default='site1',
        help='Site identifier (default: site1)'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        default='/tmp/wafer-test-data',
        help='Directory for test files'
    )
    parser.add_argument(
        '--sidecar-url',
        type=str,
        default=None,
        help='Sidecar agent URL (default: from SIDECAR_URL env or localhost:17000)'
    )
    
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    
    try:
        summary = run_multiprocess_job(
            num_subjobs=args.num_subjobs,
            site_id=args.site_id,
            data_dir=data_dir,
            sidecar_url=args.sidecar_url
        )
        
        # Exit with success
        return 0
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

