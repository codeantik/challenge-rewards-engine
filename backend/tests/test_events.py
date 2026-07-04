from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.models.event import Event
from app.models.job import Job

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


async def _jobs_for_event(event_id: uuid.UUID) -> list[Job]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        rows = await session.scalars(select(Job).where(Job.event_id == event_id))
        return list(rows.all())


async def test_create_event_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/events",
        json={"event_id": str(uuid.uuid4()), "event_type": "custom_event", "payload": {}},
    )
    assert response.status_code == 401


async def test_create_event_returns_202_and_enqueues_one_job(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "producer@example.com")
    event_id = str(uuid.uuid4())

    response = await client.post(
        "/api/events",
        json={"event_id": event_id, "event_type": "custom_event", "payload": {"x": 1}},
        headers=headers,
    )
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["event_id"] == event_id
    assert data["event_type"] == "custom_event"
    assert data["payload"] == {"x": 1}

    events = await _events_of_type("custom_event")
    assert len(events) == 1

    jobs = await _jobs_for_event(uuid.UUID(event_id))
    assert len(jobs) == 1
    assert jobs[0].status == "pending"


async def test_resubmitting_same_event_id_replays_stored_response(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "retrier@example.com")
    event_id = str(uuid.uuid4())
    body = {"event_id": event_id, "event_type": "custom_event", "payload": {"x": 1}}

    first = await client.post("/api/events", json=body, headers=headers)
    # Resubmission carries different payload/type on purpose — the stored
    # original must win, not this one.
    second = await client.post(
        "/api/events",
        json={"event_id": event_id, "event_type": "different_type", "payload": {"x": 999}},
        headers=headers,
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json() == second.json()

    events = await _events_of_type("custom_event")
    assert len(events) == 1
    assert await _events_of_type("different_type") == []

    jobs = await _jobs_for_event(uuid.UUID(event_id))
    assert len(jobs) == 1


async def test_create_event_rejects_bad_body(client: AsyncClient) -> None:
    headers = await _register_and_login(client, "badbody@example.com")
    response = await client.post(
        "/api/events",
        json={"event_id": "not-a-uuid", "event_type": "custom_event", "payload": {}},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
