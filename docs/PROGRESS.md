# Progress

Source of truth for project status. Update after every task/session, same commit as related code.

## Status board

| Task | Deliverable | Status |
|------|-------------|--------|
| 1 | | Not started |
| 2 | | Not started |
| 3 | | Not started |
| 4 | | Not started |
| 5 | | Not started |
| 6 | | Not started |
| 7 | | Not started |

## Daily log

### 2026-10-28 (later)

- Wrote `docs/architecture.md`: context/container/layering diagrams, ingestion and PDF fan-out flowcharts, 8 sequence diagrams (upload, PDF extract, reconciliation, correction, auth, reprocess, search, failure paths), security and deployment topology, decision table. Mermaid, GitHub-renderable.
- Wrote `docs/database_schema.md`: full ER diagram, per-table columns/types/indexes, pgvector notes, Alembic migration rules, money=NUMERIC rules. Fixes broken README link.
- Verified: docs reviewed for Mermaid/Markdown structure; not rendered locally (no mmdc). No code run — docs only.
- Next: backend scaffolding (pyproject, app.core.config, .env.example, docker-compose), first API health endpoint.

### 2026-10-28

- Created repo skeleton: `backend/app/{api,core,models,schemas,services,repositories,pipelines,extraction,validation,workers}`, `backend/{tests,evaluation}`, `frontend/`, `docs/`.
- Verified: directory tree only; no code run.
- Next: define assignment tasks 1–7 on status board; add `.env.example`, docker-compose, backend deps.

## Known issues and limitations

- Skeleton only; no application code, tests, or CI yet.
- `docs/architecture.md` and `docs/database_schema.md` are design specs for unimplemented code — nothing runtime-verified.
- Mermaid diagrams not rendered locally (no renderer installed); verified by structure review only.

## Decisions

- Layout follows AGENTS.md §7 (strict layering api → services → repositories → models).
