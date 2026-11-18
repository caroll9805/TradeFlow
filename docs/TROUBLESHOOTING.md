# Troubleshooting

Always start with the logs: `logs\*.log` (written by the .cmd launchers), `docker compose ps`, and
`docker compose logs --tail 200 <service>` (`db`, `backend`, `worker`, `frontend`).

## Docker Desktop
| Symptom | Fix |
|---|---|
| `error during connect` / `The system cannot find the file specified ... dockerDesktopLinuxEngine` | Docker Desktop is not running or still starting. Open it and wait for *Engine running*. |
| `WSL 2 installation is incomplete` | Run `wsl --update` in an admin PowerShell, reboot, start Docker Desktop. |
| Build is extremely slow / `TLS handshake timeout` / `i/o timeout` pulling images | Network/registry throttling. Re-run `docker compose build` (completed layers are cached). Behind a corporate proxy, set it in Docker Desktop → Settings → Resources → Proxies. |
| `no space left on device` | `docker system prune` (removes unused images/caches), or increase the disk image size in Settings. |
| Frontend build killed / exit code 137 | Not enough memory: give Docker ≥4 GB (Settings → Resources). |
| `port is already allocated` (8080, 8000) | Another program uses the port. Stop it, or change `"8080:80"` / `"8000:8000"` in `docker-compose.yml`. |
| Scripts blocked: `running scripts is disabled on this system` | Use the `.cmd` launchers, or `powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1`. |
| `env file ... .env not found` | `Copy-Item .env.example .env` (the start script does this automatically). |

## PostgreSQL
| Symptom | Fix |
|---|---|
| `password authentication failed for user "tradeflow"` | The `pgdata` volume was created with an older password. Either restore the old `POSTGRES_PASSWORD` in `.env`, or wipe the DB: `docker compose down -v`. |
| `set POSTGRES_PASSWORD in .env` | `.env` is missing the variable. |
| Connection string breaks | Use only letters and digits in `POSTGRES_PASSWORD` (it is embedded in `DATABASE_URL`). |
| `extension "postgis" is not available` | You replaced the `postgis/postgis` image with plain `postgres`; switch back. |
| Want a clean start | `docker compose down -v; docker compose up -d` (deletes all data). |

## Backend (Python / FastAPI)
| Symptom | Fix |
|---|---|
| `pip install` fails during build | Network issue → re-run the build. A specific package version not found → check the internet connection to pypi.org. |
| Backend restarts in a loop | `docker compose logs backend`. Typical: database not reachable (check `db` is healthy), an error in `alembic upgrade head` (copy the traceback), or `JWT_SECRET must be set` when `ENVIRONMENT=production`. |
| `Target database is not up to date` / migration errors after code changes | `docker compose exec backend alembic upgrade head`; for local test data you can reset with `down -v`. |
| `exec ./entrypoint.sh: no such file` or `\r: command not found` | The file was saved with Windows (CRLF) line endings. Convert `backend/entrypoint.sh` to LF (VS Code: status bar “CRLF” → “LF”). |
| HTTP 401 after some time | The access token expired; the frontend refreshes automatically. If it persists, log out and in. |
| HTTP 429 | Auth or AI rate limit reached; wait one minute or raise `AUTH_RATE_LIMIT` in `.env`. |
| Foreign-currency offer rejected (“No recorded exchange rate”) | Add a rate in Platform admin → Exchange rates. |

## Frontend (npm / React)
| Symptom | Fix |
|---|---|
| `npm ERR! ERESOLVE` during build | Delete `frontend/package-lock.json` (if present) and rebuild; report the conflicting packages. |
| TypeScript errors stop the build | They are printed in `logs\build.log` / `logs\frontend-build.log` with file and line. |
| Blank page | Browser dev tools (F12) → Console. Rebuild with `docker compose up -d --build frontend`. |
| Map tiles missing | The browser needs internet access to `tile.openstreetmap.org`. |

## Frontend ↔ backend connection
The browser only talks to `http://localhost:8080`; Nginx forwards `/api/*` to `http://backend:8000` inside the
Docker network, so no CORS or API URL configuration is needed.
| Symptom | Fix |
|---|---|
| UI shows “Something went wrong” on every page / `502 Bad Gateway` on `/api` | Backend not running or not healthy: `docker compose ps`, `docker compose logs backend`. |
| Works on :8000 but not via :8080 | Check `frontend/nginx.conf` `proxy_pass http://backend:8000;` and that both services are on the default compose network. |
| Vite dev server (:5173) cannot reach API | In dev compose `VITE_API_PROXY=http://backend:8000` is set; outside Docker use `http://localhost:8000`. |
| Verify the chain | `docker compose exec -T backend python -m app.smoke --base http://frontend` |
