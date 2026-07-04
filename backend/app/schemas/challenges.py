from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.progress import ProgressOut
from app.services.strategies import STRATEGIES

ChallengeStatusLiteral = Literal["draft", "active", "expired", "archived"]
ChallengePeriodLiteral = Literal["one_time", "weekly"]


class RewardConfig(BaseModel):
    """Generic reward shape consumed by Phase 5's disbursal — not switched
    on by the evaluator, so it isn't part of the strategy registry.
    """

    type: str = Field(min_length=1, max_length=50)
    amount: int = Field(gt=0)


def validate_challenge_config(type_: str, rule_config: dict[str, Any]) -> None:
    """Shared by `ChallengeCreate` and the admin PATCH handler (which merges
    a partial update onto the existing row before re-validating). Reads
    valid types from the registry itself rather than a hardcoded literal,
    so adding a strategy doesn't require touching this schema.
    """
    strategy = STRATEGIES.get(type_)
    if strategy is None:
        raise ValueError(f"unknown challenge type '{type_}'; must be one of {sorted(STRATEGIES)}")
    strategy.validate_config(rule_config)


class ChallengeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    type: str
    event_type: str = Field(min_length=1, max_length=50)
    rule_config: dict[str, Any] = Field(default_factory=dict)
    reward: RewardConfig
    status: ChallengeStatusLiteral = "draft"
    period: ChallengePeriodLiteral = "one_time"
    start_at: datetime | None = None
    end_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_rule_config(self) -> ChallengeCreate:
        try:
            validate_challenge_config(self.type, self.rule_config)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        return self


class ChallengeUpdate(BaseModel):
    """All fields optional (PATCH semantics). `type`/`rule_config` are
    re-validated together against whichever of the two the caller didn't
    touch — see `app/api/admin_challenges.py` for the merge.
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    type: str | None = None
    event_type: str | None = Field(default=None, min_length=1, max_length=50)
    rule_config: dict[str, Any] | None = None
    reward: RewardConfig | None = None
    status: ChallengeStatusLiteral | None = None
    period: ChallengePeriodLiteral | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None


class ChallengeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    type: str
    event_type: str
    rule_config: dict[str, Any]
    reward: dict[str, Any]
    status: str
    period: str
    start_at: datetime | None
    end_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ChallengeWithProgressOut(ChallengeOut):
    """`ChallengeOut` plus the caller's own progress on it — `None` when the
    user has never triggered a qualifying event, rather than a synthetic
    zeroed `ProgressOut` (there's no `progress` row until the worker writes
    one). Used by the `/challenges` and `/challenges/weekly` read endpoints.
    """

    progress: ProgressOut | None
