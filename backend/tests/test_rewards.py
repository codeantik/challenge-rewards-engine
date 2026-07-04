"""Phase 5: reward disbursal, the two idempotency guards working together,
and the read endpoints (`/challenges`, `/challenges/weekly`, `/users/me/*`).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.models.challenge import Challenge, ChallengeStatus
from app.models.event import Event
from app.models.reward import Reward
from app.services.evaluator import evaluate_event
from app.services.rewards import completion_key

PASSWORD = "correct-horse-battery"
UTC_TZ = ZoneInfo("UTC")


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


async def _rewards_for(user_id: uuid.UUID) -> list[Reward]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        stmt = select(Reward).where(Reward.user_id == user_id)
        return list((await session.scalars(stmt)).all())


def test_completion_key_is_constant_for_one_time_challenges() -> None:
    challenge = Challenge(
        name="one-shot", type="count", event_type="comment_posted",
        rule_config={"target": 1}, reward={"type": "points", "amount": 1},
        status=ChallengeStatus.active.value, period="one_time",
    )
    key_now = completion_key(challenge, now=datetime(2026, 6, 20, tzinfo=UTC), tz=UTC_TZ)
    key_later = completion_key(challenge, now=datetime(2026, 7, 10, tzinfo=UTC), tz=UTC_TZ)
    assert key_now == key_later == "once"


def test_completion_key_rolls_over_by_iso_week_for_weekly_challenges() -> None:
    challenge = Challenge(
        name="weekly", type="count", event_type="comment_posted",
        rule_config={"target": 1}, reward={"type": "points", "amount": 1},
        status=ChallengeStatus.active.value, period="weekly",
    )
    # 2026-06-22 is a Monday (week 26); 2026-06-29 is the following Monday (week 27).
    week_one = completion_key(challenge, now=datetime(2026, 6, 24, tzinfo=UTC), tz=UTC_TZ)
    week_two = completion_key(challenge, now=datetime(2026, 6, 30, tzinfo=UTC), tz=UTC_TZ)
    assert week_one == "2026-W26"
    assert week_two == "2026-W27"
    assert week_one != week_two


async def test_completing_challenge_disburses_reward_exactly_once_when_evaluated_twice(
    client: AsyncClient,
) -> None:
    """Mirrors `test_evaluate_event_is_idempotent_when_run_twice` in
    test_evaluator.py, but asserts the *reward* ledger side (invariant #4,
    place #2) rather than progress: a crash-and-retry that re-runs
    `evaluate_event` for the same event must still land exactly one row.
    """
    headers = await _register_and_login(client, "rewarded@example.com")
    me = await client.get("/api/auth/me", headers=headers)
    user_id = uuid.UUID(me.json()["data"]["id"])

    await _create_challenge(
        name="Comment once", description="", type="count", event_type="comment_posted",
        rule_config={"target": 1}, reward={"type": "points", "amount": 25},
        status=ChallengeStatus.active.value, period="one_time",
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

    rewards = await _rewards_for(user_id)
    assert len(rewards) == 1
    assert rewards[0].amount == 25
    assert rewards[0].reward_type == "points"
    assert rewards[0].completion_key == "once"


async def test_get_my_rewards_is_paginated(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "ledger@example.com")
    me = await client.get("/api/auth/me", headers=headers)
    user_id = uuid.UUID(me.json()["data"]["id"])

    for i in range(3):
        await _create_challenge(
            name=f"Challenge {i}", description="", type="count", event_type=f"evt_{i}",
            rule_config={"target": 1}, reward={"type": "points", "amount": 10},
            status=ChallengeStatus.active.value, period="one_time",
        )

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        for i in range(3):
            event = Event(event_type=f"evt_{i}", user_id=user_id, payload={})
            db.add(event)
            await db.commit()
            await db.refresh(event)
            await evaluate_event(db, event)
            await db.commit()

    response = await client.get("/api/users/me/rewards", params={"limit": 2}, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["data"]) == 2
    assert body["meta"] == {"page": 1, "limit": 2, "total": 3, "total_pages": 2}


async def test_get_active_challenges_includes_progress(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "progressreader@example.com")
    me = await client.get("/api/auth/me", headers=headers)
    user_id = uuid.UUID(me.json()["data"]["id"])

    challenge = await _create_challenge(
        name="Comment 3 times", description="", type="count", event_type="comment_posted",
        rule_config={"target": 3}, reward={"type": "points", "amount": 5},
        status=ChallengeStatus.active.value, period="one_time",
    )

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        event = Event(event_type="comment_posted", user_id=user_id, payload={})
        db.add(event)
        await db.commit()
        await db.refresh(event)
        await evaluate_event(db, event)
        await db.commit()

    response = await client.get("/api/challenges", headers=headers)
    assert response.status_code == 200, response.text
    entries = {c["id"]: c for c in response.json()["data"]}
    assert entries[str(challenge.id)]["progress"] == {
        "challenge_id": str(challenge.id),
        "current_value": 1,
        "target_value": 3,
        "is_complete": False,
        "completed_at": None,
        "updated_at": entries[str(challenge.id)]["progress"]["updated_at"],
    }


async def test_weekly_endpoint_filters_by_period(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "weeklyreader@example.com")

    one_time = await _create_challenge(
        name="One-time", description="", type="count", event_type="comment_posted",
        rule_config={"target": 1}, reward={"type": "points", "amount": 5},
        status=ChallengeStatus.active.value, period="one_time",
    )
    weekly = await _create_challenge(
        name="Weekly", description="", type="count", event_type="comment_posted",
        rule_config={"target": 1}, reward={"type": "points", "amount": 5},
        status=ChallengeStatus.active.value, period="weekly",
    )

    response = await client.get("/api/challenges/weekly", headers=headers)
    assert response.status_code == 200, response.text
    ids = {c["id"] for c in response.json()["data"]}
    assert str(weekly.id) in ids
    assert str(one_time.id) not in ids


async def test_get_my_streaks_reports_current_and_best(client: AsyncClient) -> None:
    from datetime import timedelta

    headers = await _register_and_login(client, "streakreader@example.com")
    me = await client.get("/api/auth/me", headers=headers)
    user_id = uuid.UUID(me.json()["data"]["id"])

    challenge = await _create_challenge(
        name="3-day streak", description="", type="streak", event_type="post_created",
        rule_config={"length": 5}, reward={"type": "points", "amount": 100},
        status=ChallengeStatus.active.value, period="one_time",
    )

    today = datetime.now(UTC).date()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        for offset in (1, 0):
            day = today - timedelta(days=offset)
            ts = datetime.combine(day, datetime.min.time(), tzinfo=UTC) + timedelta(hours=10)
            db.add(Event(event_type="post_created", user_id=user_id, payload={}, created_at=ts))
        await db.commit()

    response = await client.get("/api/users/me/streaks", headers=headers)
    assert response.status_code == 200, response.text
    entries = {s["challenge_id"]: s for s in response.json()["data"]}
    entry = entries[str(challenge.id)]
    assert entry["current_streak"] == 2
    assert entry["best_streak"] == 2
    assert entry["target_length"] == 5
