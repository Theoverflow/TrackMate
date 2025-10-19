from uuid import uuid4
import sys
from pathlib import Path

# Add monitoring_sdk to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'apps' / 'monitoring_sdk'))

from monitoring_sdk.context import Monitored
from monitoring_sdk.models import AppRef

class DummyEmitter:
    def __init__(self): self.sent = []
    def send(self, ev): self.sent.append(ev)

def test_monitored_success(monkeypatch):
    app = AppRef(app_id=uuid4(), name='test-app', version='1')
    emitter = DummyEmitter()
    with Monitored(site_id='fab', app=app, entity_type='job', emitter=emitter, enable_logging=False):
        pass
    assert len(emitter.sent) >= 2
    kinds = [e.event.kind for e in emitter.sent]
    assert kinds[0] == 'started' and kinds[-1] == 'finished'
