from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Literal
from uuid import UUID, uuid4
from datetime import datetime, timezone

EventKind = Literal['started','progress','metric','finished','error','canceled']
EntityType = Literal['job','subjob']

@dataclass(frozen=True)
class AppRef:
    app_id: UUID
    name: str
    version: str

@dataclass(frozen=True)
class EntityRef:
    type: EntityType
    id: UUID
    parent_id: Optional[UUID]
    business_key: Optional[str]
    sub_key: Optional[str]

@dataclass(frozen=True)
class EventPayload:
    kind: EventKind
    at: datetime
    metrics: Dict[str, float]
    status: str
    metadata: Dict[str, object]

@dataclass(frozen=True)
class JobEvent:
    idempotency_key: UUID
    site_id: str
    app: AppRef
    entity: EntityRef
    event: EventPayload

    @staticmethod
    def now(kind: EventKind, site_id: str, app: AppRef, entity: EntityRef, status: str,
            metrics: Optional[Dict[str, float]] = None, metadata: Optional[Dict[str, object]] = None,
            idem: Optional[UUID] = None) -> 'JobEvent':
        return JobEvent(
            idempotency_key=idem or uuid4(), site_id=site_id, app=app, entity=entity,
            event=EventPayload(
                kind=kind, at=datetime.now(timezone.utc),
                metrics=metrics or {}, status=status, metadata=metadata or {}
            )
        )

    def to_json(self) -> Dict[str, object]:
        def enc(v):
            if isinstance(v, UUID): return str(v)
            if isinstance(v, datetime): return v.isoformat()
            return v
        return {
            "idempotency_key": enc(self.idempotency_key),
            "site_id": self.site_id,
            "app": {"app_id": enc(self.app.app_id), "name": self.app.name, "version": self.app.version},
            "entity": {
                "type": self.entity.type, "id": enc(self.entity.id),
                "parent_id": enc(self.entity.parent_id) if self.entity.parent_id else None,
                "business_key": self.entity.business_key, "sub_key": self.entity.sub_key
            },
            "event": {
                "kind": self.event.kind, "at": enc(self.event.at),
                "metrics": self.event.metrics, "status": self.event.status,
                "metadata": self.event.metadata
            }
        }
