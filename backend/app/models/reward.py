from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Reward(Base):
    """The disbursal ledger (CLAUDE.md invariant #4, place #2).

    `completion_key` is what makes a row "which completion this is": a
    constant (`"once"`) for `period=one_time` challenges, or the ISO week
    (`"2026-W27"`) for `period=weekly` ones, so a new week is a fresh
    completion. The unique constraint below is the actual at-most-once
    guarantee — disbursal is an insert-or-ignore against it, not an
    application-level "check then insert" (see `app/services/rewards.py`).
    """

    __tablename__ = "rewards"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_challenge_id",
            "completion_key",
            name="uq_rewards_user_challenge_completion",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    reward_type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    source_challenge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("challenges.id"), nullable=False, index=True
    )
    completion_key: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
