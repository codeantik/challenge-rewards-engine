"""Read endpoints joining `challenges` with the caller's own `progress`
(Phase 5). Never writes — evaluation and disbursal happen exclusively in
the worker (`app/services/evaluator.py`); these routes only ever `SELECT`.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.db import DbSession
from app.core.responses import Envelope
from app.models.challenge import Challenge, ChallengePeriod, ChallengeStatus
from app.models.progress import Progress
from app.schemas.challenges import ChallengeOut, ChallengeWithProgressOut
from app.schemas.progress import ProgressOut

router = APIRouter(prefix="/challenges", tags=["challenges"])


async def _active_challenges_with_progress(
    db: DbSession, user: CurrentUser, *, period: str | None = None
) -> list[ChallengeWithProgressOut]:
    stmt = (
        select(Challenge, Progress)
        .outerjoin(
            Progress,
            (Progress.challenge_id == Challenge.id) & (Progress.user_id == user.id),
        )
        .where(Challenge.status == ChallengeStatus.active.value)
    )
    if period is not None:
        stmt = stmt.where(Challenge.period == period)
    stmt = stmt.order_by(Challenge.created_at.desc())

    rows = (await db.execute(stmt)).all()
    return [
        ChallengeWithProgressOut(
            **ChallengeOut.model_validate(challenge).model_dump(),
            progress=ProgressOut.model_validate(progress) if progress is not None else None,
        )
        for challenge, progress in rows
    ]


@router.get("", response_model=Envelope[list[ChallengeWithProgressOut]])
async def list_active_challenges(
    user: CurrentUser, db: DbSession
) -> Envelope[list[ChallengeWithProgressOut]]:
    return Envelope(data=await _active_challenges_with_progress(db, user))


@router.get("/weekly", response_model=Envelope[list[ChallengeWithProgressOut]])
async def list_weekly_challenges(
    user: CurrentUser, db: DbSession
) -> Envelope[list[ChallengeWithProgressOut]]:
    return Envelope(
        data=await _active_challenges_with_progress(
            db, user, period=ChallengePeriod.weekly.value
        )
    )
