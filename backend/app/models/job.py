from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class JobStatus(enum.StrEnum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class Job(Base):
    """The outbox row enqueued in the *same transaction* as its event insert
    (CLAUDE.md invariant #5). One job per event, never re-enqueued on an
    event-id replay. Phase 4's worker polls this table with
    `SELECT ... FOR UPDATE SKIP LOCKED`, evaluates, and marks it `done` or
    `failed` (with `attempts`/`last_error` driving retry/backoff).
    """

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status in ('pending', 'processing', 'done', 'failed')", name="ck_jobs_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.event_id"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=JobStatus.pending.value
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
