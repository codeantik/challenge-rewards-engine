from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ChallengeStatus(enum.StrEnum):
    draft = "draft"
    active = "active"
    expired = "expired"
    archived = "archived"


class Challenge(Base):
    """A data-driven challenge config (CLAUDE.md invariant #3).

    `type` is the only field the evaluator ever switches on, and it does so
    through exactly one place — the strategy registry in
    `app/services/strategies.py` — never with `if type == ...` in domain
    logic. `rule_config` is the opaque, per-type payload that strategy
    interprets (`{"target": N}` for `count`, `{"length": N}` for `streak`);
    it's JSONB rather than fixed columns because a count challenge and a
    streak challenge don't share a column set, and forcing one would mean
    nullable sprawl or a table per type.
    """

    __tablename__ = "challenges"
    __table_args__ = (
        CheckConstraint(
            "status in ('draft', 'active', 'expired', 'archived')", name="ck_challenges_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    rule_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    reward: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ChallengeStatus.draft.value, index=True
    )
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
