from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProgressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    challenge_id: uuid.UUID
    current_value: int
    target_value: int
    is_complete: bool
    completed_at: datetime | None
    updated_at: datetime


class StreakOut(BaseModel):
    """Recomputed straight from source events (see
    `app/services/strategies.py::compute_user_streak`) — `best_streak`
    isn't stored anywhere, unlike `current`/`target`, which the `progress`
    cache already carries for completion purposes.
    """

    challenge_id: uuid.UUID
    name: str
    current_streak: int
    best_streak: int
    target_length: int
