from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from app.main import app

# A bare `Exception` is handled by Starlette's `ServerErrorMiddleware`, which
# sits *outside* `CORSMiddleware` in the stack built by `app/main.py` — so
# without `_cors_headers_for_unhandled_exception` (app/core/errors.py), an
# unhandled 500 would carry no CORS headers and the browser would report an
# opaque "CORS policy" failure instead of the real error. This route exists
# purely to force that path deterministically.
_boom_router = APIRouter()


@_boom_router.get("/_test/boom")
async def _boom() -> None:
    raise RuntimeError("deliberate failure for the CORS regression test")


app.include_router(_boom_router, prefix="/api")


@pytest.fixture
async def raising_client() -> AsyncGenerator[AsyncClient, None]:
    """The shared `client` fixture's `ASGITransport` defaults to
    `raise_app_exceptions=True`, which re-raises an unhandled exception
    straight into the test process instead of letting `ServerErrorMiddleware`
    turn it into the real HTTP response a live server would send — which is
    exactly the response this test needs to inspect. `raise_app_exceptions=False`
    here makes the transport behave like a real deployment for this one case.
    """
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_unhandled_exception_still_carries_cors_headers_for_allowed_origin(
    raising_client: AsyncClient,
) -> None:
    response = await raising_client.get(
        "/api/_test/boom", headers={"Origin": "http://localhost:3000"}
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"


async def test_unhandled_exception_omits_cors_headers_for_disallowed_origin(
    raising_client: AsyncClient,
) -> None:
    response = await raising_client.get(
        "/api/_test/boom", headers={"Origin": "https://not-allowed.example.com"}
    )

    assert response.status_code == 500
    assert "access-control-allow-origin" not in response.headers
