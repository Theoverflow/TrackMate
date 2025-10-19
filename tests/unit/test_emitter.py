"""Unit tests for SidecarEmitter."""
import pytest
from uuid import uuid4
from unittest.mock import Mock, patch
import httpx

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'apps' / 'monitoring_sdk'))

from monitoring_sdk.emitter import SidecarEmitter
from monitoring_sdk.models import AppRef, EntityRef, JobEvent


class TestSidecarEmitter:
    """Test suite for SidecarEmitter."""
    
    def test_initialization(self):
        """Test emitter initialization."""
        emitter = SidecarEmitter(base_url='http://test:8000', timeout=10.0)
        assert emitter.base_url == 'http://test:8000'
        assert emitter.timeout == 10.0
    
    def test_initialization_from_env(self, monkeypatch):
        """Test emitter initialization from environment variables."""
        monkeypatch.setenv('SIDECAR_URL', 'http://env-test:9000')
        emitter = SidecarEmitter()
        assert emitter.base_url == 'http://env-test:9000'
    
    @patch('httpx.Client.post')
    def test_send_event_success(self, mock_post):
        """Test sending a single event successfully."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        emitter = SidecarEmitter(enable_retries=False)
        app = AppRef(app_id=uuid4(), name='test-app', version='1.0')
        entity = EntityRef(type='job', id=uuid4(), parent_id=None, business_key='test', sub_key=None)
        event = JobEvent.now('started', 'fab1', app, entity, status='running')
        
        emitter.send(event)
        
        assert mock_post.called
        assert mock_post.call_count == 1
    
    @patch('httpx.Client.post')
    def test_send_event_retry_on_network_error(self, mock_post):
        """Test retry logic on network errors."""
        mock_post.side_effect = httpx.NetworkError("Connection failed")
        
        emitter = SidecarEmitter(enable_retries=True, max_retries=2)
        app = AppRef(app_id=uuid4(), name='test-app', version='1.0')
        entity = EntityRef(type='job', id=uuid4(), parent_id=None, business_key='test', sub_key=None)
        event = JobEvent.now('started', 'fab1', app, entity, status='running')
        
        with pytest.raises(httpx.NetworkError):
            emitter.send(event)
        
        # Should have retried
        assert mock_post.call_count >= 2
    
    @patch('httpx.Client.post')
    def test_send_batch(self, mock_post):
        """Test sending batch of events."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        emitter = SidecarEmitter(enable_retries=False)
        app = AppRef(app_id=uuid4(), name='test-app', version='1.0')
        
        events = [
            JobEvent.now('started', 'fab1', app, 
                        EntityRef(type='job', id=uuid4(), parent_id=None, business_key=f'job{i}', sub_key=None),
                        status='running')
            for i in range(5)
        ]
        
        emitter.send_batch(events)
        
        assert mock_post.called
        call_args = mock_post.call_args
        assert len(call_args[1]['json']) == 5
    
    def test_context_manager(self):
        """Test emitter as context manager."""
        with SidecarEmitter() as emitter:
            assert emitter is not None
        
        # Should close cleanly
        assert True

