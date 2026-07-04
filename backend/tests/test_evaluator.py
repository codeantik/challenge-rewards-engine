"""The Phase 4 vertical slice (plan.md): emit an event -> worker evaluates
-> a progress row moves. Also covers the streak strategy and the
recompute-based idempotency that lets a job safely run twice.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.models.challenge import Challenge, ChallengeStatus
from app.models.event import Event
from app.models.progress import Progress
from app.services.evaluator import evaluate_event
from app.worker import claim_and_process_one

PASSWORD = "correct-horse-battery"


async def _register_and_login(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    login = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    token = login.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_challenge(**kwargs: object) -> Challenge:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        challenge = Challenge(**kwargs)
        session.add(challenge)
        await session.commit()
        await session.refresh(challenge)
        return challenge


async def _get_progress(user_id: uuid.UUID, challenge_id: uuid.UUID) -> Progress | None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        stmt = select(Progress).where(
            Progress.user_id == user_id, Progress.challenge_id == challenge_id
        )
        return (await session.scalars(stmt)).first()


async def test_count_challenge_progress_moves_via_worker(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "slicer@example.com")
    me = await client.get("/api/auth/me", headers=headers)
    user_id = uuid.UUID(me.json()["data"]["id"])

    challenge = await _create_challenge(
        name="Comment 3 times",
        description="",
        type="count",
        event_type="comment_posted",
        rule_config={"target": 3},
        reward={"type": "points", "amount": 50},
        status=ChallengeStatus.active.value,
    )

    sessionmaker = get_sessionmaker()

    for i in range(3):
        response = await client.post(
            "/api/events",
            json={
                "event_id": str(uuid.uuid4()),
                "event_type": "comment_posted",
                "payload": {},
            },
            headers=headers,
        )
        assert response.status_code == 202, response.text

        async with sessionmaker() as db:
            claimed = await claim_and_process_one(db)
        assert claimed is True

        progress = await _get_progress(user_id, challenge.id)
        assert progress is not None
        assert progress.current_value == i + 1
        assert progress.target_value == 3
        assert progress.is_complete is (i + 1 >= 3)


async def test_worker_ignores_challenges_for_other_event_types(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "unrelated@example.com")
    me = await client.get("/api/auth/me", headers=headers)
    user_id = uuid.UUID(me.json()["data"]["id"])

    challenge = await _create_challenge(
        name="Post 1 time",
        description="",
        type="count",
        event_type="post_created",
        rule_config={"target": 1},
        reward={"type": "points", "amount": 10},
        status=ChallengeStatus.active.value,
    )

    sessionmaker = get_sessionmaker()
    response = await client.post(
        "/api/events",
        json={"event_id": str(uuid.uuid4()), "event_type": "comment_posted", "payload": {}},
        headers=headers,
    )
    assert response.status_code == 202

    async with sessionmaker() as db:
        assert await claim_and_process_one(db) is True

    assert await _get_progress(user_id, challenge.id) is None


async def test_draft_challenge_is_not_evaluated(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "draftwatcher@example.com")
    me = await client.get("/api/auth/me", headers=headers)
    user_id = uuid.UUID(me.json()["data"]["id"])

    challenge = await _create_challenge(
        name="Draft challenge",
        description="",
        type="count",
        event_type="comment_posted",
        rule_config={"target": 1},
        reward={"type": "points", "amount": 10},
        status=ChallengeStatus.draft.value,
    )

    sessionmaker = get_sessionmaker()
    response = await client.post(
        "/api/events",
        json={"event_id": str(uuid.uuid4()), "event_type": "comment_posted", "payload": {}},
        headers=headers,
    )
    assert response.status_code == 202

    async with sessionmaker() as db:
        assert await claim_and_process_one(db) is True

    assert await _get_progress(user_id, challenge.id) is None


async def test_evaluate_event_is_idempotent_when_run_twice(client: AsyncClient) -> None:
    """Simulates a worker crash after `evaluate_event` succeeds but before
    the job is marked `done` — the retry re-runs `evaluate_event` for the
    same event. Progress must land in the same place either way (CLAUDE.md
    invariant #5), because the strategy recomputes from source events
    rather than incrementing a counter.
    """
    headers = await _register_and_login(client, "retrier@example.com")
    me = await client.get("/api/auth/me", headers=headers)
    user_id = uuid.UUID(me.json()["data"]["id"])

    challenge = await _create_challenge(
        name="Comment once",
        description="",
        type="count",
        event_type="comment_posted",
        rule_config={"target": 1},
        reward={"type": "points", "amount": 10},
        status=ChallengeStatus.active.value,
    )

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        event = Event(event_type="comment_posted", user_id=user_id, payload={})
        db.add(event)
        await db.commit()
        await db.refresh(event)

        await evaluate_event(db, event)
        await db.commit()
        await evaluate_event(db, event)
        await db.commit()

    progress = await _get_progress(user_id, challenge.id)
    assert progress is not None
    assert progress.current_value == 1
    assert progress.is_complete is True


async def test_streak_challenge_completes_on_consecutive_days(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "streaker@example.com")
    me = await client.get("/api/auth/me", headers=headers)
    user_id = uuid.UUID(me.json()["data"]["id"])

    challenge = await _create_challenge(
        name="3-day streak",
        description="",
        type="streak",
        event_type="post_created",
        rule_config={"length": 3},
        reward={"type": "points", "amount": 100},
        status=ChallengeStatus.active.value,
    )

    today = datetime.now(UTC).date()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        last_event = None
        for offset in (2, 1, 0):
            day = today - timedelta(days=offset)
            ts = datetime.combine(day, datetime.min.time(), tzinfo=UTC) + timedelta(
                hours=10
            )
            event = Event(event_type="post_created", user_id=user_id, payload={}, created_at=ts)
            db.add(event)
            last_event = event
        await db.commit()
        assert last_event is not None
        await db.refresh(last_event)

        await evaluate_event(db, last_event)
        await db.commit()

    progress = await _get_progress(user_id, challenge.id)
    assert progress is not None
    assert progress.current_value == 3
    assert progress.target_value == 3
    assert progress.is_complete is True
