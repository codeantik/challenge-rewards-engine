# CLAUDE.md — invariants for this repo

This file is the contract every later phase must respect. If a change would violate one of these, stop and flag it rather than working around it silently.

## Architectural invariants

1. **The engine is decoupled from the forum.** The forum only ever *emits* events; it must never call the evaluator directly. The engine knows about events, challenges, progress, and rewards — nothing about posts or comments.
2. **All events enter through one path.** Forum mutation handlers and the public `POST /api/events` endpoint converge on the same ingestion function. There is no second way to create an event row.
3. **The evaluator is data-driven.** `challenge.type` may be switched on in exactly one place — a strategy registry (`STRATEGIES: dict[str, ChallengeStrategy]`). No `if type == ...` / `match type` in domain or business logic, ever. Adding a challenge type means adding one strategy, touching nothing else.
4. **Idempotency lives in two places:**
   - **Event ingestion** is idempotent on `event_id` (unique constraint). Re-submitting a seen `event_id` replays the *stored original response* rather than reprocessing.
   - **Reward disbursal** is at-most-once via a DB unique constraint on `(user_id, challenge_id, completion_key)`. The worker can run a job twice safely because of this.
5. **Evaluation is asynchronous and durable.** A Postgres-backed job/outbox table is enqueued in the *same transaction* as the event insert. A worker polls it with `SELECT ... FOR UPDATE SKIP LOCKED`, with retries on failure. `FastAPI BackgroundTasks` is never used for evaluation — it has no durability and breaks with more than one worker process. Ingestion returns `202 Accepted`; nothing evaluates on the request path.
6. **A single fixed forum timezone** (config constant, default `UTC`) drives both streak-day bucketing and the Monday weekly reset. No per-user timezone logic.
7. **Strict typing on both sides.** `mypy` clean on Python (no untyped defs, no implicit `Any` leaking across module boundaries). `strict: true` in `tsconfig.json`, no `any` abuse on the frontend.

## Event catalog

| event_type        | emitted by                          | meaning                                  |
|-------------------|--------------------------------------|-------------------------------------------|
| `post_created`    | `POST /posts`                        | a user created a forum post               |
| `post_viewed`     | `GET /posts/{id}` (detail view)      | a user viewed a post's detail page        |
| `comment_posted`  | `POST /posts/{id}/comments`          | a user commented on a post                |
| `solution_marked` | `POST /posts/{id}/solution`          | the post owner marked a comment as the solution |

Every event row carries at minimum: `event_id` (client-generated, unique), `event_type`, `user_id`, `payload` (JSONB), `created_at`.

## Response & error envelope

**Success** — every `2xx` JSON response body is shaped:

```jsonc
{
  "data": { /* the actual resource or result */ },
  "meta": { /* optional: pagination, etc. — omitted when not applicable */ }
}
```

**Error** — every non-2xx JSON response body is shaped:

```jsonc
{
  "error": {
    "code": "VALIDATION_ERROR",       // stable machine-readable string, UPPER_SNAKE_CASE
    "message": "email: not a valid email address",
    "details": [ { "loc": ["body", "email"], "msg": "not a valid email address", "type": "value_error" } ],
    "request_id": "b3f1c2e4-..."      // correlates to server logs
  }
}
```

The HTTP status code still carries the category (`400`/`401`/`403`/`404`/`409`/`422`/`500`); `error.code` exists so the frontend can branch on a stable identifier without parsing `message` strings. Implemented as a single global exception handler in `backend/app/errors.py` — one place, not scattered per-route try/excepts. `request_id` is generated per-request (middleware) and echoed in both success and error responses via a `X-Request-Id` header, so any response can be correlated to logs.

## Phase map

| Phase | Goal |
|---|---|
| 0 | Foundations & contracts — repo layout, tooling, health check, envelopes (this phase) |
| 1 | Auth & roles — users, JWT, `get_current_user`, `require_admin` |
| 2 | Forum domain — posts/comments/solutions, each emitting an event |
| 3 | Event ingestion & idempotency — `POST /api/events`, unique `event_id`, transactional job enqueue |
| 4 | Challenge engine — challenge config CRUD, generic strategy-registry evaluator, durable worker (first end-to-end vertical slice) |
| 5 | Rewards + progress/streak reads — ledger with unique `(user_id, challenge_id, completion_key)`, read endpoints |
| 6 | Frontend foundation — Next.js shell, TanStack Query, auth flow, weekly widget |
| 7 | Core pages — feed (URL state), post detail, create post (optimistic + rollback) |
| 8 | Challenges/Progress + Profile/Rewards — polling, charting data-viz, paginated ledger |
| 9 | Docs, deploy, hardening, bonus (tests, rate limiting, leaderboard, multiple reward types) |

See `plan.md` for the full detail behind each phase and `explain.md` for the running design rationale.
