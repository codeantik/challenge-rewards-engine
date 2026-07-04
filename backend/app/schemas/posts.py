from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SortOption = Literal["latest", "trending"]


class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10_000)


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author_id: uuid.UUID
    title: str
    body: str
    comment_count: int
    view_count: int
    solution_comment_id: uuid.UUID | None
    created_at: datetime


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5_000)


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    post_id: uuid.UUID
    author_id: uuid.UUID
    body: str
    created_at: datetime


class PostDetailOut(PostOut):
    comments: list[CommentOut]


class MarkSolutionRequest(BaseModel):
    comment_id: uuid.UUID
