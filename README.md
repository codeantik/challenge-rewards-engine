# Challenge & Rewards Engine

A Postgres-backed challenge/reward evaluation engine, decoupled from a Vultr
Developer Community Forum (Next.js) via an async event pipeline. See
`CLAUDE.md` for the architectural invariants this repo is graded against,
`plan.md` for the phase-by-phase build plan, and `explain.md` for the full
design rationale (why each schema/trade-off is the way it is — read that
before a live review).

> **Status:** all phases (0–9) complete. Backend: auth, forum domain, event
> ingestion + idempotency, challenge engine + generic evaluator + durable
> worker, reward ledger, progress/streak reads, rate limiting on
> `POST /api/events`. Frontend: auth flow, Shell A layout with a live-polling
> weekly widget, feed/detail/create with optimistic updates + real rollback,
> challenges/progress page with charting data-viz, profile/rewards ledger.
> No public deploy for this submission — see "Deployment" below.

## Quickstart (5 minutes)

```bash
git clone <this repo> && cd challenge-rewards-engine
docker compose up --build
```

Then, in a separate terminal, provision an admin user and sample challenges:

```bash
docker compose exec backend python -m app.scripts.seed
```

Open `http://localhost:3000`, register a new account, and go verify the
flow (below). The API is at `http://localhost:8000/api`
(`GET /api/health` to confirm it's up).

## Setup (without Docker)

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate   # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -e ".[dev]"
cp .env.example .env     # then point DATABASE_URL at a real Postgres
alembic upgrade head
uvicorn app.main:app --reload
```

The evaluation worker is a **separate process** — this is not
`FastAPI BackgroundTasks` (see `CLAUDE.md` invariant #5: no durability, no
retries, breaks with >1 worker). Run it alongside the API:

```bash
python -m app.worker
```

Provision an admin + sample challenges (idempotent, safe to re-run):

```bash
python -m app.scripts.seed
```

By default this creates `admin@example.com` / `ChangeMe123!` — override with
`SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` env vars before running it.

Run the test suite (needs a real Postgres reachable via `DATABASE_URL`,
schema migrated):

```bash
pytest -q
ruff check .
mypy app
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

App: `http://localhost:3000`

### Everything via Docker Compose

```bash
docker compose up --build
```

Brings up Postgres (named volume, host port `5433` to avoid clashing with a
local Postgres), the backend (`/api/health`), the evaluation worker, and the
frontend — each as its own service, matching the "worker is a separate
process" invariant above.

## Env vars

See `backend/.env.example` and `frontend/.env.example` for the full list.
Notable ones beyond the obvious (`DATABASE_URL`, `JWT_SECRET`):

- `FORUM_TIMEZONE` — the single fixed timezone driving streak-day bucketing
  and the Monday weekly reset (CLAUDE.md invariant #6). Default `UTC`.
- `EVENT_RATE_LIMIT_CAPACITY` / `EVENT_RATE_LIMIT_WINDOW_SECONDS` — the
  token-bucket limit on `POST /api/events`, per authenticated user. Default
  20 requests / 60s.

## How to provision challenges

Three ways:

1. **Seed script** (`python -m app.scripts.seed` / the Docker Compose
   equivalent above) — creates one admin user and five sample challenges
   covering every axis the engine supports: `count` vs `streak` type,
   `one_time` vs `weekly` period, and a non-`points` reward type (`badge`)
   to show `reward.type` is a free-form string, not a fixed enum.
2. **Admin console** (Phase 10) — log in as an admin and an "Admin" link
   appears in the sidebar (`/admin/challenges`, gated client-side on
   `user.role === "admin"`, same as the seeded admin's account). List, create,
   edit, and archive challenges through a form that mirrors
   `ChallengeCreate`/`ChallengeUpdate` field-for-field — no curl required.
3. **Admin API directly**, once you have an admin token (`POST /api/auth/login`
   as the seeded admin, or promote your own user — see "Notes" below):

   ```bash
   curl -X POST http://localhost:8000/api/admin/challenges \
     -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
     -d '{
       "name": "Conversation Starter",
       "type": "count",
       "event_type": "comment_posted",
       "rule_config": {"target": 3},
       "reward": {"type": "points", "amount": 50},
       "status": "active",
       "period": "one_time"
     }'
   ```

   `type` must be one of the strategy registry's keys (`count`, `streak` —
   `GET /api/admin/challenges` after a bad `type` will 422 and name the valid
   ones). `rule_config` shape depends on `type`: `{"target": N}` for `count`,
   `{"length": N}` for `streak`.

There's no self-serve "become an admin" endpoint by design (see Phase 1 notes
in `explain.md`) — promote a user directly in Postgres if you're not using
the seeded admin:

```sql
UPDATE users SET role = 'admin' WHERE email = 'you@example.com';
```

## How to verify the full flow

This is the event → job → progress → reward chain end-to-end — the
riskiest/most-graded part of the assignment. Using the seeded "First
Comment" challenge (`count`, target 1, reward 10 points) as the fastest path
to a visible payout:

1. Register + log in as a normal user (via the frontend, or
   `POST /api/auth/register` then `/api/auth/login`).
2. Create a post (`POST /api/posts` or the "New post" page) and post a
   comment on it (`POST /api/posts/{id}/comments` or the post detail page).
   This emits a `comment_posted` event and returns `202` immediately —
   nothing evaluates on the request path.
3. Within ~1 second (the worker's poll interval), the durable worker claims
   the enqueued job, evaluates the user's active challenges, and (since
   "First Comment" needs just one qualifying event) marks it complete and
   disburses the reward — all in one transaction.
4. Confirm: `GET /api/users/me/progress` shows `is_complete: true` for that
   challenge; `GET /api/users/me/rewards` shows one ledger row
   (`reward_type: "points", amount: 10`); `GET /api/users/me/rewards/summary`
   shows `total_points: 10`. On the frontend, the Challenges page's progress
   rings and the Profile page's points balance reflect this without a
   reload (both poll every ~30s).
5. To see idempotency instead of just the happy path: resubmit the exact
   same `event_id` to `POST /api/events` — you get back the byte-identical
   `202` response and no second job/progress write. Run the worker against
   the same job twice (or just trust `tests/test_evaluator.py::test_evaluate_event_is_idempotent_when_run_twice`)
   to see the reward isn't double-disbursed.

I ran this exact sequence by hand against a live Postgres instance while
finishing this phase — a `comment_posted` event moved four challenges'
progress in one worker pass and disbursed the "First Comment" reward
correctly on the first try.

## Design decisions

The short version — see `explain.md` for the full reasoning behind each:

- **Evaluator is data-driven**: `challenge.type` is switched on in exactly
  one place, a strategy registry (`app/services/strategies.py`). Adding a
  challenge type is one new strategy class + one registry line.
- **Durable async evaluation**: a Postgres outbox table (`jobs`), enqueued in
  the same transaction as the event insert, polled with
  `SELECT ... FOR UPDATE SKIP LOCKED`. Not `BackgroundTasks` — no durability,
  no retries, breaks with >1 worker.
- **Idempotency in two places**: event ingestion (unique `event_id`, replay
  the stored original response) and reward disbursal (unique
  `(user_id, challenge_id, completion_key)`).
- **One fixed forum timezone** drives both streak-day bucketing and the
  Monday weekly reset — never per-user.
- **Rate limiting** (bonus): an in-memory token bucket per user on
  `POST /api/events`, chosen over adding Redis for the same reason the job
  queue is plain Postgres — the most explainable option that satisfies the
  requirement, with the trade-off (per-process state) spelled out in
  `app/core/rate_limit.py`.

## Testing

`pytest -q` runs 63 tests against a real Postgres database (schema migrated
via `alembic upgrade head`) covering: idempotent event replay, the
count/streak strategies (including the streak grace-day rule) in isolation,
worker claim/retry/failure behavior, reward disbursal exactly-once under a
double-run, and the rate limiter (pure unit tests + a live 429 against the
endpoint). `ruff check .` and `mypy app` (strict) are both clean.

## Deployment

Three pieces, three homes — Postgres, backend/worker, and frontend each
deploy independently:

**1. Postgres** — Supabase or Neon; both have a free Postgres tier that
doesn't expire, unlike Render's (deleted after 90 days). Create a project,
copy its connection string as-is — a plain `postgres://...?sslmode=require`
URL is fine (Supabase: Project Settings → Database → Connection string →
URI; use the **Session pooler** one, since a serverless-style deploy opens
more short-lived connections than a direct connection slot budget likes).
`app/core/config.py` rewrites the scheme to `postgresql+asyncpg://` and
lifts `sslmode` into an asyncpg `ssl=True` connect arg automatically, so
nothing needs hand-editing.

**2. Backend (Render)** — `render.yaml` at the repo root is a Render
Blueprint defining one free Web Service, `challenge-rewards-api`. The
existing Dockerfile CMD (`alembic upgrade head && uvicorn ...`) runs
migrations on every boot, then serves `/api`. Push to GitHub, then in the
Render dashboard: New → Blueprint → point at this repo. Paste the
Supabase/Neon connection string into `DATABASE_URL` when prompted (the
blueprint marks it `sync: false` — manual, not committed). Update
`CORS_ORIGINS`/`CORS_ORIGIN_REGEX` in `render.yaml` to match the actual
Vercel domain before or after the first deploy. No payment method needed —
this is Render's genuinely free Web Service plan.

**3. Worker (GitHub Actions, not Render)** — Render has no free plan for
either an always-on Background Worker (~$7/mo) or a Cron Job (Render wants
a card on file for a paid instance type even though the per-second billing
would be pennies). Instead, `.github/workflows/drain-worker.yml` runs
`python -m app.worker --once` (`app/worker.py::drain_once`, which drains
every pending job then exits) on a GitHub Actions schedule every 5
minutes — free and unlimited on this public repo, no payment method
anywhere. Add the same Postgres connection string as a repo secret:
Settings → Secrets and variables → Actions → New repository secret →
`DATABASE_URL`. Trade-off: reward evaluation lands within the schedule
interval (up to ~5 min, GitHub's minimum, sometimes delayed further under
platform load) instead of the ~1s `run_forever` gives locally. If that
latency matters more than avoiding a card on file, switch to a paid Render
Background Worker running `app/worker.py` with no `--once` flag instead.

**4. Frontend (Vercel)** — import the repo, set **Root Directory** to
`frontend` in the project settings (Vercel auto-detects Next.js from
there), and set `NEXT_PUBLIC_API_BASE_URL` to the Render web service's URL
plus `/api` (e.g. `https://challenge-rewards-api.onrender.com/api`) for
Production and Preview. `CORS_ORIGIN_REGEX` on the backend
(`https://your-app-.*\.vercel\.app`) is what lets PR preview deployments —
which get a fresh Vercel subdomain each time — reach the API without
re-deploying the backend per PR.

Note Render's free Web Service also spins down after 15 minutes idle and
cold-starts (~30-50s) on the next request — expected on a free-tier demo,
not a bug.

## Bonus features

In priority order per `plan.md`:

1. **Unit tests** — done throughout (not deferred to this phase): streak
   logic (`tests/test_strategies.py`), event idempotency
   (`tests/test_events.py`), reward disbursal exactly-once
   (`tests/test_rewards.py`), a CORS regression (`tests/test_errors.py`),
   plus admin/auth/posts/evaluator/worker coverage.
2. **Rate limiting on `/api/events`** — done, see above.
3. **Admin console UI** (Phase 10) — done: `/admin/challenges` (list,
   create, edit, archive), gated to `role === "admin"`. Previously the admin
   CRUD API existed but had no frontend, so provisioning meant curl or the
   seed script.
4. **Leaderboard page** — not built (descoped for this submission).
5. **Multiple reward types** — `reward.type` was already a free-form string
   from Phase 4 (not a `points`-only enum), so "points" and "badge" rewards
   already coexist in the ledger and the Profile page's summary endpoint
   groups by `reward_type`; a dedicated UI for a third type wasn't built.
