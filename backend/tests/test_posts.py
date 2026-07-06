from __future__ import annotations

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.models.event import Event

PASSWORD = "correct-horse-battery"


async def _register_and_login(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    login = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    token = login.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _events_of_type(event_type: str) -> list[Event]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        rows = await session.scalars(select(Event).where(Event.event_type == event_type))
        return list(rows.all())


async def test_create_post_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/api/posts", json={"title": "t", "body": "b"})
    assert response.status_code == 401


async def test_create_post_writes_post_and_event(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "author@example.com")
    response = await client.post(
        "/api/posts", json={"title": "Hello", "body": "World"}, headers=headers
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["title"] == "Hello"
    assert data["comment_count"] == 0
    assert data["view_count"] == 0
    assert data["solution_comment_id"] is None

    events = await _events_of_type("post_created")
    assert len(events) == 1
    assert events[0].payload["post_id"] == data["id"]


async def test_create_post_rejects_blank_title(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "blank@example.com")
    response = await client.post(
        "/api/posts", json={"title": "", "body": "World"}, headers=headers
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_list_posts_latest_orders_newest_first(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "lister@example.com")
    first = await client.post(
        "/api/posts", json={"title": "first", "body": "b"}, headers=headers
    )
    second = await client.post(
        "/api/posts", json={"title": "second", "body": "b"}, headers=headers
    )

    response = await client.get("/api/posts?sort=latest", headers=headers)
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    ids = [p["id"] for p in body["data"]]
    assert ids[0] == second.json()["data"]["id"]
    assert ids[1] == first.json()["data"]["id"]
    assert body["meta"]["total"] == 2
    assert body["meta"]["page"] == 1


async def test_list_posts_trending_favors_more_comments(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "trend@example.com")
    quiet = await client.post(
        "/api/posts", json={"title": "quiet", "body": "b"}, headers=headers
    )
    popular = await client.post(
        "/api/posts", json={"title": "popular", "body": "b"}, headers=headers
    )
    popular_id = popular.json()["data"]["id"]
    for _ in range(3):
        await client.post(
            f"/api/posts/{popular_id}/comments", json={"body": "nice"}, headers=headers
        )

    response = await client.get("/api/posts?sort=trending", headers=headers)
    ids = [p["id"] for p in response.json()["data"]]
    assert ids.index(popular_id) < ids.index(quiet.json()["data"]["id"])


async def test_get_post_not_found(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "missing@example.com")
    response = await client.get(
        "/api/posts/00000000-0000-0000-0000-000000000000", headers=headers
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_get_post_increments_view_count_and_emits_event(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "viewer@example.com")
    created = await client.post(
        "/api/posts", json={"title": "viewed", "body": "b"}, headers=headers
    )
    post_id = created.json()["data"]["id"]

    response = await client.get(f"/api/posts/{post_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["view_count"] == 1
    assert data["comments"] == []

    events = await _events_of_type("post_viewed")
    assert len(events) == 1


async def test_create_comment_updates_count_and_nests_in_detail(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "commenter@example.com")
    created = await client.post(
        "/api/posts", json={"title": "with comments", "body": "b"}, headers=headers
    )
    post_id = created.json()["data"]["id"]

    comment_response = await client.post(
        f"/api/posts/{post_id}/comments", json={"body": "first!"}, headers=headers
    )
    assert comment_response.status_code == 201, comment_response.text
    comment_id = comment_response.json()["data"]["id"]

    detail = await client.get(f"/api/posts/{post_id}", headers=headers)
    detail_data = detail.json()["data"]
    assert detail_data["comment_count"] == 1
    assert [c["id"] for c in detail_data["comments"]] == [comment_id]

    events = await _events_of_type("comment_posted")
    assert len(events) == 1
    assert events[0].payload["comment_id"] == comment_id


async def test_create_comment_on_missing_post_404s(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "ghost@example.com")
    response = await client.post(
        "/api/posts/00000000-0000-0000-0000-000000000000/comments",
        json={"body": "x"},
        headers=headers,
    )
    assert response.status_code == 404


async def test_mark_solution_owner_only(client: AsyncClient) -> None:
    owner_headers = await _register_and_login(client, "owner@example.com")
    other_headers = await _register_and_login(client, "other@example.com")

    created = await client.post(
        "/api/posts", json={"title": "q", "body": "b"}, headers=owner_headers
    )
    post_id = created.json()["data"]["id"]
    comment = await client.post(
        f"/api/posts/{post_id}/comments", json={"body": "the answer"}, headers=other_headers
    )
    comment_id = comment.json()["data"]["id"]

    forbidden = await client.patch(
        f"/api/posts/{post_id}/solution/{comment_id}",
        headers=other_headers,
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"

    ok = await client.patch(
        f"/api/posts/{post_id}/solution/{comment_id}",
        headers=owner_headers,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["solution_comment_id"] == comment_id

    events = await _events_of_type("solution_marked")
    assert len(events) == 1


async def test_mark_solution_rejects_comment_from_another_post(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "cross@example.com")
    post_a = await client.post(
        "/api/posts", json={"title": "a", "body": "b"}, headers=headers
    )
    post_b = await client.post(
        "/api/posts", json={"title": "b", "body": "b"}, headers=headers
    )
    post_a_id = post_a.json()["data"]["id"]
    post_b_id = post_b.json()["data"]["id"]

    comment_on_b = await client.post(
        f"/api/posts/{post_b_id}/comments", json={"body": "x"}, headers=headers
    )
    comment_on_b_id = comment_on_b.json()["data"]["id"]

    response = await client.patch(
        f"/api/posts/{post_a_id}/solution/{comment_on_b_id}",
        headers=headers,
    )
    assert response.status_code == 404
