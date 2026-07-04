"""Tests the worker's claim/retry mechanics directly (CLAUDE.md invariant
#5): `SELECT ... FOR UPDATE SKIP LOCKED` claiming, and retry-then-fail on
a broken job.
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.models.challenge import Challenge, ChallengeStatus
from app.models.event import Event
from app.models.job import Job, JobStatus
from app.models.user import User
from app.worker import MAX_ATTEMPTS, claim_and_process_one


async def _seed_pending_job(email: str) -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        user = User(email=email, password_hash="x")
        session.add(user)
        await session.flush()
        event = Event(event_type="comment_posted", user_id=user.id, payload={})
        session.add(event)
        await session.flush()
        session.add(Job(event_id=event.event_id))
        await session.commit()


async def test_worker_claims_one_job_then_finds_queue_empty() -> None:
    await _seed_pending_job("workeruser@example.com")
    sessionmaker = get_sessionmaker()

    async with sessionmaker() as db:
        assert await claim_and_process_one(db) is True

    async with sessionmaker() as session:
        jobs = (await session.scalars(select(Job))).all()
        assert len(jobs) == 1
        assert jobs[0].status == JobStatus.done.value

    async with sessionmaker() as db:
        assert await claim_and_process_one(db) is False


async def test_worker_retries_then_permanently_fails_a_broken_job() -> None:
    await _seed_pending_job("brokenuser@example.com")

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        challenge = Challenge(
            name="Broken",
            description="",
            # Bypasses the admin schema's registry validation on purpose,
            # to simulate a strategy-lookup failure the worker must retry.
            type="does-not-exist-in-registry",
            event_type="comment_posted",
            rule_config={},
            reward={"type": "points", "amount": 1},
            status=ChallengeStatus.active.value,
        )
        session.add(challenge)
        await session.commit()

    for attempt in range(1, MAX_ATTEMPTS + 1):
        async with sessionmaker() as db:
            assert await claim_and_process_one(db) is True

        async with sessionmaker() as session:
            job = (await session.scalars(select(Job))).first()
            assert job is not None
            assert job.attempts == attempt
            expected_status = (
                JobStatus.pending.value if attempt < MAX_ATTEMPTS else JobStatus.failed.value
            )
            assert job.status == expected_status
            assert job.last_error is not None
