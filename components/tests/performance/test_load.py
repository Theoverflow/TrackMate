"""Performance and load tests."""
import pytest
import asyncio
import httpx
from uuid import uuid4
from datetime import datetime, timezone
import time
from statistics import mean, stdev


@pytest.mark.performance
class TestPerformance:
    """Performance test suite."""
    
    SIDECAR_URL = 'http://localhost:8000'
    LOCAL_API_URL = 'http://localhost:18000'
    
    def create_test_event(self, job_id: str = None):
        """Create a test event."""
        return {
            'idempotency_key': str(uuid4()),
            'site_id': 'perf-test',
            'app': {
                'app_id': str(uuid4()),
                'name': 'perf-test-app',
                'version': '1.0.0'
            },
            'entity': {
                'type': 'job',
                'id': job_id or str(uuid4()),
                'parent_id': None,
                'business_key': 'perf-test',
                'sub_key': None
            },
            'event': {
                'kind': 'started',
                'at': datetime.now(timezone.utc).isoformat(),
                'status': 'running',
                'metrics': {'cpu_user_s': 0.1, 'mem_max_mb': 100.0},
                'metadata': {'test': 'performance'}
            }
        }
    
    @pytest.mark.asyncio
    async def test_single_event_latency(self):
        """Test latency for single event ingestion."""
        latencies = []
        
        async with httpx.AsyncClient() as client:
            for _ in range(100):
                event = self.create_test_event()
                
                start = time.time()
                r = await client.post(
                    f'{self.SIDECAR_URL}/v1/ingest/events',
                    json=event,
                    timeout=10.0
                )
                latency = time.time() - start
                
                assert r.status_code == 200
                latencies.append(latency)
        
        avg_latency = mean(latencies)
        std_latency = stdev(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        
        print(f"\n=== Single Event Latency ===")
        print(f"Average: {avg_latency*1000:.2f}ms")
        print(f"StdDev: {std_latency*1000:.2f}ms")
        print(f"P95: {p95_latency*1000:.2f}ms")
        print(f"Max: {max(latencies)*1000:.2f}ms")
        
        # Assert reasonable performance (adjust thresholds as needed)
        assert avg_latency < 0.5, f"Average latency too high: {avg_latency}s"
        assert p95_latency < 1.0, f"P95 latency too high: {p95_latency}s"
    
    @pytest.mark.asyncio
    async def test_batch_throughput(self):
        """Test batch ingestion throughput."""
        batch_sizes = [10, 50, 100]
        
        for batch_size in batch_sizes:
            events = [self.create_test_event() for _ in range(batch_size)]
            
            start = time.time()
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f'{self.SIDECAR_URL}/v1/ingest/events:batch',
                    json=events,
                    timeout=30.0
                )
            duration = time.time() - start
            
            assert r.status_code == 200
            
            throughput = batch_size / duration
            print(f"\n=== Batch Size: {batch_size} ===")
            print(f"Duration: {duration:.2f}s")
            print(f"Throughput: {throughput:.2f} events/s")
            
            # Should process at least 50 events/second
            assert throughput > 50, f"Throughput too low: {throughput} events/s"
    
    @pytest.mark.asyncio
    async def test_concurrent_ingestion(self):
        """Test concurrent event ingestion."""
        num_concurrent = 20
        events_per_task = 10
        
        async def send_events():
            async with httpx.AsyncClient() as client:
                for _ in range(events_per_task):
                    event = self.create_test_event()
                    await client.post(
                        f'{self.SIDECAR_URL}/v1/ingest/events',
                        json=event,
                        timeout=10.0
                    )
        
        start = time.time()
        tasks = [send_events() for _ in range(num_concurrent)]
        await asyncio.gather(*tasks)
        duration = time.time() - start
        
        total_events = num_concurrent * events_per_task
        throughput = total_events / duration
        
        print(f"\n=== Concurrent Ingestion ===")
        print(f"Concurrent tasks: {num_concurrent}")
        print(f"Total events: {total_events}")
        print(f"Duration: {duration:.2f}s")
        print(f"Throughput: {throughput:.2f} events/s")
        
        # Should handle concurrent load
        assert throughput > 100, f"Concurrent throughput too low: {throughput} events/s"
    
    @pytest.mark.asyncio
    async def test_query_performance(self):
        """Test query endpoint performance."""
        latencies = []
        
        async with httpx.AsyncClient() as client:
            for _ in range(50):
                start = time.time()
                r = await client.get(
                    f'{self.LOCAL_API_URL}/v1/jobs',
                    params={'limit': 100},
                    timeout=5.0
                )
                latency = time.time() - start
                
                assert r.status_code == 200
                latencies.append(latency)
        
        avg_latency = mean(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        
        print(f"\n=== Query Performance ===")
        print(f"Average: {avg_latency*1000:.2f}ms")
        print(f"P95: {p95_latency*1000:.2f}ms")
        
        # Queries should be fast
        assert avg_latency < 0.2, f"Query latency too high: {avg_latency}s"
        assert p95_latency < 0.5, f"P95 query latency too high: {p95_latency}s"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s', '-m', 'performance'])

