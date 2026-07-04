"""`/users/me/*` read endpoints (Phase 5): progress, streaks, and the
paginated reward ledger. Auth-scoped to the caller only — there is no
"view another user's progress" route.
"""

from __future__ import annotations

from math import ceil

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser
from app.core.db import DbSession
from app.core.responses import Envelope
from app.models.challenge import Challenge, ChallengeStatus
from app.models.progress import Progress
from app.models.reward import Reward
from app.schemas.progress import ProgressOut, StreakOut
from app.schemas.rewards import RewardOut, RewardsSummaryOut, RewardTypeSummary
from app.services.strategies import STREAK_CHALLENGE_TYPES, compute_user_streak

router = APIRouter(prefix="/users/me", tags=["users"])


@router.get("/progress", response_model=Envelope[list[ProgressOut]])
async def get_my_progress(user: CurrentUser, db: DbSession) -> Envelope[list[ProgressOut]]:
    stmt = (
        select(Progress)
        .where(Progress.user_id == user.id)
        .order_by(Progress.updated_at.desc())
    )
    rows = (await db.scalars(stmt)).all()
    return Envelope(data=[ProgressOut.model_validate(p) for p in rows])


@router.get("/streaks", response_model=Envelope[list[StreakOut]])
async def get_my_streaks(user: CurrentUser, db: DbSession) -> Envelope[list[StreakOut]]:
    stmt = select(Challenge).where(
        Challenge.type.in_(STREAK_CHALLENGE_TYPES),
        Challenge.status == ChallengeStatus.active.value,
    )
    challenges = (await db.scalars(stmt)).all()

    out: list[StreakOut] = []
    for challenge in challenges:
        current, best = await compute_user_streak(db, user_id=user.id, challenge=challenge)
        length = challenge.rule_config.get("length", 0)
        out.append(
            StreakOut(
                challenge_id=challenge.id,
                name=challenge.name,
                current_streak=current,
                best_streak=best,
                target_length=length,
            )
        )
    return Envelope(data=out)


@router.get("/rewards", response_model=Envelope[list[RewardOut]])
async def get_my_rewards(
    user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> Envelope[list[RewardOut]]:
    total_count = await db.scalar(
        select(func.count()).select_from(Reward).where(Reward.user_id == user.id)
    )
    total: int = total_count or 0

    stmt = (
        select(Reward)
        .where(Reward.user_id == user.id)
        .order_by(Reward.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = (await db.scalars(stmt)).all()

    total_pages = ceil(total / limit) if total else 0
    return Envelope(
        data=[RewardOut.model_validate(r) for r in rows],
        meta={"page": page, "limit": limit, "total": total, "total_pages": total_pages},
    )


@router.get("/rewards/summary", response_model=Envelope[RewardsSummaryOut])
async def get_my_rewards_summary(
    user: CurrentUser, db: DbSession
) -> Envelope[RewardsSummaryOut]:
    stmt = (
        select(
            Reward.reward_type,
            func.sum(Reward.amount).label("total_amount"),
            func.count().label("count"),
            func.max(Reward.created_at).label("latest_at"),
        )
        .where(Reward.user_id == user.id)
        .group_by(Reward.reward_type)
    )
    rows = (await db.execute(stmt)).all()

    total_points = 0
    badges: list[RewardTypeSummary] = []
    for reward_type, total_amount, count, latest_at in rows:
        if reward_type == "points":
            total_points = total_amount
            continue
        badges.append(
            RewardTypeSummary(
                reward_type=reward_type,
                total_amount=total_amount,
                count=count,
                latest_at=latest_at,
            )
        )
    return Envelope(data=RewardsSummaryOut(total_points=total_points, badges=badges))
