"""Provisioning script for a fresh checkout: one admin user + a handful of
sample challenges covering every axis the engine supports (`count`/`streak`
type, `one_time`/`weekly` period), so a reviewer can go from `docker compose
up` to a disbursed reward without hand-writing any JSON.

Run after `alembic upgrade head` (this script never touches the schema
itself — that's Alembic's job, not a seed script's):

    python -m app.scripts.seed

Idempotent, safe to re-run: the admin user is upserted by email (created if
absent, promoted to `admin` if it exists as a plain user — this is the
"out-of-band DB write" Phase 1 anticipated for admin promotion); challenges
are matched by `name` and skipped if already present. That's a script-level
check, not a DB constraint (`challenges.name` isn't unique) — good enough
for a provisioning script that isn't a concurrent write path.
"""

from __future__ import annotations

import asyncio
import os

from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.core.security import hash_password
from app.models.challenge import Challenge, ChallengePeriod, ChallengeStatus
from app.models.user import User, UserRole

ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe123!")

SAMPLE_CHALLENGES: list[dict[str, object]] = [
    {
        "name": "First Comment",
        "description": "Post your first comment on any thread.",
        "type": "count",
        "event_type": "comment_posted",
        "rule_config": {"target": 1},
        "reward": {"type": "points", "amount": 10},
        "status": ChallengeStatus.active.value,
        "period": ChallengePeriod.one_time.value,
    },
    {
        "name": "Conversation Starter",
        "description": "Post 3 comments across any threads.",
        "type": "count",
        "event_type": "comment_posted",
        "rule_config": {"target": 3},
        "reward": {"type": "points", "amount": 50},
        "status": ChallengeStatus.active.value,
        "period": ChallengePeriod.one_time.value,
    },
    {
        "name": "Weekly Commenter",
        "description": "Post 5 comments before the week resets Monday.",
        "type": "count",
        "event_type": "comment_posted",
        "rule_config": {"target": 5},
        "reward": {"type": "points", "amount": 30},
        "status": ChallengeStatus.active.value,
        "period": ChallengePeriod.weekly.value,
    },
    {
        "name": "5-Day Streak",
        "description": "Create a post on 5 consecutive days.",
        "type": "streak",
        "event_type": "post_created",
        "rule_config": {"length": 5},
        "reward": {"type": "points", "amount": 200},
        "status": ChallengeStatus.active.value,
        "period": ChallengePeriod.one_time.value,
    },
    {
        "name": "Solution Finder",
        "description": "Mark a comment as the solution on one of your posts.",
        "type": "count",
        "event_type": "solution_marked",
        "rule_config": {"target": 1},
        "reward": {"type": "badge", "amount": 1},
        "status": ChallengeStatus.active.value,
        "period": ChallengePeriod.one_time.value,
    },
]


async def seed() -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        admin = await db.scalar(select(User).where(User.email == ADMIN_EMAIL))
        if admin is None:
            admin = User(
                email=ADMIN_EMAIL,
                password_hash=hash_password(ADMIN_PASSWORD),
                role=UserRole.admin.value,
            )
            db.add(admin)
            print(f"created admin user {ADMIN_EMAIL!r} (password: {ADMIN_PASSWORD!r})")
        elif admin.role != UserRole.admin.value:
            admin.role = UserRole.admin.value
            print(f"promoted existing user {ADMIN_EMAIL!r} to admin")
        else:
            print(f"admin user {ADMIN_EMAIL!r} already exists, skipping")

        for spec in SAMPLE_CHALLENGES:
            name = spec["name"]
            existing = await db.scalar(select(Challenge).where(Challenge.name == name))
            if existing is not None:
                print(f"challenge {name!r} already exists, skipping")
                continue
            db.add(Challenge(**spec))
            print(f"created challenge {name!r}")

        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
