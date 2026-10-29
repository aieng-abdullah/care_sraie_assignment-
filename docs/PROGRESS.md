# Progress

Source of truth for project status. Update after every task/session, same commit as related code.

## Status board

| Task | Deliverable | Status |
|------|-------------|--------|
| 1 | Backend scaffold: config, logging, health probes, Celery app, Alembic, Docker | Done |
| 2 | Documents API (upload, status, results, search, corrections, reprocess) | In progress — upload/list/status done; result/corrections/reprocess/search pending |
| 3 | PDF / image pipelines (page-parallel OCR + text extraction) | Not started |
| 4 | Excel / CSV pipelines | Not started |
| 5 | LLM extraction + grounding + validation rules | Not started |
| 6 | Frontend (Next.js): upload, monitor, inspect, review, correct, search | Not started |
| 7 | Evaluation dataset, metrics, report | Not started |

## Daily log

### 2026-10-29 (PR B: documents API part 1)

- Data layer: ORM models for all 8 core tables (`documents`, `pages`, `extractions`, `line_items`, `validation_issues`, `corrections`, `processing_events`, `reconciliations`) with NUMERIC(18,4) money, indexes per schema doc; `app/core/database.py` (engine/session/Base, SQLite support for tests).
- Migration `0001_initial` written manually (no local Postgres/Docker). Verified offline: `alembic upgrade head --sql` renders 9 CREATE TABLE + 13 indexes; `downgrade 0001_initial:base --sql` renders 8 DROP TABLE. **Not executed against a live PostgreSQL — unverified.**
- Endpoints: `POST /api/v1/documents` (multi-file: magic-byte detection, size cap, sha256 dedupe, filename sanitization, xlsx archive verification, per-item errors, 429 rate limit), `GET /api/v1/documents` (paginated, `q`/`status` filters), `GET /api/v1/documents/{id}/status` (page progress).
- Layers: `services/{documents,file_validation}.py`, `repositories/documents.py`, `schemas/document.py`, `api/v1/documents.py`; in-memory fixed-window rate limiter (`core/rate_limit.py`, single-process — documented limitation).
- Verified (real output): `ruff format --check` pass; `ruff check` pass; `mypy` "Success: no issues found in 36 source files"; `pytest -v --cov=app` **35 passed**, TOTAL 92%.
- Tests run against per-test SQLite files, not PostgreSQL — pg-specific DDL (partial index `postgresql_where`, timezone behavior under pg) not runtime-verified. CSV UTF-8 boundary trim heuristic covered by tests; filename `ILIKE %q%` filter has no supporting pg index yet (needs pg_trgm at Task 5 search).
- No Celery enqueue yet: upload stores `status=queued` in DB only; wiring enqueue to the pipeline lands with Task 1 (no silent stub per AGENTS §3).
- Next: Task 1 pipelines (PDF/image/spreadsheet processing + worker enqueue), then result/validation endpoints.

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

- **Upload does not enqueue Celery work yet**: documents stay `status=queued` until the Task 1 pipeline PR adds the parent job (intentional — no silent stubs).
- **Migration `0001_initial` never executed against live PostgreSQL** (no Docker/PG in dev env); only offline `--sql` rendering verified. Tests run on SQLite — pg-specific behavior (partial index, tz) unverified.
- **Rate limiter is in-process memory**: resets on restart, counts per replica; acceptable single-instance, not multi-replica (NFR scalability caveat).
- **`filename ILIKE '%q%'` list filter is unindexed** (would need pg_trgm GIN) — defer to Task 5 search work.
- Rate-limit and file-validation tests cover unit paths; `/ready` real-dependency path still needs integration test against live postgres/redis.
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
