# AI-Assisted Development Disclosure

Record which parts of the project were AI-assisted and the prompts used (development and product features, including the extraction prompt). Be accurate and complete.

## AI-assisted work

| Date | Scope | Tool/model | Notes |
|------|-------|------------|-------|
| 2026-10-28 | Repo init, AGENTS.md, folder skeleton | OpenCode (mimo-v2.6-flash-free) | Structure only; no product logic |
| 2026-10-28 | `docs/architecture.md`, `docs/database_schema.md`, README | OpenCode (mimo-v2.6-flash-free) | Design specs written by AI from assignment brief + AGENTS.md; user reviewed via plan |
| 2026-10-29 | Backend scaffold: config, logging, health probes, Celery app, Docker, CI (PR #5) | OpenCode (mimo-v2.6-flash-free) | User chose scope; gates run locally, results pasted in PR |
| 2026-10-29 | Auth removal decision + code/docs changes | OpenCode (mimo-v2.6-flash-free) | User compared assignment brief vs AGENTS.md and chose option 2 |
| 2026-10-29 | Data layer + documents API (upload/list/status, models, migration, tests) | OpenCode (mimo-v2.6-flash-free) | Feature built from schema doc; user directed "PR B documents API" |

## Prompts used

### Development

- Init GitHub repo `aieng-abdullah/care_sraie_assignment-` with README.
- Create/update `AGENTS.md` from provided specification.
- Build folder structure per AGENTS.md §7.
- Write detailed `docs/architecture.md` with diagrams (Mermaid, every flow) and `docs/database_schema.md` (separate schema doc) — format/scope decided by user in Q&A.
- "yes" → backend scaffolding (pyproject/config/.env.example/docker/health) per proposed plan.
- Paste of full assignment brief → check whether auth is required (answer: no; strong security only).
- "2" → drop JWT auth layer, update AGENTS.md and docs to match.
- "yes" → PR B: documents API (models, Alembic migration, upload/list/status endpoints, rate limit, tests).

### Product features

- TBD (extraction prompt to be added here when implemented).
