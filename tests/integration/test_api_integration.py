"""Integration tests for API services."""
import pytest
import asyncio
from uuid import uuid4
from datetime import datetime, timezone
import httpx


@pytest.mark.asyncio
class TestSidecarAgentIntegration:
    """Integration tests for Sidecar Agent."""
    
    BASE_URL = 'http://localhost:8000'
    
    async def test_health_endpoint(self):
        """Test health check endpoint."""
        async with httpx.AsyncClient() as client:
            r = await client.get(f'{self.BASE_URL}/v1/healthz')
            assert r.status_code == 200
            data = r.json()
            assert data['status'] == 'ok'
            assert 'spool_count' in data
    
    async def test_ingest_single_event(self):
        """Test ingesting a single event."""
        event = {
            'idempotency_key': str(uuid4()),
            'site_id': 'test-fab',
            'app': {
                'app_id': str(uuid4()),
                'name': 'test-app',
                'version': '1.0.0'
            },
            'entity': {
                'type': 'job',
                'id': str(uuid4()),
                'parent_id': None,
                'business_key': 'test-job',
                'sub_key': None
            },
            'event': {
                'kind': 'started',
                'at': datetime.now(timezone.utc).isoformat(),
                'status': 'running',
                'metrics': {},
                'metadata': {}
            }
        }
        
        async with httpx.AsyncClient() as client:
            r = await client.post(f'{self.BASE_URL}/v1/ingest/events', json=event, timeout=10.0)
            assert r.status_code == 200
            data = r.json()
            assert data['ok'] is True
    
    async def test_ingest_batch(self):
        """Test ingesting a batch of events."""
        events = []
        for i in range(5):
            events.append({
                'idempotency_key': str(uuid4()),
                'site_id': 'test-fab',
                'app': {
                    'app_id': str(uuid4()),
                    'name': 'test-app',
                    'version': '1.0.0'
                },
                'entity': {
                    'type': 'job',
                    'id': str(uuid4()),
                    'parent_id': None,
                    'business_key': f'test-job-{i}',
                    'sub_key': None
                },
                'event': {
                    'kind': 'started',
                    'at': datetime.now(timezone.utc).isoformat(),
                    'status': 'running',
                    'metrics': {},
                    'metadata': {}
                }
            })
        
        async with httpx.AsyncClient() as client:
            r = await client.post(f'{self.BASE_URL}/v1/ingest/events:batch', json=events, timeout=10.0)
            assert r.status_code == 200
            data = r.json()
            assert data['ok'] is True


@pytest.mark.asyncio
class TestLocalAPIIntegration:
    """Integration tests for Local API."""
    
    BASE_URL = 'http://localhost:18000'
    
    async def test_health_endpoint(self):
        """Test health check endpoint."""
        async with httpx.AsyncClient() as client:
            r = await client.get(f'{self.BASE_URL}/v1/healthz')
            assert r.status_code == 200
            data = r.json()
            assert 'status' in data
    
    async def test_jobs_query(self):
        """Test querying jobs."""
        async with httpx.AsyncClient() as client:
            r = await client.get(f'{self.BASE_URL}/v1/jobs', params={'limit': 10})
            assert r.status_code == 200
            data = r.json()
            assert 'items' in data
            assert 'count' in data
    
    async def test_subjobs_query(self):
        """Test querying subjobs."""
        async with httpx.AsyncClient() as client:
            r = await client.get(f'{self.BASE_URL}/v1/subjobs', params={'limit': 10})
            assert r.status_code == 200
            data = r.json()
            assert 'items' in data
    
    async def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint."""
        async with httpx.AsyncClient() as client:
            r = await client.get(f'{self.BASE_URL}/metrics')
            assert r.status_code == 200
            # Metrics should be in Prometheus text format
            assert b'http_requests_total' in r.content or b'# TYPE' in r.content


@pytest.mark.asyncio
class TestCentralAPIIntegration:
    """Integration tests for Central API."""
    
    BASE_URL = 'http://localhost:19000'
    
    async def test_health_endpoint(self):
        """Test health check endpoint."""
        async with httpx.AsyncClient() as client:
            r = await client.get(f'{self.BASE_URL}/v1/healthz')
            assert r.status_code == 200
            data = r.json()
            assert 'status' in data
            assert 'sites' in data
    
    async def test_list_sites(self):
        """Test listing configured sites."""
        async with httpx.AsyncClient() as client:
            r = await client.get(f'{self.BASE_URL}/v1/sites')
            assert r.status_code == 200
            data = r.json()
            assert 'sites' in data
            assert 'count' in data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

