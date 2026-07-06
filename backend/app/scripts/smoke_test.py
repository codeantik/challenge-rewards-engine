"""Production sanity check — exercises a deployed API over the wire (no DB
access, no app imports beyond stdlib/httpx) so it can be pointed at Render,
a preview URL, or localhost equally.

    python -m app.scripts.smoke_test --api-base https://challenge-rewards-api.onrender.com/api

Registers a throwaway user (fresh UUID email, never collides), then checks
the invariants CLAUDE.md actually promises: envelope shapes, 202+idempotent
event ingestion, the rate limiter, and the async worker path. Business-logic
outcomes that depend on which challenges happen to be seeded (progress,
rewards) are reported, not asserted — this script doesn't know what's been
seeded into the target environment.

Exits non-zero if any hard check fails.
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid
from dataclasses import dataclass, field

import httpx


@dataclass
class Results:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    def ok(self, name: str) -> None:
        print(f"  PASS  {name}")
        self.passed.append(name)

    def bad(self, name: str, detail: str) -> None:
        print(f"  FAIL  {name} — {detail}")
        self.failed.append(name)


def wait_for_health(client: httpx.Client, results: Results, timeout: float) -> None:
    print("\n[1] backend health (tolerating Render free-tier cold start)")
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            resp = client.get("/health", timeout=15)
            if resp.status_code == 200 and "data" in resp.json():
                results.ok(f"GET /health -> 200 ({resp.json()['data']})")
                return
            last_error = f"status={resp.status_code} body={resp.text[:200]}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        time.sleep(3)
    results.bad("GET /health", f"never returned within {timeout:.0f}s ({last_error})")


def register(client: httpx.Client, results: Results) -> tuple[str, str] | None:
    print("\n[2] register + login")
    email = f"smoke-{uuid.uuid4()}@example.com"
    password = "SmokeTest123!"
    resp = client.post("/auth/register", json={"email": email, "password": password})
    if resp.status_code != 201:
        results.bad("POST /auth/register", f"status={resp.status_code} body={resp.text[:200]}")
        return None
    body = resp.json()
    token = body.get("data", {}).get("access_token")
    if not token:
        results.bad("POST /auth/register", f"no access_token in body: {body}")
        return None
    results.ok(f"POST /auth/register -> 201 ({email})")
    return email, token


def check_me(client: httpx.Client, results: Results, token: str, email: str) -> None:
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    if resp.status_code == 200 and resp.json().get("data", {}).get("email") == email:
        results.ok("GET /auth/me -> matches registered email")
    else:
        results.bad("GET /auth/me", f"status={resp.status_code} body={resp.text[:200]}")


def check_error_envelope(client: httpx.Client, results: Results) -> None:
    print("\n[3] error envelope shape (CLAUDE.md contract)")
    resp = client.post("/auth/register", json={"email": "not-an-email"})
    is_json = resp.headers.get("content-type", "").startswith("application/json")
    body = resp.json() if is_json else {}
    error = body.get("error", {})
    has_request_id = "x-request-id" in {k.lower() for k in resp.headers}
    if resp.status_code == 422 and error.get("code") and error.get("message") and has_request_id:
        results.ok(f"POST /auth/register (bad email) -> 422 error envelope, code={error['code']}")
    else:
        results.bad(
            "error envelope",
            f"status={resp.status_code} body={body} request_id_header={has_request_id}",
        )


def create_post(client: httpx.Client, results: Results, token: str) -> str | None:
    print("\n[4] event-emitting mutation (post_created)")
    resp = client.post(
        "/posts",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "sanity check", "body": "produced by smoke_test.py"},
    )
    if resp.status_code != 201:
        results.bad("POST /posts", f"status={resp.status_code} body={resp.text[:200]}")
        return None
    post_id: str = resp.json()["data"]["id"]
    results.ok(f"POST /posts -> 201 (id={post_id})")
    return post_id


def check_idempotent_event(client: httpx.Client, results: Results, token: str) -> None:
    print("\n[5] event ingestion idempotency (CLAUDE.md invariant #4)")
    event_id = str(uuid.uuid4())
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"event_id": event_id, "event_type": "smoke_test", "payload": {"n": 1}}

    first = client.post("/events", headers=headers, json=payload)
    second = client.post("/events", headers=headers, json={**payload, "payload": {"n": 999}})

    if first.status_code != 202 or second.status_code != 202:
        results.bad(
            "POST /events (idempotent replay)",
            f"status1={first.status_code} status2={second.status_code}",
        )
        return
    if first.json() == second.json():
        results.ok("POST /events twice with same event_id -> identical stored response")
    else:
        results.bad(
            "POST /events (idempotent replay)",
            f"bodies differ: {first.json()} != {second.json()}",
        )


def snapshot_progress(client: httpx.Client, token: str) -> tuple[object, object]:
    headers = {"Authorization": f"Bearer {token}"}
    progress = client.get("/users/me/progress", headers=headers)
    rewards = client.get("/users/me/rewards", headers=headers)
    return progress.json().get("data"), rewards.json().get("data")


def check_progress_endpoints(client: httpx.Client, results: Results, token: str) -> None:
    print(
        "\n[6] progress/rewards endpoints (structural only — content depends on seeded challenges)"
    )
    progress, rewards = snapshot_progress(client, token)
    if isinstance(progress, list) and isinstance(rewards, list):
        results.ok(
            "GET /users/me/progress + /users/me/rewards -> 200 "
            f"(progress={len(progress)}, rewards={len(rewards)})"
        )
    else:
        results.bad(
            "progress/rewards", f"unexpected shapes: progress={progress!r} rewards={rewards!r}"
        )


def check_worker_drain(client: httpx.Client, token: str, wait_seconds: float) -> None:
    print(
        f"\n[info] snapshotting progress, waiting up to {wait_seconds:.0f}s for the GitHub "
        "Actions worker to drain the job created above (runs every 5 min, or trigger it "
        "manually: gh workflow run drain-worker.yml)"
    )
    before = snapshot_progress(client, token)
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        time.sleep(15)
        after = snapshot_progress(client, token)
        if after != before:
            print(f"  progress changed after drain:\n    before={before}\n    after={after}")
            return
    print("  no change observed in the wait window (expected if no challenge matches "
          "the smoke-test events, or if the worker hasn't run yet — not a failure)")


def check_rate_limit(client: httpx.Client, results: Results, token: str, capacity: int) -> None:
    print(
        f"\n[7] rate limiter (bursts >{capacity} requests/min against /events — "
        "run last, burns the bucket)"
    )
    headers = {"Authorization": f"Bearer {token}"}
    saw_429 = False
    error_envelope_ok = False
    for _ in range(capacity + 5):
        resp = client.post(
            "/events",
            headers=headers,
            json={"event_id": str(uuid.uuid4()), "event_type": "smoke_test_burst", "payload": {}},
        )
        if resp.status_code == 429:
            saw_429 = True
            body = resp.json()
            error_envelope_ok = bool(body.get("error", {}).get("code"))
            break
    if saw_429 and error_envelope_ok:
        results.ok("burst of events -> 429 with error envelope once capacity is exhausted")
    else:
        results.bad(
            "rate limiter", f"never saw a 429 with error envelope in {capacity + 5} requests"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-base", required=True, help="e.g. https://challenge-rewards-api.onrender.com/api"
    )
    parser.add_argument(
        "--health-timeout", type=float, default=90.0, help="seconds to tolerate cold start"
    )
    parser.add_argument(
        "--drain-wait", type=float, default=0.0, help="seconds to poll for worker drain (0=skip)"
    )
    parser.add_argument(
        "--skip-rate-limit", action="store_true", help="skip the rate-limit burst check"
    )
    parser.add_argument(
        "--rate-limit-capacity",
        type=int,
        default=20,
        help="must match EVENT_RATE_LIMIT_CAPACITY",
    )
    args = parser.parse_args()

    results = Results()
    with httpx.Client(base_url=args.api_base, timeout=30) as client:
        wait_for_health(client, results, args.health_timeout)
        if not results.failed:
            auth = register(client, results)
            if auth:
                email, token = auth
                check_me(client, results, token, email)
                check_error_envelope(client, results)
                create_post(client, results, token)
                check_idempotent_event(client, results, token)
                check_progress_endpoints(client, results, token)
                if args.drain_wait > 0:
                    check_worker_drain(client, token, args.drain_wait)
                if not args.skip_rate_limit:
                    check_rate_limit(client, results, token, args.rate_limit_capacity)

    print(f"\n{len(results.passed)} passed, {len(results.failed)} failed")
    return 1 if results.failed else 0


if __name__ == "__main__":
    sys.exit(main())
