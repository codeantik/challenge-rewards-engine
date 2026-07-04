from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Progress(Base):
    """A materialized cache of `ChallengeStrategy.evaluate(...)`'s output for
    one `(user, challenge)` pair — not an incrementing counter.

    The evaluator recomputes `current_value`/`is_complete` from the raw
    `events` table on every run and upserts this row wholesale. That's what
    makes re-running a job for the same event safe (CLAUDE.md invariant #5):
    there's no "add 1" step to accidentally double, just "recompute and
    overwrite" from a source of truth that itself doesn't change on replay.
    """

    __tablename__ = "progress"
    __table_args__ = (
        UniqueConstraint("user_id", "challenge_id", name="uq_progress_user_challenge"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("challenges.id"), nullable=False, index=True
    )

    current_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
