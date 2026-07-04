# Challenge & Rewards Engine

A Postgres-backed challenge/reward evaluation engine, decoupled from a Vultr Developer Community Forum (Next.js) via an async event pipeline. See `CLAUDE.md` for the architectural invariants and `plan.md` for the phase-by-phase build plan. See `explain.md` for the design rationale (maintained separately — not this file).

> **Status:** Phase 0 (foundations) only. Auth, domain models, the evaluator, and the frontend pages are not built yet.

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

Brings up Postgres (named volume), the backend (`/api/health`), and the frontend.

## Env vars

See `backend/.env.example` and `frontend/.env.example`.

## What's not here yet

Setup for provisioning challenges, running the worker, and verifying the full event → evaluate → reward flow will be documented here as later phases land (see `plan.md`).
