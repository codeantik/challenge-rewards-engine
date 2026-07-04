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
from app.core.config import get_settings
from app.core.db import DbSession
from app.core.rate_limit import TokenBucketRateLimiter
from app.core.responses import Envelope
from app.schemas.events import EventIn, EventOut
from app.services.events import ingest_event

router = APIRouter(prefix="/events", tags=["events"])

_settings = get_settings()
_rate_limiter = TokenBucketRateLimiter(
    capacity=_settings.event_rate_limit_capacity,
    refill_seconds=_settings.event_rate_limit_window_seconds,
)


@router.post("", response_model=Envelope[EventOut], status_code=202)
async def create_event(body: EventIn, user: CurrentUser, db: DbSession) -> Envelope[EventOut]:
    # Checked per-user, before touching the DB, so a client hammering this
    # endpoint pays no query cost beyond the auth lookup already required.
    # Applies to replays too (invariant #4's idempotent re-submission still
    # spends a token) — simpler to reason about than special-casing replays,
    # and a well-behaved retrier isn't going to be anywhere near the limit.
    _rate_limiter.check(user.id)

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
