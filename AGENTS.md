# AGENTS.md

Rules for any AI coding agent (Claude Code, Cursor, Copilot, etc.) working in this repository.
Read this file fully before making changes. If a rule here conflicts with a request, stop and ask.

## 1. Project Context

**AI-Powered Document Intelligence System**: ingests PDFs (up to ~1000 pages), images, Excel and CSV files, extracts structured invoice data, validates it, cross-verifies documents (PDF-PDF, PDF-Excel), and exposes results through a REST API and web UI.

**Stack:** FastAPI, Celery + Redis, PostgreSQL + pgvector, PyMuPDF, PaddleOCR/Tesseract + OpenCV, pandas/openpyxl, LLM API (structured output), Next.js + Tailwind, docker-compose.

**Assignment deliverables (all must be present at submission):**
1. Git repository with source code
2. README and setup instructions
3. Architecture diagram and database schema
4. Working backend API and frontend
5. PDF, image, Excel, and CSV processing pipelines
6. Automated tests and test results
7. Evaluation report with actual measured metrics
8. Recorded walkthrough of the working application
9. AI prompts and disclosure of AI-assisted development

The brief also requires smooth performance, high speed, scalability, reliability, and strong security.

### 1.1 Non-Functional Requirements (hard gates)

Every change must preserve these. A PR that weakens one of them without saying so in "Impact and risks" is not mergeable.

| NFR | Invariant |
|---|---|
| Performance | No OCR/LLM/embedding/disk-heavy work in the request path — enqueue only. Every filtered/searched column is indexed. Every list endpoint is paginated. No N+1 queries. |
| Speed | Upload/status endpoints return in milliseconds. Large PDFs process page-by-page in parallel. LLM calls capped per invoice, never per page. |
| Scalability | Stateless services; state only in PostgreSQL/Redis. Workers scale horizontally (`docker compose up --scale worker=N`). Page jobs idempotent. Queue isolation: separate `ocr` (CPU), `extract` (LLM-bound), `index` (embeddings) queues so one backlog cannot starve the others. |
| Reliability | Explicit timeout on every external call (LLM, DB, Redis, OCR). Retries with backoff+jitter only for idempotent jobs, plus dead-letter and reprocess path. Corrupted input fails gracefully without crashing workers. Transactions on multi-step writes. |
| Security | Magic-byte upload checks, size/page caps, sanitized filenames. ORM parameterized queries only. LLM/OCR output untrusted (schema + grounding). Secrets via env only, never logged. No PII/document text in logs. Pinned non-root Docker images. |

## 2. Hard Prohibitions (never do these)

1. **Never edit, overwrite, delete, or commit `.env` or any secrets file without explicit permission.** Changes go in `.env.example` (placeholders only). If a new variable is needed, add it to `.env.example` and tell the user.
2. **Never lie, and never show fake confidence.** Do not claim code works, tests pass, or metrics are achieved unless you actually ran it and saw the output. If you did not run it, say "not verified."
3. **Never invent data.** No fabricated metrics, accuracy numbers, benchmark results, sample outputs, or dataset labels. Evaluation numbers must come from a real run.
4. **Never invent extracted values** in the product itself: missing or uncertain fields are `null` with a confidence score, never guessed.
5. **Never hard-code secrets, API keys, tokens, or credentials**, even temporarily.
6. **Never silence errors** (empty `except`, `pass`, swallowed exceptions) or disable/skip/delete tests to make a build pass.
7. **Never run destructive commands** (`rm -rf`, `DROP TABLE`, `git push --force`, `git reset --hard`, volume deletion) without explicit permission.
8. **Never add a dependency** without stating why, and prefer the standard library or an existing dependency first.
9. **Never use floats for money.** Use `Decimal` (Python) and string/decimal types in JSON and DB (`NUMERIC`).
10. **Never log PII, document contents, or API keys.**

## 3. Honesty and Reporting

- State clearly what was changed, what was run, and what was **not** verified.
- If a task is only partly done, say so. Do not present a stub as a finished feature.
- If uncertain about requirements, a library's behavior, or an API, say so and ask rather than guess.
- Report failures plainly, including failing tests and their output.
- Mark placeholders and TODOs explicitly (`TODO(name): reason`); never leave silent fakes or mocked behavior in production paths.

## 4. Git Hygiene

- **Branches:** one branch per task, named `type/short-description` (e.g. `feat/ocr-pipeline`, `fix/duplicate-detection`). Never commit directly to `main`.
- **Commits:** small, atomic, one logical change each. Use Conventional Commits:
  `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`, `perf:`, `ci:`
  Format: `type(scope): imperative summary` (max ~72 chars), with a body explaining *why* when not obvious.
  Example: `feat(validation): add subtotal vs line-items consistency check`
- **Never commit:** `.env`, credentials, uploaded documents, large binaries, model weights, `__pycache__`, `node_modules`, build output, logs. Keep `.gitignore` current.
- **Before every commit:** run formatter, linter, type check, and the relevant tests. Review `git diff` and `git status`; no unrelated changes, no debug prints, no commented-out code.
- **No history rewriting** on shared branches. No force-push unless explicitly approved.
- **Pull requests:** every change reaches `main` through a PR. See the PR rules below.

### Writing Pull Requests

**Size and scope**
- One PR = one feature or fix. Keep it focused and reviewable (aim for under ~400 changed lines, excluding lockfiles and generated files). Split large work into stacked PRs.
- No unrelated refactors, formatting churn, or drive-by changes in a feature PR.
- Open a PR only when the code runs, tests pass, and lint/type checks are green. Use a **Draft PR** for work in progress.

**Title**
- Use Conventional Commit format: `type(scope): imperative summary`, max ~72 chars.
- Example: `feat(pipelines): add per-page parallel PDF processing`

**Description (use this template)**

```markdown
## Summary
What this PR does and why, in 2-4 sentences.

## Changes
- Bullet list of the main changes, grouped by module.

## How to test
Exact commands and steps a reviewer can run.

## Test results
Paste the real output (pass/fail counts, coverage). If something was not run, say "not run" and why.

## Verification status
- [ ] Tests pass locally
- [ ] Lint, format, and type checks pass
- [ ] Verified manually (describe how), or state "not verified"

## Impact and risks
Migrations, new env vars, new dependencies, breaking changes, performance or security implications.

## Known limitations / TODOs
Anything incomplete, stubbed, or deferred. Be explicit.

## Docs
- [ ] README / docs updated if behavior or setup changed
- [ ] `docs/PROGRESS.md` updated
- [ ] `docs/ai_disclosure.md` updated if AI-assisted
```

**Honesty rules for PRs**
- Never claim tests pass, features work, or metrics are achieved unless you ran them and saw the output. Paste actual results, not summaries from memory.
- Disclose limitations, stubs, and failing or skipped tests. Never hide them.
- List every new dependency with the reason, and every new or changed environment variable (added to `.env.example`, never `.env`).
- Call out database migrations and whether they are reversible.
- Do not include secrets, real documents, or PII in the description, screenshots, or logs.

**Before opening and merging**
- Rebase or merge the latest `main` and resolve conflicts cleanly.
- Self-review the full diff: no debug prints, commented-out code, stray files, or accidental `.env` changes.
- Confirm file-level and single-line docstrings are present on all new files, classes, and functions.
- Merge only when CI is green. Prefer **squash merge** so `main` keeps one clean Conventional Commit per PR, then delete the branch.
- Never force-push to `main`, and never merge a red build.
- **Datasets:** commit only the generator scripts and small fixtures; large generated data is reproducible via script, not stored in git.

## 5. Code Quality Standards

### 5.1 Docstrings and Comments (mandatory)

**Every source file starts with a file-level docstring/comment** describing what the file is for and its role in the system.

**Every class and function has a single-line docstring.** One line only. No multi-line essays.

Python:

```python
"""Validation rules that check invoice totals, line items, and required fields."""

from decimal import Decimal


class InvoiceValidator:
    """Runs all validation rules against an extracted invoice."""

    def check_total(self, subtotal: Decimal, tax: Decimal, total: Decimal) -> bool:
        """Return True if subtotal plus tax equals total within rounding tolerance."""
        ...
```

TypeScript / React:

```ts
/** Upload form that sends multiple documents to the API and shows progress. */

/** Return the display label for a document processing status. */
export function statusLabel(status: DocumentStatus): string { ... }
```

- Comments explain *why*, not *what*. Remove dead code instead of commenting it out.
- Public functions have full type hints (Python) or explicit types (TypeScript). No `any` without justification.

### 5.2 Style and Tooling

- **Python:** `ruff` (lint + format), `mypy` (strict where practical), `pytest`. PEP 8, max line length 100.
- **TypeScript:** `eslint`, `prettier`, `tsc --noEmit`, strict mode on.
- Functions do one thing and stay short (aim under ~40 lines). Avoid deep nesting; use early returns.
- No magic numbers or strings: use named constants or config.
- Use Pydantic models for all request, response, and LLM output schemas. Validate at boundaries.
- Handle errors with specific exception types and meaningful messages. Fail gracefully on corrupted files and record the failure in processing history.

## 6. Architecture Principles

### 6.1 Scalability

- Treat every heavy operation (OCR, LLM calls, embeddings) as a **background job**, never in the request path.
- Process large PDFs **page by page in parallel tasks**; never load a 1000-page file fully into memory. Stream and batch.
- Jobs must be **idempotent** with retries, backoff, and a dead-letter path.
- Keep services **stateless** so workers can scale horizontally. State lives in PostgreSQL/Redis.
- Paginate every list endpoint. Add DB indexes for every filtered/searched column. Avoid N+1 queries.
- Batch LLM and embedding calls; cap calls per invoice, not per page.
- Keep OCR, extraction, and indexing on separate Celery queues (`ocr`, `extract`, `index`) so a CPU-heavy backlog cannot starve LLM-bound work or vice versa.
- Before adding a feature, ask: what happens at 10x the load? Answer that question in the PR description under "Impact and risks".

### 6.2 Modularity

- Strict layering: `api` (routes) -> `services` (business logic) -> `repositories` (DB access) -> `models`. Routes contain no business logic; services do not touch HTTP objects.
- Each pipeline stage (ingest, parse, OCR, extract, validate, index) is an independent, testable module behind a clear interface.
- Depend on abstractions for swappable parts (OCR engine, LLM provider, vector store) so they can be replaced without touching callers.
- No circular imports, no god files, no copy-paste duplication. Extract shared logic.
- Configuration comes only from environment/settings objects, never scattered constants.

### 6.3 Security

- Validate uploads by **content (magic bytes)**, not extension; enforce size and page limits; sanitize filenames; never trust client-provided paths.
- Rate-limit uploads. (No auth layer: brief requires "strong security" but no user accounts; decision recorded in `docs/PROGRESS.md`.)
- Parameterized queries only (use the ORM). No string-built SQL.
- Treat LLM output and OCR text as **untrusted input**; validate against schemas and guard against prompt injection from document content.
- Note PII exposure when sending document text to external LLM APIs.

### 6.4 Frontend Scope (Task 6)

The brief asks for a **simple React or Next.js interface**. Build exactly these six capabilities, nothing more:

1. **Upload** multiple documents at once
2. **Monitor** processing progress (per document, with page progress for large PDFs)
3. **Inspect** extracted information
4. **Review** validation errors
5. **Correct** extracted values (calls the correction endpoint, which re-runs validation)
6. **Search** previously processed documents (keyword filters and semantic search)

Rules:
- Keep it simple and functional. No extra pages, dashboards, analytics, theming systems, or animations beyond what these six need.
- Show real data from the API. Never hard-code or mock results in the UI.
- Show loading, empty, and error states. Display low-confidence and `null` fields clearly, and never fill them in on the client.
- Use a typed API client (TypeScript) and keep components small and reusable.

## 7. Naming and Structure (professional conventions)

- **Python files/modules:** `snake_case.py`, descriptive nouns: `invoice_validator.py`, `ocr_engine.py`, `spreadsheet_parser.py`. Not `utils2.py`, `temp.py`, `new_final.py`.
- **Classes:** `PascalCase`. **Functions/variables:** `snake_case`. **Constants:** `UPPER_SNAKE_CASE`.
- **React components:** `PascalCase.tsx` (`DocumentTable.tsx`). Hooks: `useXxx.ts`. Other TS files: `kebab-case.ts`.
- **Tests:** mirror source layout, named `test_<module>.py`; test names describe behavior (`test_total_mismatch_is_flagged`).
- **API routes:** plural nouns, lowercase, versioned (`/api/v1/documents`).
- **DB:** `snake_case` plural tables, singular columns, migrations via Alembic only. Never edit the schema by hand.
- Suggested layout:

```
backend/
  app/
    api/            # route handlers
    core/           # config, security, logging
    models/         # ORM models
    schemas/        # Pydantic schemas
    services/       # business logic
    repositories/   # DB access
    pipelines/      # pdf, image, spreadsheet processing
    extraction/     # LLM prompts, schema, grounding checks
    validation/     # rules engine, reconciliation
    workers/        # background tasks
  tests/
  evaluation/       # dataset generator, metrics scripts
frontend/
docs/               # architecture, schema, evaluation report, AI disclosure
```

## 8. Testing and Evaluation

- Every new feature or bug fix ships with tests. Cover happy path, edge cases, and failure scenarios (corrupted file, empty file, bad OCR, LLM timeout, malformed LLM output).
- Tests must be deterministic: mock the LLM and external services in unit tests.
- Evaluation metrics (extraction accuracy, processing time, document success rate, failure rate) are produced **only by running the evaluation script** on the labeled dataset. Report real numbers, including bad ones.

## 9. AI-Assisted Development Disclosure

- Maintain a single file, `docs/ai_disclosure.md`, containing both: (1) which parts of the project were AI-assisted, and (2) the prompts used for development and product features (including the extraction prompt). Be accurate and complete.
- The developer must understand and be able to explain every line committed.

## 10. Production Readiness

The brief asks for smooth performance, high speed, scalability, reliability, and strong security. Performance and scalability are covered in 6.1, security in 6.3. In addition:

- **Configuration:** all settings come from environment variables, validated at startup. Provide `.env.example` only.
- **Reliability:** set explicit timeouts on external calls (LLM, DB, Redis, OCR). Retry only idempotent tasks, with backoff. Failed jobs are recorded and can be reprocessed. A corrupted file must fail gracefully without crashing the worker.
- **Logging:** structured logs of job lifecycle events (queued, started, retried, failed, done). Never log PII, document text, or secrets.
- **Limits:** cap upload size, page count, and concurrent jobs. Clean up temp files.
- **Data safety:** schema changes only through Alembic migrations. Use transactions for multi-step writes. Keep an audit trail for manual corrections.
- **Deployment:** `docker compose up` must work from a clean clone. Pin dependency versions.
- **Errors:** consistent error format and correct HTTP status codes. Never leak stack traces to clients.
- **CI gates:** lint, type check, tests, and a dependency vulnerability scan (`pip-audit` or `uv audit`) must pass. A red scan blocks merge.
- **Rate limits:** upload endpoints return 429 under abuse; limits configurable via env.
- **Measured numbers only:** any latency or throughput figure in a PR or report comes from a real run (p50/p95 measured), never an estimate.

## 11. Progress Tracking

- Maintain a single file, `docs/PROGRESS.md`, as the source of truth for project status. Update it at the end of every task or work session, in the same commit as the related code.
- Structure:
  - **Status board:** the 7 assignment tasks plus deliverables, each marked `Not started`, `In progress`, `Done`, or `Blocked`.
  - **Daily log:** dated entries (newest first) with what was done, what was verified (and how), and what is next.
  - **Known issues and limitations:** open bugs, shortcuts taken, and unverified areas.
  - **Decisions:** short notes on key design choices and why (feeds the README and architecture docs).
- Mark a task `Done` only when it meets the Definition of Done below. Never mark something done that was not run and verified.
- Keep entries factual and brief. Record failures and blockers as plainly as successes.

## 12. Definition of Done

A task is done only when all of these are true:

- [ ] Code runs and the relevant tests pass (output actually observed)
- [ ] Lint, format, and type checks pass
- [ ] File-level and function/class single-line docstrings are present
- [ ] No secrets, `.env` changes, or stray files in the diff
- [ ] Error and failure paths are handled
- [ ] Production concerns considered (config, logging, timeouts, limits, migrations)
- [ ] NFR gates (§1.1) checked for this change, or explicitly listed as "not verified": size/page limits enforced, request path free of heavy work, timeouts set
- [ ] PR written per the PR rules (clear description, real test output, limitations disclosed)
- [ ] Docs/README updated if behavior or setup changed
- [ ] `docs/PROGRESS.md` updated with status, verification, and next steps
- [ ] Summary written stating what was done and what remains unverified