from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from httpx import AsyncClient
from sqlalchemy import update

from app.api.deps import AdminUser
from app.core.db import get_sessionmaker
from app.main import app
from app.models.user import User, UserRole

# `require_admin` has no product route to exercise yet in Phase 1 (admin CRUD
# lands in Phase 4) — this route exists purely so the dependency itself can
# be tested end-to-end through the real app (real JWT, real DB role lookup).
_probe_router = APIRouter()


@_probe_router.get("/auth/_admin_probe")
async def _admin_probe(user: AdminUser) -> dict[str, bool]:
    return {"ok": True}


app.include_router(_probe_router, prefix="/api")

PASSWORD = "correct-horse-battery"


async def _register(client: AsyncClient, email: str, password: str = PASSWORD) -> dict[str, Any]:
    response = await client.post("/api/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()["data"]
    return body


async def _promote_to_admin(email: str) -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(
            update(User).where(User.email == email).values(role=UserRole.admin.value)
        )
        await session.commit()


async def test_register_returns_token_and_user(client: AsyncClient) -> None:
    body = await _register(client, "alice@example.com")
    assert body["user"]["email"] == "alice@example.com"
    assert body["user"]["role"] == "user"
    assert body["access_token"]


async def test_register_normalizes_email_case(client: AsyncClient) -> None:
    body = await _register(client, "Mixed.Case@Example.com")
    assert body["user"]["email"] == "mixed.case@example.com"


async def test_register_duplicate_email_conflicts(client: AsyncClient) -> None:
    await _register(client, "bob@example.com")
    response = await client.post(
        "/api/auth/register", json={"email": "bob@example.com", "password": PASSWORD}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


async def test_register_rejects_short_password(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register", json={"email": "short@example.com", "password": "short"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_login_then_me(client: AsyncClient) -> None:
    await _register(client, "carol@example.com")
    login_response = await client.post(
        "/api/auth/login", json={"email": "carol@example.com", "password": PASSWORD}
    )
    assert login_response.status_code == 200
    token = login_response.json()["data"]["access_token"]

    me_response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["data"]["email"] == "carol@example.com"


async def test_login_wrong_password_rejected(client: AsyncClient) -> None:
    await _register(client, "dave@example.com")
    response = await client.post(
        "/api/auth/login", json={"email": "dave@example.com", "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_login_unknown_email_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )
    assert response.status_code == 401


async def test_me_without_token_rejected(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_me_with_garbage_token_rejected(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert response.status_code == 401


async def test_admin_probe_rejects_user_accepts_admin(client: AsyncClient) -> None:
    user_body = await _register(client, "user-role@example.com")
    await _register(client, "admin-role@example.com")
    await _promote_to_admin("admin-role@example.com")

    admin_login = await client.post(
        "/api/auth/login", json={"email": "admin-role@example.com", "password": PASSWORD}
    )
    admin_token = admin_login.json()["data"]["access_token"]

    user_resp = await client.get(
        "/api/auth/_admin_probe",
        headers={"Authorization": f"Bearer {user_body['access_token']}"},
    )
    admin_resp = await client.get(
        "/api/auth/_admin_probe", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert user_resp.status_code == 403
    assert user_resp.json()["error"]["code"] == "FORBIDDEN"
    assert admin_resp.status_code == 200
    assert admin_resp.json() == {"ok": True}
