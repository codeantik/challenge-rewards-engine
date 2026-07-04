# Build Plan — Challenge & Rewards Engine + Vultr Community Forum

**Deadline:** Day 5. **Stack:** FastAPI + Postgres (backend), Next.js + TS + Tailwind + shadcn (frontend).

## Guiding principles

1. **Vertical slice early.** The riskiest thing in this assignment is the async chain `event → job → progress → reward`. Get a *thin* version of that green by end of Day 2, then widen and polish. Don't build all the endpoints before the first reward is ever disbursed.
2. **Invariants over features.** A few properties must hold everywhere: the evaluator has *no per-challenge-type branching in domain logic*; every mutation flows through one event path; idempotency is enforced at the DB layer, not in app code you hope runs once. These are graded harder than any single endpoint.
3. **Commit per phase, keep it incremental.** The rubric explicitly rewards a clear commit history. One coherent commit (or a few) per phase below.
4. **Update `explain.md` as you go.** Each phase has an "explain.md note" — fill that section in when the phase lands, while it's fresh. That doc is your live-review insurance.
5. **Bonus is last.** Nothing in the Bonus section gets touched until the core end-to-end flow works and is documented.

---

## Phase 0 — Foundations & contracts  *(Day 1, first half)*

**Goal:** A repo two services can grow in, with conventions locked so later phases don't drift.

- Monorepo: `/backend` (FastAPI), `/frontend` (Next.js), `/docker-compose.yml`, root `README.md`, `explain.md`, `CLAUDE.md`.
- `docker-compose` with Postgres; both services runnable locally.
- Backend skeleton: FastAPI app, `/api` base path, settings via pydantic-settings, Alembic wired, a `/api/health` route, structured **error envelope** decided and implemented as an exception handler.
- Decide and write down (in `explain.md`): error envelope shape, response envelope, the **event catalog** (`post_created`, `post_viewed`, `comment_posted`, `solution_marked`), and the forum timezone.
- Tooling: ruff + mypy (backend), eslint + prettier + strict tsconfig (frontend). `.env.example` for both.

**Invariants introduced:** error envelope, base path, TZ constant.
**Done when:** `docker compose up` gives you Postgres + a healthy FastAPI on `/api/health`.
**explain.md note:** the mental model + the five core decisions (skeleton them now, fill as built).

---

## Phase 1 — Auth & roles  *(Day 1, second half)*

**Goal:** Everything downstream can require a user and gate admin.

- Users table (email, password hash, role `user|admin`), Alembic migration.
- `POST /api/auth/register`, `POST /api/auth/login` (JWT), `GET /api/auth/me`.
- `get_current_user` dependency; `require_admin` dependency returning `403` for non-admins.

**Done when:** you can register, log in, hit `/auth/me`, and a `user` token is rejected by an admin-only test route.
**explain.md note:** auth choice (JWT vs session) and the role-gating mechanism.

---

## Phase 2 — Forum domain  *(Day 1 → Day 2)*

**Goal:** Real event producers exist.

- Posts (create, list with `sort=latest|trending` + `page`/`limit`, detail with nested comments), comments, mark-solution (owner-only, `403` otherwise).
- Each mutation **emits an event through the ingestion path** (see Phase 3) — not by calling the evaluator directly.
- `trending` = pick a simple, documented formula (e.g. score decayed by age); write it down.

**Done when:** creating a post / comment / solution writes an event row as a side effect.
**explain.md note:** the event boundary — why forum handlers emit rather than evaluate.

---

## Phase 3 — Event ingestion & idempotency  *(Day 2)*

**Goal:** One durable front door for all events.

- `POST /api/events` → `202 Accepted`, body `{ event_id, event_type, payload }`.
- Events table with **unique `event_id`**; re-submitting a seen `event_id` **replays the stored original response** without reprocessing.
- In the *same transaction* as the event insert, enqueue an evaluation job (outbox/job row). No dual-write.

**Invariants introduced:** event-level idempotency (replay stored response), transactional enqueue.
**Done when:** posting the same `event_id` twice returns byte-identical responses and enqueues one job.
**explain.md note:** idempotency place #1 (event replay), and the outbox pattern.

---

## Phase 4 — Challenge engine: config + generic evaluator + async job  *(Day 2 → Day 3)*

**Goal:** The heart of the assignment — and the first end-to-end green.

- Challenges table: `name, description, type, rule_config (JSONB), event_type, start_at, end_at, reward (JSONB), status`. Lifecycle `draft → active → expired → archived`.
- Admin CRUD: `POST/GET/PATCH/DELETE /api/admin/challenges` (DELETE archives). Validate inputs; sensible defaults for optional fields.
- **Generic evaluator** driven entirely by `rule_config`: a strategy registry keyed by `type`. `count` and `streak` strategies. **Zero `if type == ...` in domain logic.**
- **Durable worker** polling the job table; evaluates the affected user's active challenges; writes/updates progress.

**Invariants introduced:** no per-type branching; strategy registry is the only place `type` is switched on.
**Done when (VERTICAL SLICE):** emit a `comment_posted` event → worker evaluates a count challenge → a progress row moves from 0/3 to 1/3.
**explain.md note:** the generic evaluator (the core), the async job choice + justification, streak-day bucketing.

---

## Phase 5 — Rewards + progress/streak reads  *(Day 3)*

**Goal:** The backend flow is complete and queryable.

- Reward ledger: `user_id, reward_type, amount, source_challenge_id, completion_key, created_at`, **unique `(user_id, challenge_id, completion_key)`**.
- Idempotent disbursal on completion (guarded by that constraint), inside the evaluation transaction.
- Read endpoints: `GET /challenges` (active + progress), `GET /challenges/weekly`, `GET /users/me/progress`, `GET /users/me/streaks`, `GET /users/me/rewards` (paginated).

**Invariants introduced:** reward-level idempotency (place #2), weekly `completion_key` = ISO week.
**Done when:** completing a challenge disburses exactly one ledger entry, even if the job runs twice.
**explain.md note:** idempotency place #2, weekly reset via `completion_key`, streak endpoints.

---

## Phase 6 — Frontend foundation  *(Day 3 → Day 4)*

**Goal:** Establish the patterns so pages are cheap to build.

- Next.js (App Router), Tailwind, shadcn, TanStack Query provider, auth flow + token handling.
- **Shell A** layout (left sidebar · feed · right rail) — 1d–1g are already drawn in it.
- **Weekly Challenge widget** as a layout-level component on all 5 pages, polling.
- Primitives: `Skeleton` surfaces, an error boundary wrapper, one **named custom hook** with a single responsibility (candidate: `useWeeklyChallenge` or `useUrlFilters`).

**Done when:** logged-in shell renders on every route with a live-polling weekly widget.
**explain.md note:** the polling interval choice + reasoning; the custom hook's single responsibility.

---

## Phase 7 — Core pages  *(Day 4)*

**Goal:** Feed, detail, create — with the required behaviours, not stubs.

- **Feed:** `sort`/`page` in the **URL** (shareable, back-restores), skeleton rows, **optimistic** new-post insert with rollback + toast.
- **Post detail:** nested comments, optimistic comment, owner-only mark-as-solution.
- **Create post:** form → optimistic feed insert → emits `post_created`.

**Done when:** filters survive a share+reload+back; a failed post visibly rolls back.
**explain.md note:** optimistic update + rollback mechanics; URL-as-state.

---

## Phase 8 — Challenges/Progress + Profile/Rewards  *(Day 4 → Day 5)*

**Goal:** The polling page + the real data-viz, plus rewards surface.

- **Challenges & Progress:** polls (async evaluation), weekly breakdown, and the **charting data-viz** — streak heatmap *or* progress rings via Recharts/D3. **Not** a component-lib progress bar.
- **Profile / Rewards:** points balance, badges, paginated ledger with skeleton rows.
- Error boundaries with visible retry fallback on every fetch surface.

**Done when:** progress trickles in without reload; the data-viz is genuinely chart-library-rendered.
**explain.md note:** which data-viz and why; how polling drives it.

---

## Phase 9 — Docs, deploy, bonus, hardening  *(Day 5)*

**Goal:** Ship something a reviewer can run in five minutes.

- Finalize `README.md` (setup for both services, env vars, **how to provision challenges**, **how to verify the full flow**, design decisions) and `explain.md`.
- `.env.example` both sides; a seed/provisioning script for an admin + sample challenges.
- Deploy to a public URL (or record a 3–5 min walkthrough).
- **Bonus, in priority order:** unit tests (streak logic, idempotency, reward disbursal) → rate limiting on `/api/events` → leaderboard page → multiple reward types.

**Done when:** a stranger clones, runs, provisions a challenge, emits an event, and sees a reward — guided only by your README.

---

## Risk register (watch these)

- **Evaluator branching creep** — the moment domain code checks `type`, refactor into the strategy.
- **Non-durable jobs** — `BackgroundTasks` will look fine locally and fail the review question. Use the durable path.
- **Timezone ambiguity** — streaks and Monday-reset are undefined until TZ is fixed. Decide once, apply everywhere.
- **Optimistic UI without real rollback** — reviewers will force a failure; make sure it actually reverts.
- **Data-viz disqualification** — a shadcn/Tailwind bar does not count. Use a charting lib.