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


class RewardTypeSummary(BaseModel):
    reward_type: str
    total_amount: int
    count: int
    latest_at: datetime


class RewardsSummaryOut(BaseModel):
    """Server-computed aggregate over the full ledger (not just one page).

    `"points"` is the conventional reward_type (see
    `app/services/rewards.py::disburse_reward`'s default) and is surfaced as
    a single balance; every other `reward_type` an admin configured on a
    challenge's `reward` JSONB is treated as a badge and grouped/counted
    separately.
    """

    total_points: int
    badges: list[RewardTypeSummary]
