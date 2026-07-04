from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.db import DbSession
from app.core.errors import AppError
from app.core.responses import Envelope
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Envelope[TokenOut], status_code=201)
async def register(body: RegisterRequest, db: DbSession) -> Envelope[TokenOut]:
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise AppError("CONFLICT", "email already registered", status_code=409)

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        role=UserRole.user.value,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    return Envelope(data=TokenOut(access_token=token, user=UserOut.model_validate(user)))


@router.post("/login", response_model=Envelope[TokenOut])
async def login(body: LoginRequest, db: DbSession) -> Envelope[TokenOut]:
    user = await db.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise AppError("UNAUTHORIZED", "invalid email or password", status_code=401)

    token = create_access_token(user.id)
    return Envelope(data=TokenOut(access_token=token, user=UserOut.model_validate(user)))


@router.get("/me", response_model=Envelope[UserOut])
async def me(user: CurrentUser) -> Envelope[UserOut]:
    return Envelope(data=UserOut.model_validate(user))
