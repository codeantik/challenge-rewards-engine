from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RewardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reward_type: str
    amount: int
    source_challenge_id: uuid.UUID
    completion_key: str
    created_at: datetime
