"""Unit tests for Monitored context manager."""
import pytest
from uuid import uuid4
import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'apps' / 'monitoring_sdk'))

from monitoring_sdk.context import Monitored
from monitoring_sdk.models import AppRef


class DummyEmitter:
    """Dummy emitter for testing."""
    
    def __init__(self):
        self.sent = []
    
    def send(self, ev):
        self.sent.append(ev)


class TestMonitored:
    """Test suite for Monitored context manager."""
    
    def test_monitored_success(self):
        """Test successful job execution."""
        app = AppRef(app_id=uuid4(), name='test-app', version='1.0')
        emitter = DummyEmitter()
        
        with Monitored(
            site_id='fab1',
            app=app,
            entity_type='job',
            business_key='test-job',
            emitter=emitter,
            enable_logging=False
        ) as ctx:
            time.sleep(0.1)  # Simulate work
        
        assert len(emitter.sent) >= 2
        kinds = [e.event.kind for e in emitter.sent]
        assert kinds[0] == 'started'
        assert kinds[-1] == 'finished'
        assert emitter.sent[-1].event.status == 'succeeded'
    
    def test_monitored_failure(self):
        """Test job execution with exception."""
        app = AppRef(app_id=uuid4(), name='test-app', version='1.0')
        emitter = DummyEmitter()
        
        with pytest.raises(ValueError):
            with Monitored(
                site_id='fab1',
                app=app,
                entity_type='job',
                emitter=emitter,
                enable_logging=False
            ):
                raise ValueError("Test error")
        
        assert len(emitter.sent) >= 2
        assert emitter.sent[-1].event.status == 'failed'
        assert 'error' in emitter.sent[-1].event.metadata
        assert emitter.sent[-1].event.metadata['error'] == 'Test error'
    
    def test_monitored_metrics_collection(self):
        """Test that metrics are collected."""
        app = AppRef(app_id=uuid4(), name='test-app', version='1.0')
        emitter = DummyEmitter()
        
        with Monitored(
            site_id='fab1',
            app=app,
            entity_type='job',
            emitter=emitter,
            enable_logging=False
        ):
            # Do some work to generate metrics
            data = [i**2 for i in range(1000)]
            time.sleep(0.05)
        
        finish_event = emitter.sent[-1]
        assert 'duration_s' in finish_event.event.metrics
        assert finish_event.event.metrics['duration_s'] > 0
        assert 'mem_max_mb' in finish_event.event.metrics
        assert finish_event.event.metrics['mem_max_mb'] > 0
    
    def test_monitored_tick(self):
        """Test progress tick functionality."""
        app = AppRef(app_id=uuid4(), name='test-app', version='1.0')
        emitter = DummyEmitter()
        
        with Monitored(
            site_id='fab1',
            app=app,
            entity_type='job',
            emitter=emitter,
            enable_logging=False
        ) as ctx:
            ctx.tick(extra_meta={'step': 1})
            time.sleep(0.05)
            ctx.tick(extra_meta={'step': 2})
        
        # Should have: started + 2 ticks + finished
        assert len(emitter.sent) >= 4
        progress_events = [e for e in emitter.sent if e.event.kind == 'progress']
        assert len(progress_events) == 2
        assert progress_events[0].event.metadata['step'] == 1
        assert progress_events[1].event.metadata['step'] == 2
    
    def test_monitored_subjob(self):
        """Test subjob monitoring."""
        app = AppRef(app_id=uuid4(), name='test-app', version='1.0')
        parent_id = uuid4()
        emitter = DummyEmitter()
        
        with Monitored(
            site_id='fab1',
            app=app,
            entity_type='subjob',
            parent_id=parent_id,
            sub_key='sub-1',
            emitter=emitter,
            enable_logging=False
        ):
            pass
        
        assert len(emitter.sent) >= 2
        assert emitter.sent[0].entity.type == 'subjob'
        assert emitter.sent[0].entity.parent_id == parent_id
        assert emitter.sent[0].entity.sub_key == 'sub-1'
    
    def test_monitored_metadata(self):
        """Test custom metadata."""
        app = AppRef(app_id=uuid4(), name='test-app', version='1.0')
        emitter = DummyEmitter()
        
        metadata = {'batch_id': '12345', 'priority': 'high'}
        
        with Monitored(
            site_id='fab1',
            app=app,
            entity_type='job',
            metadata=metadata,
            emitter=emitter,
            enable_logging=False
        ):
            pass
        
        start_event = emitter.sent[0]
        assert start_event.event.metadata['batch_id'] == '12345'
        assert start_event.event.metadata['priority'] == 'high'

