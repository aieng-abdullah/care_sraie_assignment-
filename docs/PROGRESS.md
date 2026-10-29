# Progress

Source of truth for project status. Update after every task/session, same commit as related code.

## Status board

| Task | Deliverable | Status |
|------|-------------|--------|
| 1 | Backend scaffold: config, logging, health probes, Celery app, Alembic, Docker | Done |
| 2 | Documents API (upload, status, results, search, corrections, reprocess) | Not started |
| 3 | PDF / image pipelines (page-parallel OCR + text extraction) | Not started |
| 4 | Excel / CSV pipelines | Not started |
| 5 | LLM extraction + grounding + validation rules | Not started |
| 6 | Frontend (Next.js): upload, monitor, inspect, review, correct, search | Not started |
| 7 | Evaluation dataset, metrics, report | Not started |

## Daily log

### 2026-10-29 (later)

- Dropped auth layer per owner decision: assignment brief requires "strong security" but never mentions login/JWT; JWT existed only as an AGENTS.md rule. Removed `jwt_secret`/`jwt_*` and `rate_limit_login_per_minute` from `Settings`, `JWT_*`/`RATE_LIMIT_LOGIN_PER_MINUTE` from `.env.example`, `pyjwt` + `argon2-cffi` deps; AGENTS.md security/NFR rules rewritten (no authz); `users` table and `user_id` columns removed from `docs/database_schema.md`; auth sequence and JWT references removed from `docs/architecture.md` and README.
- Security now: magic-byte checks, size/page caps, upload rate limit, parameterized ORM, env-only secrets, no PII in logs. Decision: re-add auth only if deployment needs multi-user isolation (not in brief).
- Next: gates (uv lock, ruff/mypy/pytest), then PR B documents API.

### 2026-10-29

- PR A backend scaffold: `app/main.py` (factory + lifespan), `app/api/v1/health.py` (`/health` liveness, `/ready` DB+Redis with 2s/1s timeouts, 503 on fail), `app/workers/celery_app.py` (queues ingest/ocr/extract/index, acks-late, prefetch=1), `app/workers/tasks.py` stub, Alembic init wired to `Settings.database_url` (no revision yet — no models), `backend/Dockerfile` (python:3.11.11-slim, uv 0.6.14, non-root), `docker-compose.yml` (pgvector/pg16, redis:7.2.5-alpine, api, worker; frontend deferred).
- Fixed README local-dev section: uv commands replace nonexistent `requirements.txt`; API table gains `/health`, `/ready`.
- Committed previously untracked scaffold: `pyproject.toml`, `uv.lock`, `app/core/{config,logging}.py`, `.env.example`, `.github/workflows/ci.yml`, tests.
- mypy: added `plugins = ["pydantic.mypy"]`; tests switched to `Settings.model_validate` (typed-splat + `_env_file` kwargs failed strict mypy).
- Verified (real output): `ruff format --check` pass; `ruff check` pass; `mypy` "Success: no issues found in 22 source files"; `pytest -v --cov=app` **14 passed**, TOTAL cover 81%. health.py `_check_database`/`_check_redis` bodies untested in unit tests (mocked at router); real-dependency path needs integration test against live postgres/redis — not verified.
- Not verified: Docker image build, compose bring-up, Alembic against live DB, worker boot.
- Next: PR B auth (login, JWT middleware) or integration tests for ready probes.

## Known issues and limitations

- No ORM models or migrations yet; Alembic initialized with `target_metadata = None`.
- `/ready` unit tests mock DB/Redis; no integration test with live services.
- `docker-compose.yml` not built/run yet; frontend service absent (no Next.js app).
- Worker container has no tasks; `celery_app` imported at module load requires env (compose supplies it).
- `*.csv`/`*.xlsx` in `.gitignore` will block committed test fixtures unless negated later.
- Docker images use tags, not digests (digest pinning deferred).

## Decisions

- Layout follows AGENTS.md §7 (strict layering api → services → repositories → models).
- **No authentication.** Brief mandates "strong security" but defines no users/login; JWT was an AGENTS.md addition, removed 2026-10-29 to protect the 5-day budget for brief Tasks 1–7. Security = input validation, rate limits, secret hygiene. AGENTS.md updated to match.
- App built via `create_app()` factory; uvicorn `--factory` form so settings validation fails at process boot.
- Celery broker/backend both Redis; queue isolation now, routing added with first real tasks.
- Alembic URL comes from `app.core.config.Settings`, never from `alembic.ini`.
- `Settings` constructed in tests via `model_validate` (no env/dotenv side effects).
