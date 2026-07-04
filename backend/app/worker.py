"""The durable evaluation worker (CLAUDE.md invariant #5).

Deliberately *not* `FastAPI BackgroundTasks`: that runs in-process with no
durability (a crash between `202` and evaluation loses the work), no
retries, and breaks the moment there's more than one worker. This is a
plain Postgres-backed poll loop instead — `jobs` rows were enqueued in the
same transaction as their `Event` insert (`app/services/events.py`), so a
job never exists without its event or vice versa.

`claim_and_process_one` does the actual `SELECT ... FOR UPDATE SKIP LOCKED`
claim: multiple worker processes can poll the same table concurrently
without grabbing the same row, and a crash mid-processing just leaves the
row `processing` forever rather than corrupting anything (a stuck-row
reaper is a reasonable follow-up, not implemented here).

Delivery is at-least-once (a job can be retried after a failure); combined
with `evaluate_event`'s recompute-from-source-events idempotency, the
*effective* semantics are exactly-once.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sessionmaker
from app.models.event import Event
from app.models.job import Job, JobStatus
from app.services.evaluator import evaluate_event

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
POLL_INTERVAL_SECONDS = 1.0


async def claim_and_process_one(db: AsyncSession) -> bool:
    """Claim and process a single pending job inside `db`'s transaction.
    Returns `False` if no pending job was available (caller should back off
    before polling again); `True` either way once a job was claimed,
    regardless of whether it succeeded.
    """
    stmt = (
        select(Job)
        .where(Job.status == JobStatus.pending.value)
        .order_by(Job.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = (await db.scalars(stmt)).first()
    if job is None:
        return False

    job.status = JobStatus.processing.value
    await db.flush()

    event = await db.get(Event, job.event_id)
    if event is None:
        # The FK on jobs.event_id guarantees this can't happen outside a
        # corrupted DB — fail loudly rather than silently dropping the job.
        job.status = JobStatus.failed.value
        job.last_error = "referenced event no longer exists"
        await db.commit()
        return True

    try:
        await evaluate_event(db, event)
    except Exception as exc:
        job.attempts += 1
        job.last_error = str(exc)[:2000]
        job.status = (
            JobStatus.failed.value if job.attempts >= MAX_ATTEMPTS else JobStatus.pending.value
        )
        await db.commit()
        logger.warning("job %s failed (attempt %d): %s", job.id, job.attempts, exc)
        return True

    job.status = JobStatus.done.value
    await db.commit()
    return True


async def run_forever(poll_interval: float = POLL_INTERVAL_SECONDS) -> None:
    sessionmaker = get_sessionmaker()
    while True:
        async with sessionmaker() as db:
            claimed = await claim_and_process_one(db)
        if not claimed:
            await asyncio.sleep(poll_interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())
