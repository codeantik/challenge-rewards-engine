from __future__ import annotations

from typing import Any

from httpx import AsyncClient
from sqlalchemy import update

from app.core.db import get_sessionmaker
from app.models.user import User, UserRole

PASSWORD = "correct-horse-battery"


async def _register_and_login(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    login = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    token = login.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _promote_to_admin(email: str) -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(
            update(User).where(User.email == email).values(role=UserRole.admin.value)
        )
        await session.commit()


async def _admin_headers(client: AsyncClient, email: str) -> dict[str, str]:
    headers = await _register_and_login(client, email)
    await _promote_to_admin(email)
    # role is re-read from the DB on every request (see explain.md Phase 1),
    # so promotion takes effect on this same token without a re-login.
    return headers


def _count_challenge_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": "Comment 3 times",
        "description": "Post three comments",
        "type": "count",
        "event_type": "comment_posted",
        "rule_config": {"target": 3},
        "reward": {"type": "points", "amount": 50},
        "status": "active",
    }
    body.update(overrides)
    return body


async def test_create_challenge_requires_admin(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "plain-user@example.com")
    response = await client.post(
        "/api/admin/challenges", json=_count_challenge_body(), headers=headers
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_create_challenge_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/api/admin/challenges", json=_count_challenge_body())
    assert response.status_code == 401


async def test_admin_creates_and_reads_challenge(client: AsyncClient) -> None:
    headers = await _admin_headers(client, "admin1@example.com")
    create_resp = await client.post(
        "/api/admin/challenges", json=_count_challenge_body(), headers=headers
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()["data"]
    assert created["type"] == "count"
    assert created["rule_config"] == {"target": 3}
    assert created["reward"] == {"type": "points", "amount": 50}
    assert created["status"] == "active"

    get_resp = await client.get(f"/api/admin/challenges/{created['id']}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["id"] == created["id"]

    list_resp = await client.get("/api/admin/challenges", headers=headers)
    assert list_resp.status_code == 200
    assert any(c["id"] == created["id"] for c in list_resp.json()["data"])


async def test_create_challenge_rejects_unknown_type(client: AsyncClient) -> None:
    headers = await _admin_headers(client, "admin2@example.com")
    response = await client.post(
        "/api/admin/challenges",
        json=_count_challenge_body(type="not-a-real-strategy"),
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_create_challenge_rejects_bad_rule_config_for_type(client: AsyncClient) -> None:
    headers = await _admin_headers(client, "admin3@example.com")
    response = await client.post(
        "/api/admin/challenges",
        json=_count_challenge_body(rule_config={"wrong_key": 1}),
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_patch_updates_fields(client: AsyncClient) -> None:
    headers = await _admin_headers(client, "admin4@example.com")
    created = (
        await client.post("/api/admin/challenges", json=_count_challenge_body(), headers=headers)
    ).json()["data"]

    patch_resp = await client.patch(
        f"/api/admin/challenges/{created['id']}",
        json={"rule_config": {"target": 5}},
        headers=headers,
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["data"]["rule_config"] == {"target": 5}


async def test_patch_rejects_rule_config_incompatible_with_current_type(
    client: AsyncClient,
) -> None:
    headers = await _admin_headers(client, "admin5@example.com")
    created = (
        await client.post("/api/admin/challenges", json=_count_challenge_body(), headers=headers)
    ).json()["data"]

    patch_resp = await client.patch(
        f"/api/admin/challenges/{created['id']}",
        json={"rule_config": {"length": 5}},  # streak-shaped config on a count challenge
        headers=headers,
    )
    assert patch_resp.status_code == 422
    assert patch_resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_delete_archives_rather_than_removes(client: AsyncClient) -> None:
    headers = await _admin_headers(client, "admin6@example.com")
    created = (
        await client.post("/api/admin/challenges", json=_count_challenge_body(), headers=headers)
    ).json()["data"]

    delete_resp = await client.delete(f"/api/admin/challenges/{created['id']}", headers=headers)
    assert delete_resp.status_code == 200
    assert delete_resp.json()["data"]["status"] == "archived"

    get_resp = await client.get(f"/api/admin/challenges/{created['id']}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["status"] == "archived"


async def test_get_unknown_challenge_404s(client: AsyncClient) -> None:
    import uuid

    headers = await _admin_headers(client, "admin7@example.com")
    response = await client.get(f"/api/admin/challenges/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
