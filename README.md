# Challenge & Rewards Engine

A Postgres-backed challenge/reward evaluation engine, decoupled from a Vultr Developer Community Forum (Next.js) via an async event pipeline. See `CLAUDE.md` for the architectural invariants and `plan.md` for the phase-by-phase build plan. See `explain.md` for the design rationale (maintained separately — not this file).

> **Status:** Backend Phases 0–5 (foundations, auth & roles, forum domain, event ingestion & idempotency, challenge engine + evaluator + worker, reward ledger + progress/streak reads) and Frontend Phase 6 (auth flow, Shell A layout, live-polling weekly widget, error boundary + skeleton primitives). Core pages (feed/detail/create), the charting data-viz, and the profile/rewards ledger are not built yet.

## Setup

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate   # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Health check: `GET http://localhost:8000/api/health`

The evaluation worker is a separate process (not `BackgroundTasks` — see `CLAUDE.md`); run it alongside the API:

```bash
python -m app.worker
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

Brings up Postgres (named volume), the backend (`/api/health`), the evaluation worker, and the frontend.

## Env vars

See `backend/.env.example` and `frontend/.env.example`.

## What's not here yet

Setup for provisioning challenges, running the worker, and verifying the full event → evaluate → reward flow will be documented here as later phases land (see `plan.md`).
