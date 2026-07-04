"""`POST /api/events` — the engine's public front door (CLAUDE.md invariant
#2). Any authenticated producer can emit an event here; it converges on the
exact same `ingest_event` that forum handlers call in-process. There is no
second way to create an event row.

Ingestion never evaluates on the request path (invariant #5) — the response
is `202 Accepted` the moment the event (and its job) are durably stored, new
or replayed alike.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.core.db import DbSession
from app.core.responses import Envelope
from app.schemas.events import EventIn, EventOut
from app.services.events import ingest_event

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=Envelope[EventOut], status_code=202)
async def create_event(body: EventIn, user: CurrentUser, db: DbSession) -> Envelope[EventOut]:
    event, _is_new = await ingest_event(
        db,
        event_type=body.event_type,
        user_id=user.id,
        payload=body.payload,
        event_id=body.event_id,
    )
    await db.commit()
    await db.refresh(event)
    return Envelope(data=EventOut.model_validate(event))
