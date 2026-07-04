from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventIn(BaseModel):
    """Client-generated `event_id` is the idempotency key (CLAUDE.md
    invariant #4, place #1): resubmitting the same one replays the stored
    original response rather than reprocessing, whatever `event_type`/
    `payload` the resubmission carries.
    """

    event_id: uuid.UUID
    event_type: str = Field(min_length=1, max_length=50)
    payload: dict[str, Any] = Field(default_factory=dict)


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    event_type: str
    payload: dict[str, Any]
    created_at: datetime
