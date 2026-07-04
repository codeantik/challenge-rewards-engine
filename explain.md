# explain.md — how this system works and why

> **Purpose.** This is not the README (that tells someone how to *run* the app). This doc explains *why every piece is the way it is*, so you can defend any schema decision or trade-off cold in the live review. The AI-usage policy says understanding matters more than output — this is where that understanding lives. Fill in each phase's section as you build it, while the reasoning is fresh.

---

## 0. The mental model (read this first)

There are **two systems** that barely know about each other:

- The **Forum** — posts, comments, solutions. It is a normal CRUD app. Its *only* obligation to the engine is: whenever a user does something meaningful, **emit an event**.
- The **Engine** — knows nothing about posts or comments. It knows about **events, challenges, progress, and rewards**. It receives events, evaluates them against data-driven challenge configs, updates progress, and disburses rewards.

The seam between them is a single event stream. This decoupling is the whole point of the assignment, and it's why the design below keeps insisting that the forum never calls the evaluator directly.

The data flow, end to end:

```
user action (comment)
  → forum handler writes the comment
  → AND emits an event  (POST /api/events, or the internal equivalent)
      → event stored (idempotent on event_id)  ── same DB txn ──▶  job enqueued
  → API returns 202 immediately (no evaluation on the request path)
                                   … later, asynchronously …
  → worker picks up the job
  → generic evaluator runs the user's active challenges against the config
  → progress rows updated
  → if a challenge just completed → reward disbursed (idempotently) into the ledger
  → frontend, which has been polling, sees progress move and the reward appear
```

Everything else is detail hanging off this spine.

---

## 1. The generic, data-driven evaluator  *(the core)*

**The requirement:** an admin creates a challenge by POSTing a config; the engine evaluates *all* challenges from that config with no hardcoded per-type logic. If the domain layer ever branches on `type`, the design has failed.

**The shape.** A challenge row carries:

- `event_type` — *which* event this challenge cares about (e.g. `comment_posted`).
- `type` — *how* to interpret progress (`count` or `streak`).
- `rule_config` (JSONB) — the parameters for that interpretation.
- `reward` (JSONB) — what to grant on completion.

`rule_config` examples:

```jsonc
// count: do event_type N times in the window
{ "target": 3 }
// streak: do event_type on N consecutive days
{ "length": 5 }
```

**Where `type` is allowed to be switched on — exactly one place:** a strategy registry.

```python
STRATEGIES: dict[str, ChallengeStrategy] = {
    "count":  CountStrategy(),
    "streak": StreakStrategy(),
}
```

Each strategy implements the same interface: given a user, a challenge, and the user's relevant events, return `(current_value, target_value, is_complete)`. The evaluator loops over a user's active challenges, looks up `STRATEGIES[challenge.type]`, and asks it to compute progress. Adding a "unique-days-with-2-events" challenge later = add one strategy, touch nothing else. **That extensibility is the exact thing the live review will test** ("now add a challenge type that…").

**Why JSONB for `rule_config` and `reward`:** the config is polymorphic by design — a count challenge and a streak challenge don't share a fixed column set. Columns would force nullable sprawl or a table per type; JSONB keeps the schema honest ("this is opaque config the strategy interprets") and validates at the application edge (Pydantic per type) rather than the DB. Trade-off: no DB-level constraints on config contents — mitigated by strict validation on the admin write path.

> **explain.md note (fill when Phase 4 lands):** paste your `ChallengeStrategy` interface and the two implementations, and note any defaulting you did for missing config fields.

---

## 2. Idempotency — it lives in *two* places

People conflate these; keeping them distinct is a fast way to look sharp in review.

**Place #1 — event ingestion.** The client generates `event_id`. Re-submitting the same `event_id` must return the **original response** without reprocessing. So:

- `events.event_id` has a **unique constraint**.
- On insert conflict, we **don't** just "skip" — we fetch and return the *stored* original response. (Store the response, or enough to reconstruct it, at first processing.)
- Why it matters: networks retry. A double-submitted "comment_posted" must not count twice toward a challenge.

**Place #2 — reward disbursal.** A challenge rewards a user **at most once per qualifying completion**. So:

- The ledger has a **unique constraint** on `(user_id, challenge_id, completion_key)`.
- Disbursal is an insert guarded by that constraint (insert-or-ignore / catch-unique). If the row exists, the reward was already given — do nothing.
- `completion_key` encodes *which* completion: for a one-shot challenge it's constant; for a **weekly** challenge it's the **ISO week** (so it can pay out once per week and reset Monday — see §4).

Together: event idempotency stops double-counting *input*; reward idempotency stops double-paying *output*. The worker can safely run a job twice (see §3) precisely because both guards exist.

> **explain.md note (fill when Phases 3 & 5 land):** paste the two unique constraints and the exact insert-on-conflict code.

---

## 3. The async job — why not the obvious thing

**The requirement:** evaluation runs asynchronously via a background job; ingestion returns `202` immediately; document the choice.

**The trap:** FastAPI `BackgroundTasks`. It runs in the same process, has **no durability** (a crash between `202` and evaluation loses the work), **no retries**, and **breaks with >1 worker**. It demos fine and fails the review question.

**The choice here: a Postgres-backed outbox / job table, polled by a worker.**

- When an event is ingested, in the **same transaction** we insert the event row *and* a `job` row (`status=pending`). Same-txn means we never have an event with no job or a job with no event — this sidesteps the dual-write problem you'd get by publishing to an external queue after committing.
- A worker loop selects pending jobs (`FOR UPDATE SKIP LOCKED` so multiple workers don't collide), evaluates, marks `done`. Failures → retry with backoff / `failed` after N attempts.
- Delivery is **at-least-once**. Combined with the idempotent progress/reward writes from §2, the *effective* semantics are **exactly-once**. That sentence is the one to say out loud in review.

**Why this over Celery/RQ + Redis:** those are perfectly good and show queue fluency, but they add infra to run and reason about. For a 5-day, single-reviewer submission, "it's just Postgres, here's the table, here's the worker loop" is the most *explainable* option — and explainability is the graded axis. (If you'd rather show Redis/Celery, the trade-off note flips: more infra, but battle-tested retries/scheduling out of the box.)

> **explain.md note (fill when Phase 4 lands):** paste the job table schema, the `SKIP LOCKED` select, and your retry policy.

---

## 4. Time — streaks and the Monday reset

Two requirements are secretly the same problem: "N **consecutive days**" and "resets every **Monday**" are both undefined until you pick a timezone. Decide once; apply everywhere.

**Decision (default): a fixed forum timezone**, set as a single config constant (default `UTC`). Rationale: streak-day bucketing and the weekly window must agree; a fixed TZ makes both trivially testable and removes per-user ambiguity. The alternative — per-user local time — is more "correct" for a global forum but multiplies edge cases (DST, travel) and is exactly the kind of extension they might ask you to add live. Keeping it a single constant means that extension is a localized change, and you can *say* so.

**Streak-day bucketing:** map each qualifying event's timestamp to a *day* in the forum TZ, take the **distinct** set of days (two comments same day = one day), sort, and find consecutive runs.
- **Current streak** = the run ending today (define your grace rule: does a gap yesterday break it? Write down the choice).
- **Best streak** = the longest run ever.

**Weekly window:** "this week" = from **Monday 00:00 forum-TZ** to now. Progress for the weekly challenge counts events in that window; the reward's `completion_key` is the **ISO week** so a new week is a fresh completion (§2). The widget "resets Monday" for free because the window and the key both roll over.

> **explain.md note (fill when Phases 4–5 land):** state your chosen TZ, your grace rule for current streak, and paste the day-bucketing function.

---

## 5. The event boundary — one road in

Forum handlers **emit** events; they must not evaluate. Concretely: `POST /posts` writes the post *and* produces a `post_created` event **through the same ingestion path** that the public `POST /api/events` uses. One code path means one place for idempotency, one place jobs get enqueued, and no way for a forum action to secretly bypass the engine.

Why the public `/events` endpoint exists at all alongside server-side emission: it's the engine's contract with *any* producer, and it's what makes the engine genuinely decoupled/reusable. Document that forum-originated events and externally-posted events converge on the same handler.

> **explain.md note:** describe how your forum handlers call into ingestion (shared function vs internal HTTP) and why.

---

## 6. Frontend — where the required behaviours live

Quick map of each graded behaviour to where it should live, so nothing gets dropped:

- **Optimistic UI** (post + comment): TanStack Query `onMutate` writes the cache immediately, `onError` rolls back to the snapshot and toasts. Reviewers *will* force a failure — make rollback real, not cosmetic.
- **Polling** (Challenges page + weekly widget): `refetchInterval`. **Interval choice:** ~30s (the wireframes' own note). Reasoning to document: evaluation is async and human-scale — sub-10s hammers the API for progress that changes on the order of user actions; 30s keeps the widget feeling live without wasteful load. State it explicitly.
- **Data-viz:** streak heatmap or progress rings via **Recharts/D3**. A shadcn/Tailwind bar is explicitly disqualified.
- **Loading:** skeletons, never spinners, on every fetch surface.
- **Error boundaries:** every fetch section degrades to a visible "couldn't load · retry" fallback; the page stays usable.
- **URL state:** feed `sort`/`page` in the querystring — shareable, and back-navigation restores it. Use the router + `useSearchParams`.
- **Custom hook:** at least one named hook, single responsibility. Good candidates: `useWeeklyChallenge()` (encapsulates the polling + reset math) or `useFeedParams()` (URL ↔ filter state).

> **explain.md note (fill across Phases 6–8):** name your custom hook and its single responsibility in one sentence; note your final polling interval.

---

## 7. Per-phase build log

> Fill one entry per phase as it lands. Keep each to: *what I built*, *the one decision I'd be asked about*, *anything I'd do differently*.

### Phase 0 — Foundations
- Built:
- Key decision (error/response envelope, TZ constant):
- Notes:

### Phase 1 — Auth & roles
- Built: `users` table (`id` UUID pk, `email` unique+indexed, `password_hash`, `role` string with a `CHECK (role in ('user','admin'))` constraint, `created_at`) via Alembic migration `c1cf4340c3f3`; `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`; `app/core/security.py` (bcrypt hashing, PyJWT encode/decode); `app/api/deps.py` with `get_current_user`/`require_admin` exposed as reusable `Annotated` aliases (`CurrentUser`, `AdminUser`).
- Key decision (JWT vs session, role gating): JWT, stateless — no session table, no server-side revocation list needed for a 5-day assignment scope. The token payload only carries `sub` (user id) + `iat`/`exp`, deliberately **not** a role claim: `require_admin` re-reads `role` from the DB on every request via `get_current_user`, so a role change (e.g. promoting a user to admin) takes effect on the user's very next request instead of waiting for a fresh login/token. The trade-off is one extra DB read per authenticated request — acceptable at this scale, and it closes the "stale role in an old token" class of bug for free.
- Notes: Email is lowercased at the schema layer (`RegisterRequest`/`LoginRequest` validators) before it ever reaches a query or an insert, so uniqueness and login lookups are case-insensitive without needing a DB-side `citext` extension. There's no self-serve "become an admin" endpoint by design — admin promotion is an out-of-band DB write (a seed script arrives in Phase 9); Phase 1's tests promote a user directly via `UPDATE users SET role = 'admin'` to exercise `require_admin`. Since Phase 4's admin challenge CRUD is the first real consumer of `require_admin`, Phase 1 adds a test-only probe route (`GET /api/auth/_admin_probe`, mounted only inside `tests/test_auth.py`) purely to prove the dependency rejects a `user` token with `403` and accepts an `admin` token with `200` — this is the "admin-only test route" the plan called for, not a shipped product endpoint.

### Phase 2 — Forum domain
- Built: `posts` (`title`, `body`, denormalized `comment_count`/`view_count`, `solution_comment_id`) and `comments` tables, plus the `events` table one phase early (migration `d3a1f9b2c7e4`) — `event_id` UUID primary key doubles as invariant #4's uniqueness guarantee. `app/services/events.py::ingest_event()` is the one ingestion function (invariant #2); `POST /posts`, `GET /posts/{id}` (detail view), `POST /posts/{id}/comments`, `POST /posts/{id}/solution` (owner-only, 403 otherwise) each write their domain row and call `ingest_event` in the *same* session before a single `commit()` — so the domain write and the event write are one DB transaction, not two. `GET /posts` supports `sort=latest|trending` + `page`/`limit`.
- Key decision (trending formula, emit-not-evaluate): `trending_score = (comment_count*3 + view_count) / power(age_hours + 2, 1.5)` — comments outweigh views 3:1 as the stronger engagement signal, and the `+2` offset keeps a just-created post's score finite (no divide-by-~0 spike) while still decaying fast with age. Computed at query time from denormalized counters rather than stored, since "now" keeps moving. Forum handlers never call the evaluator or write progress/reward rows directly — they only ever call `ingest_event`, which for now (pre-Phase-3) just inserts an `Event` row; Phase 3 will extend that same function with `event_id` conflict-replay and the transactional job-row enqueue, not replace it, so the "one road in" invariant holds before and after.
- Notes: `events` and its unique `event_id` PK were built now instead of deferred to Phase 3 so the forum handlers had something real to call — the plan's Phase 3 scope (idempotent replay of the *stored response*, and the outbox job row) is intentionally not implemented yet. Mark-solution validates that the comment actually belongs to the post (cross-post `comment_id` → `404`, not silently accepted); re-marking a different comment as solution is allowed (last call wins), each mark still emits its own `solution_marked` event — de-duplicating *reward* eligibility for that is an engine-side (Phase 4/5) concern, not the forum's. `posts.solution_comment_id` and `comments.post_id` form a genuine FK cycle; the migration creates `posts` with a bare (FK-less) `solution_comment_id` column, creates `comments` referencing `posts`, then adds the `posts → comments` FK constraint afterward.

### Phase 3 — Event ingestion & idempotency
- Built: `jobs` table (migration `d2d29db3cc1e`) — `id`, `event_id` (FK → `events.event_id`, **unique**), `status` (`pending|processing|done|failed`, CHECK-constrained, mirroring the `UserRole`/`enum.StrEnum` pattern from Phase 1), `attempts`, `last_error`, `created_at`/`updated_at`. `ingest_event()` (`app/services/events.py`) is extended in place, not replaced: it now returns `(Event, is_new: bool)`, wraps the event insert + job insert in a single `SAVEPOINT` (`db.begin_nested()`), and on an `event_id` conflict fetches and returns the **existing** row instead of reprocessing. `POST /api/events` (`app/api/events.py`) is a thin wrapper — auth via `CurrentUser`, calls `ingest_event`, commits, returns `202` with an `EventOut` built straight from the (possibly pre-existing) `Event` row.
- Key decision (stored-response replay, transactional enqueue): I didn't add a separate "stored response" column. The `POST /api/events` response body is a pure function of the `Event` row's own columns (`event_id`, `event_type`, `payload`, `created_at`) — so replaying means fetching the *original* row and serializing it again, which is byte-identical by construction, no extra storage needed. The job enqueue lives *inside* `ingest_event` itself (not just the public endpoint) because forum handlers need jobs enqueued too — a `comment_posted` event from `POST /posts/{id}/comments` has to reach the evaluator exactly like one from the public endpoint. Putting both the event insert and the job insert in one `SAVEPOINT` means: a genuinely new event always gets exactly one job, and a replayed event never gets a second one, without ever risking a mid-request rollback of whatever the *calling* forum handler had already flushed (the `Post`/`Comment` row) in the same outer transaction — that's what the savepoint isolates.
- Notes: On conflict, resubmission's `event_type`/`payload` are silently ignored in favor of the stored original — that's what an idempotency-key contract means, not "detect and reject mismatches" (this could be added if the review pushes on it, but isn't in the plan). The `assert`-vs-explicit-raise call: on `IntegrityError` from the savepoint, I only treat it as a replay if a row with that `event_id` genuinely exists; anything else (e.g. a broken `user_id` FK) re-raises so an unrelated bug doesn't get silently swallowed as if it were an idempotent replay. Forum handlers (Phase 2) didn't need any changes — they already call `ingest_event` and never use its return value, so widening its return type to a tuple was invisible to them; they now transitively get a `Job` row per event, which is what makes them Phase-4-ready. Could not exercise `alembic upgrade head` / `pytest` in this session (no reachable Postgres in the sandbox — docker unavailable, native Windows Postgres service present but credentials unknown); verified via `ruff` + `mypy --strict` only. Run `alembic upgrade head` and `pytest` locally before relying on this phase.

### Phase 4 — Challenge engine + async job
- Built: `challenges` table (migration `f6a2c8d4e1b3`) — `name`, `description`, `type`, `event_type`, `rule_config`/`reward` (JSONB), `status` (CHECK-constrained `draft|active|expired|archived`), `start_at`/`end_at`. `progress` table alongside it — `(user_id, challenge_id)` **unique**, `current_value`/`target_value`/`is_complete`/`completed_at`. `app/services/strategies.py` holds the registry (`STRATEGIES: dict[str, ChallengeStrategy]`) plus `CountStrategy` (`{"target": N}`) and `StreakStrategy` (`{"length": N}`), each with `validate_config()` (schema-time) and `evaluate()` (worker-time). `app/services/evaluator.py::evaluate_event()` is the generic loop: find active challenges for `event.event_type`, look up `STRATEGIES[challenge.type]`, upsert the result into `progress` via Postgres `INSERT ... ON CONFLICT DO UPDATE`. `app/worker.py` is the durable poller (`claim_and_process_one` does the `SELECT ... FOR UPDATE SKIP LOCKED` claim + evaluate + mark done/failed; `run_forever` loops it with a 1s backoff when the queue is empty). Admin CRUD lives in `app/api/admin_challenges.py` (`POST/GET/PATCH /api/admin/challenges`, `DELETE` archives rather than deletes) — added as its own `worker` service in `docker-compose.yml` running `python -m app.worker` alongside `backend`.
- Key decision (strategy registry, outbox worker): Neither `evaluate_event` nor the worker ever branches on `challenge.type` — even the admin-write-path validation doesn't hardcode `Literal["count","streak"]`; `app/schemas/challenges.py::validate_challenge_config()` looks the type up in `STRATEGIES` itself and delegates to that strategy's own `validate_config()`. So adding a third strategy is genuinely one file (implement `ChallengeStrategy`, add one registry line) — the schema, the evaluator, and the worker are all unaware anything changed. The bigger decision: **progress is a materialized cache the worker recomputes wholesale on every run, not a counter it increments.** `CountStrategy.evaluate()` re-counts matching events in the window from scratch; `StreakStrategy.evaluate()` re-derives the whole day-set and re-runs the streak scan. This is what makes "the worker can run a job twice safely" (invariant #5) true for *progress writes* specifically, not just reward disbursal (Phase 5) — there's no "+1" step to accidentally double, so replaying `evaluate_event` for the same event is a no-op by construction (`test_evaluate_event_is_idempotent_when_run_twice`). The trade-off is a full re-scan of the user's matching events on every evaluation instead of an O(1) increment — acceptable at this scale, and it's the difference between "idempotent because we recompute truth" and "idempotent because we hope a lock held."
- Notes: **Streak grace rule** (documented as promised in §4): the current streak is the run ending on the most recent active day, *as long as* that day is today or yesterday — a day with no event yet today doesn't break a streak that ran through yesterday, but a full skipped day does. Implemented as a pure function, `compute_streak(days: set[date], today: date) -> tuple[current, best]`, in `app/services/strategies.py`, tested in isolation in `tests/test_strategies.py` without touching the DB. **Retry policy**: `job.attempts` increments on any exception from `evaluate_event`; below `MAX_ATTEMPTS = 5` the job goes back to `pending` (picked up on the worker's next poll — a poll-interval's worth of backoff, not exponential); at `MAX_ATTEMPTS` it's marked `failed` permanently. **Gotcha worth flagging**: `zoneinfo.ZoneInfo("UTC")` raises `ZoneInfoNotFoundError` on both Windows and slim Linux Docker images (`python:3.12-slim` ships no IANA tzdata) — added `tzdata` as an explicit dependency rather than relying on the OS. Discovered this by actually trying to instantiate `ZoneInfo("UTC")` in this sandbox before assuming stdlib `zoneinfo` was enough; would have silently 500'd every streak evaluation in the built Docker image otherwise. `RewardConfig` (`{"type": str, "amount": int > 0}`) is intentionally generic and unvalidated beyond shape — Phase 5 owns what "disbursing" a reward means. Could not exercise `alembic upgrade head` / `pytest` against a live DB in this session (same constraint as Phase 3 — no reachable Postgres in the sandbox); verified via `ruff`, `mypy --strict`, and by exercising `compute_streak`/`validate_config` directly as plain Python outside the test harness. Run `alembic upgrade head` and `pytest` locally before relying on this phase.

### Phase 5 — Rewards + progress/streaks
- Built:
- Key decision (completion_key, ledger constraint):
- Notes:

### Phase 6 — Frontend foundation
- Built:
- Key decision (polling interval, custom hook):
- Notes:

### Phase 7 — Core pages
- Built:
- Key decision (optimistic rollback, URL state):
- Notes:

### Phase 8 — Challenges/Progress + Profile
- Built:
- Key decision (which data-viz, why):
- Notes:

### Phase 9 — Docs / deploy / bonus
- Built:
- Notes:

---

## 8. If you remember nothing else (review cheat-sheet)

- The engine is **decoupled**; the forum only **emits events**; there is **one road in**.
- The evaluator is **data-driven**; `type` is switched on in **exactly one place** (the strategy registry).
- **Idempotency is in two places:** event replay (`unique event_id`, return stored response) and reward once-only (`unique (user, challenge, completion_key)`).
- The job is **durable** (Postgres outbox, same-txn enqueue, `SKIP LOCKED`, retries) → **at-least-once + idempotent writes = effectively-once**. `BackgroundTasks` was rejected *because* it isn't durable.
- **One timezone**, fixed as a constant, drives both streak-day bucketing and the Monday weekly reset. Per-user TZ is the anticipated extension.
- Frontend: **optimistic with real rollback**, **URL-as-state**, **skeletons not spinners**, **charting-lib data-viz**, **~30s polling** (justified).
