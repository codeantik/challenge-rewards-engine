"""Forum domain: posts, comments, mark-solution.

Every mutation here writes its own domain row *and* calls `ingest_event`
in the same session before `commit()` — same DB transaction, one road in
(CLAUDE.md invariant #2). These handlers never touch the evaluator; they
only ever produce events.
"""

from __future__ import annotations

import uuid
from math import ceil

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser
from app.core.db import DbSession
from app.core.errors import AppError
from app.core.responses import Envelope
from app.models.comment import Comment
from app.models.post import Post
from app.schemas.posts import (
    CommentCreate,
    CommentOut,
    MarkSolutionRequest,
    PostCreate,
    PostDetailOut,
    PostOut,
    SortOption,
)
from app.services.events import ingest_event

router = APIRouter(prefix="/posts", tags=["posts"])


def _not_found(resource: str) -> AppError:
    return AppError("NOT_FOUND", f"{resource} not found", status_code=404)


@router.post("", response_model=Envelope[PostOut], status_code=201)
async def create_post(body: PostCreate, user: CurrentUser, db: DbSession) -> Envelope[PostOut]:
    post = Post(author_id=user.id, title=body.title, body=body.body)
    db.add(post)
    await db.flush()

    await ingest_event(
        db, event_type="post_created", user_id=user.id, payload={"post_id": str(post.id)}
    )

    await db.commit()
    await db.refresh(post)
    return Envelope(data=PostOut.model_validate(post))


@router.get("", response_model=Envelope[list[PostOut]])
async def list_posts(
    db: DbSession,
    sort: SortOption = "latest",
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> Envelope[list[PostOut]]:
    total_count = await db.scalar(select(func.count()).select_from(Post))
    total: int = total_count or 0

    stmt = select(Post)
    if sort == "trending":
        # Trending formula (see explain.md): comments are weighted 3x views
        # as the stronger engagement signal, decayed by age in hours. The
        # `+ 2` offset keeps a brand-new post's score finite instead of
        # dividing by ~0, so it doesn't spike to the top on a single view.
        age_hours = func.extract("epoch", func.now() - Post.created_at) / 3600.0
        score = (Post.comment_count * 3 + Post.view_count) / func.power(age_hours + 2, 1.5)
        stmt = stmt.order_by(score.desc())
    else:
        stmt = stmt.order_by(Post.created_at.desc())

    stmt = stmt.offset((page - 1) * limit).limit(limit)
    posts = (await db.scalars(stmt)).all()

    total_pages = ceil(total / limit) if total else 0
    return Envelope(
        data=[PostOut.model_validate(p) for p in posts],
        meta={"page": page, "limit": limit, "total": total, "total_pages": total_pages},
    )


@router.get("/{post_id}", response_model=Envelope[PostDetailOut])
async def get_post(
    post_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> Envelope[PostDetailOut]:
    post = await db.get(Post, post_id)
    if post is None:
        raise _not_found("post")

    post.view_count += 1
    await ingest_event(
        db, event_type="post_viewed", user_id=user.id, payload={"post_id": str(post.id)}
    )
    await db.commit()
    await db.refresh(post)

    comments_stmt = (
        select(Comment).where(Comment.post_id == post_id).order_by(Comment.created_at.asc())
    )
    comments = (await db.scalars(comments_stmt)).all()

    return Envelope(
        data=PostDetailOut(
            **PostOut.model_validate(post).model_dump(),
            comments=[CommentOut.model_validate(c) for c in comments],
        )
    )


@router.post("/{post_id}/comments", response_model=Envelope[CommentOut], status_code=201)
async def create_comment(
    post_id: uuid.UUID, body: CommentCreate, user: CurrentUser, db: DbSession
) -> Envelope[CommentOut]:
    post = await db.get(Post, post_id)
    if post is None:
        raise _not_found("post")

    comment = Comment(post_id=post_id, author_id=user.id, body=body.body)
    db.add(comment)
    post.comment_count += 1
    await db.flush()

    await ingest_event(
        db,
        event_type="comment_posted",
        user_id=user.id,
        payload={"post_id": str(post_id), "comment_id": str(comment.id)},
    )

    await db.commit()
    await db.refresh(comment)
    return Envelope(data=CommentOut.model_validate(comment))


@router.post("/{post_id}/solution", response_model=Envelope[PostOut])
async def mark_solution(
    post_id: uuid.UUID, body: MarkSolutionRequest, user: CurrentUser, db: DbSession
) -> Envelope[PostOut]:
    post = await db.get(Post, post_id)
    if post is None:
        raise _not_found("post")
    if post.author_id != user.id:
        raise AppError("FORBIDDEN", "only the post owner can mark a solution", status_code=403)

    comment = await db.get(Comment, body.comment_id)
    if comment is None or comment.post_id != post_id:
        raise _not_found("comment")

    post.solution_comment_id = comment.id
    await ingest_event(
        db,
        event_type="solution_marked",
        user_id=user.id,
        payload={"post_id": str(post_id), "comment_id": str(comment.id)},
    )

    await db.commit()
    await db.refresh(post)
    return Envelope(data=PostOut.model_validate(post))
