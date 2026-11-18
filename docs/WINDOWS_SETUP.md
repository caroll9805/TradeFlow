# Running TradeFlow on Windows 11 (PowerShell + Docker Desktop)

Everything (Python packages, npm packages, PostgreSQL/PostGIS, Nginx) is installed **inside Docker images** during
`docker compose build`. You do not need Python or Node.js on Windows.

## One-time prerequisites
1. Install **Docker Desktop** (WSL 2 backend) and start it. Wait until the status bar says *Engine running*.
2. Allocate at least 4 GB RAM to Docker (Settings → Resources) — the frontend build needs ~1.5 GB.
3. Free ~4 GB of disk space. The first build downloads roughly 1 GB.

## Easiest way
Double-click **`START_TRADEFLOW.cmd`** in the TradeFlow folder. Then, optionally, **`RUN_TESTS.cmd`**.
Both save complete output in `logs\` (`build.log`, `up.log`, `services.log`, `smoke.log`, `pytest.log`, `vitest.log`,
`frontend-build.log`, `migrations.log`, `test-summary.txt`).

## Same steps by hand, in order (PowerShell)
```powershell
cd $env:USERPROFILE\Desktop\TradeFlow

# 1. Docker is running?
docker info
docker compose version

# 2. Configuration (only the first time): copy and edit secrets
Copy-Item .env.example .env
notepad .env        # set POSTGRES_PASSWORD (letters/digits only) and JWT_SECRET (long random string)

# 3. Build images = install all dependencies (pip install -r requirements-dev.txt, npm install, tsc, vite build)
docker compose build --progress plain

# 4. Start PostgreSQL, backend (runs `alembic upgrade head` + seed automatically), worker, frontend
docker compose up -d
docker compose ps                       # backend should become "healthy" within ~1 minute
docker compose logs -f backend          # Ctrl+C to stop following

# 5. End-to-end smoke test through the frontend proxy (frontend -> /api -> FastAPI -> PostgreSQL)
docker compose exec -T backend python -m app.smoke --base http://frontend

# 6. Automated tests
docker compose run --rm --no-deps backend pytest -q             # backend (pytest)
docker compose run --rm backend alembic current                 # migration state on PostgreSQL
docker compose --profile test build frontend-test               # TypeScript check + production build
docker compose --profile test run --rm frontend-test            # frontend tests (Vitest)
```
Open **http://localhost:8080** (app) and **http://localhost:8000/api/docs** (API).
Demo logins (only with `SEED_DEMO=true`): `buyer@demo.example.com`, `supplier@…`, `data@…`, `admin@…`, password `Demo12345!`.

## Everyday commands
| Task | Command |
|---|---|
| Stop | `docker compose down` |
| Start again | `docker compose up -d` |
| Rebuild after code changes | `docker compose up -d --build` |
| Development mode (hot reload, Vite on :5173) | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build` |
| Reset the database completely | `docker compose down -v` then `docker compose up -d` |
| Shell inside backend | `docker compose exec backend bash` |
| psql | `docker compose exec db psql -U tradeflow -d tradeflow` |
| Remove simulated demo data | Platform admin → Demo data, or set `SEED_DEMO=false` and `docker compose down -v` |
| Create a new migration | `docker compose exec backend alembic revision --autogenerate -m "describe change"` |

Services and ports: `db` (PostgreSQL 16 + PostGIS, internal 5432), `backend` (FastAPI, host port 8000), `worker`
(scheduled connectors), `frontend` (Nginx serving the React build and proxying `/api` to `backend:8000`, host
port 8080). Redis is **not required**: rate limiting is in-process for this single-instance setup.
