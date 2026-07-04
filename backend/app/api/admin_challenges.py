"""Admin challenge config CRUD (CLAUDE.md invariant #3 — Phase 4).

These routes only ever write `challenges` rows; they never touch progress
or rewards directly. Evaluation is entirely the worker's job, driven by
whatever `status`/`rule_config` an admin leaves here.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import AdminUser
from app.core.db import DbSession
from app.core.errors import AppError
from app.core.responses import Envelope
from app.models.challenge import Challenge, ChallengeStatus
from app.schemas.challenges import (
    ChallengeCreate,
    ChallengeOut,
    ChallengeUpdate,
    validate_challenge_config,
)

router = APIRouter(prefix="/admin/challenges", tags=["admin-challenges"])


def _not_found() -> AppError:
    return AppError("NOT_FOUND", "challenge not found", status_code=404)


@router.post("", response_model=Envelope[ChallengeOut], status_code=201)
async def create_challenge(
    body: ChallengeCreate, _admin: AdminUser, db: DbSession
) -> Envelope[ChallengeOut]:
    challenge = Challenge(
        name=body.name,
        description=body.description,
        type=body.type,
        event_type=body.event_type,
        rule_config=body.rule_config,
        reward=body.reward.model_dump(),
        status=body.status,
        start_at=body.start_at,
        end_at=body.end_at,
    )
    db.add(challenge)
    await db.commit()
    await db.refresh(challenge)
    return Envelope(data=ChallengeOut.model_validate(challenge))


@router.get("", response_model=Envelope[list[ChallengeOut]])
async def list_challenges(_admin: AdminUser, db: DbSession) -> Envelope[list[ChallengeOut]]:
    stmt = select(Challenge).order_by(Challenge.created_at.desc())
    challenges = (await db.scalars(stmt)).all()
    return Envelope(data=[ChallengeOut.model_validate(c) for c in challenges])


@router.get("/{challenge_id}", response_model=Envelope[ChallengeOut])
async def get_challenge(
    challenge_id: uuid.UUID, _admin: AdminUser, db: DbSession
) -> Envelope[ChallengeOut]:
    challenge = await db.get(Challenge, challenge_id)
    if challenge is None:
        raise _not_found()
    return Envelope(data=ChallengeOut.model_validate(challenge))


@router.patch("/{challenge_id}", response_model=Envelope[ChallengeOut])
async def update_challenge(
    challenge_id: uuid.UUID, body: ChallengeUpdate, _admin: AdminUser, db: DbSession
) -> Envelope[ChallengeOut]:
    challenge = await db.get(Challenge, challenge_id)
    if challenge is None:
        raise _not_found()

    updates = body.model_dump(exclude_unset=True)
    reward = updates.pop("reward", None)

    # `type` and `rule_config` are only meaningfully valid together — if the
    # caller touched either, re-validate the merged (post-update) values
    # *before* mutating the tracked entity, so a rejected PATCH never leaves
    # a half-applied change sitting in the session.
    if "type" in updates or "rule_config" in updates:
        merged_type = updates.get("type", challenge.type)
        merged_rule_config = updates.get("rule_config", challenge.rule_config)
        try:
            validate_challenge_config(merged_type, merged_rule_config)
        except ValueError as exc:
            raise AppError("VALIDATION_ERROR", str(exc), status_code=422) from exc

    for field, value in updates.items():
        setattr(challenge, field, value)
    if reward is not None:
        challenge.reward = reward

    await db.commit()
    await db.refresh(challenge)
    return Envelope(data=ChallengeOut.model_validate(challenge))


@router.delete("/{challenge_id}", response_model=Envelope[ChallengeOut])
async def archive_challenge(
    challenge_id: uuid.UUID, _admin: AdminUser, db: DbSession
) -> Envelope[ChallengeOut]:
    """"Delete" archives rather than removing the row — progress/reward
    rows may already reference this challenge, and the lifecycle
    (draft -> active -> expired -> archived) treats archival as terminal
    state, not erasure.
    """
    challenge = await db.get(Challenge, challenge_id)
    if challenge is None:
        raise _not_found()

    challenge.status = ChallengeStatus.archived.value
    await db.commit()
    await db.refresh(challenge)
    return Envelope(data=ChallengeOut.model_validate(challenge))
