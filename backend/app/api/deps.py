"""Auth dependencies: `get_current_user` resolves the bearer token to a DB
row (so a revoked/changed account is caught immediately); `require_admin`
layers a role check on top for admin-only routes.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.db import DbSession
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.models.user import User, UserRole

_bearer_scheme = HTTPBearer(auto_error=False)
_Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)]


async def get_current_user(credentials: _Credentials, db: DbSession) -> User:
    if credentials is None:
        raise AppError("UNAUTHORIZED", "missing bearer token", status_code=401)

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise AppError("UNAUTHORIZED", "invalid or expired token", status_code=401) from exc

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AppError("UNAUTHORIZED", "invalid token payload", status_code=401) from exc

    user = await db.get(User, user_id)
    if user is None:
        raise AppError("UNAUTHORIZED", "user no longer exists", status_code=401)

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role != UserRole.admin.value:
        raise AppError("FORBIDDEN", "admin role required", status_code=403)
    return user


AdminUser = Annotated[User, Depends(require_admin)]
