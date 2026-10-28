# Architecture

Design specification for **DocIntel**, the AI-Powered Document Intelligence System.
Describes intended architecture; no application code exists yet, so nothing here is runtime-verified.
Full table definitions: [`database_schema.md`](database_schema.md).

## 1. Overview and requirements

Ingests digital and scanned PDFs (up to ~1000 pages), images, Excel and CSV files; extracts structured invoice data with an LLM; validates and cross-verifies documents; serves results through a REST API and a web UI.

| Requirement | Architectural response |
|---|---|
| ~1000-page PDFs | Per-page parallel Celery tasks; never load a file whole into memory |
| Low latency on the request path | All heavy work (OCR, LLM, embeddings) runs in background workers |
| Reliability | Idempotent jobs, retries with backoff, dead-letter path, recorded failures |
| No invented values | Grounding check against source text; `null` + confidence instead of guesses |
| Scalability | Stateless services; state in PostgreSQL/Redis; workers scale horizontally |
| Security | Magic-byte upload validation, JWT auth, parameterized ORM queries, untrusted LLM output |

## 2. System context

```mermaid
flowchart LR
    U[User] -->|browser| UI[Next.js Web UI]
    UI -->|HTTPS JSON| API[FastAPI REST API]
    API -->|structured output| LLM[External LLM Provider]
    API -->|SQL| DB[(PostgreSQL + pgvector)]
    API -->|enqueue / progress| R[(Redis)]
    W[Celery Workers] -->|poll| R
    W -->|OCR / parse / extract| FS[(Upload volume)]
    W -->|structured output| LLM
    W -->|SQL| DB
```

External dependencies: LLM provider API (over the network), PostgreSQL, Redis, filesystem (or object storage in production) for uploaded files.

## 3. Containers

```mermaid
flowchart TB
    subgraph client [Client]
        UI[frontend: Next.js + Tailwind<br/>upload, monitor, inspect, review, correct, search]
    end

    subgraph backend [backend: FastAPI + Celery]
        API[app.api<br/>routes /api/v1/*]
        SVC[app.services<br/>business logic]
        PIPE[app.pipelines<br/>pdf / image / spreadsheet]
        EXT[app.extraction<br/>LLM prompts, grounding]
        VAL[app.validation<br/>rules, reconciliation]
        WK[app.workers<br/>Celery tasks]
    end

    subgraph data [State]
        DB[(PostgreSQL + pgvector)]
        R[(Redis broker + progress)]
        VOL[(uploads volume)]
    end

    UI -->|multipart + JSON| API
    API --> SVC
    SVC -->|write metadata| DB
    SVC -->|enqueue| R
    WK -->|consume| R
    WK --> PIPE --> EXT --> VAL
    WK --> DB
    WK --> VOL
    SVC -->|read results| DB
    API -->|results, progress, search| UI
```

| Container | Role | Entry point |
|---|---|---|
| Next.js UI | Six capabilities only: upload, monitor, inspect, review, correct, search | `frontend/` |
| FastAPI API | Auth, upload, query, correction, search endpoints; no heavy work in-request | `backend/app/main.py` (planned) |
| Celery workers | Pipeline execution, retries, progress events | `backend/app/workers/` |
| PostgreSQL + pgvector | Source of truth + vectors for semantic search | — |
| Redis | Celery broker + progress/event channel | — |
| Upload volume | Stored original files, per-page artifacts | configured path |

## 4. Backend layering and module map

Strict layering; no route business logic, no services touching HTTP objects.

```mermaid
flowchart TB
    subgraph layers [Request path]
        API[app.api<br/>route handlers] --> SVC[app.services]
        SVC --> REPO[app.repositories]
        REPO --> MOD[app.models<br/>SQLAlchemy ORM]
    end

    subgraph jobs [Background path]
        WK[app.workers<br/>Celery tasks] --> PIPE[app.pipelines]
        PIPE --> EXT[app.extraction]
        PIPE --> VAL[app.validation]
        WK --> REPO
    end

    CORE[app.core<br/>config, security, logging] -.->|imported by all| layers
    CORE -.-> jobs
    SCH[app.schemas<br/>Pydantic] -.->|validate boundaries| API
    SCH -.-> EXT
```

Rules:
- `api` → `services` → `repositories` → `models` only; never skip layers.
- Each pipeline stage (ingest, parse, OCR, extract, validate, index) is an independent module behind a clear interface.
- Swappable parts (OCR engine, LLM provider, vector store) hidden behind abstractions.
- Configuration only from `app.core.config` settings objects (env vars), never scattered constants.

## 5. Ingestion and routing

Uploads validated by **content (magic bytes)**, not extension. Size and page limits enforced before enqueue.

```mermaid
flowchart TB
    UP[POST /api/v1/documents<br/>multipart] --> SCAN[Sanitize filename<br/>check size limit]
    SCAN --> MAGIC[Magic-byte sniff]
    MAGIC -->|PDF| PDFH[store + create document rows<br/>status=queued]
    MAGIC -->|JPEG/PNG/TIFF| IMGH[store + enqueue image OCR task]
    MAGIC -->|XLSX/XLS/CSV| SPTH[store + enqueue spreadsheet task]
    MAGIC -->|unknown| REJ[415 Unsupported Media Type]
    PDFH --> Q[enqueue parent PDF job]
```

| Type | First stage |
|---|---|
| PDF | Open with PyMuPDF; detect page count vs `MAX_PDF_PAGES`; fan out per-page tasks (§6) |
| Image | OpenCV preprocess (deskew, denoise, binarize) → OCR engine |
| Spreadsheet | pandas + openpyxl/xlrd: multi-sheet parse, header detection → invoice records |

## 6. Large-PDF processing (per-page fan-out)

```mermaid
flowchart TB
    P0[Parent PDF task] --> SPLIT[Split into N page tasks<br/>idempotent by document_id+page_no]
    SPLIT --> P1[page 1] & P2[page 2] & PN[page N ...]
    P1 & P2 & PN --> TL{Text layer<br/>present?}
    TL -->|yes| TXT[PyMuPDF text extract]
    TL -->|no| OCR[Preprocess + OCR<br/>Tesseract / PaddleOCR]
    TXT & OCR --> SAVE[Save page text + per-page confidence<br/>update progress counter]
    SAVE --> GRP[Invoice boundary detection:<br/>group pages into invoice units]
    GRP --> BATCH[Batch: one LLM call per invoice]
    BATCH --> EXT[Extraction + grounding + schema]
    EXT --> VAL[Validation]
    VAL --> IDX[Embed + index]
    IDX --> DONE["document status: ok, needs_review, or failed"]
```

- Page tasks run in parallel across workers; a 1000-page file is 1000 small tasks, not one large job.
- Progress: atomic counter of completed pages stored in DB (`pages` rows + `processing_events`), surfaced as `412 / 1000`.
- LLM calls capped **per invoice**, not per page, to control cost and latency.
- Idempotency: re-running a page task overwrites the same `pages` row; safe on retry.

## 7. Extraction and grounding

```mermaid
flowchart LR
    TXT[Grouped page text<br/>untrusted] --> PR[Prompt assembly<br/>document text + JSON schema]
    PR --> LLM[LLM API<br/>structured output]
    LLM --> PYD[Pydantic validate<br/>strict Invoice schema]
    PYD -->|malformed| RETRY[retry then fail gracefully<br/>status=failed, error recorded]
    PYD -->|ok| GRD[Grounding check:<br/>each value must appear in source text]
    GRD -->|ungrounded| NULL[null field + flag issue<br/>never guess]
    GRD -->|grounded| CONF[attach confidence +<br/>source_snippet per field]
    CONF --> OUT[extraction row<br/>Decimal money, nulls preserved]
```

- Missing/uncertain fields are `null` with confidence `0`, never invented (AGENTS.md §2.4).
- Money parsed to `Decimal`; floats forbidden.
- LLM output treated as untrusted: schema-validated, prompt-injection aware (document text never interpreted as instructions).

## 8. Validation and reconciliation

```mermaid
flowchart TB
    EX[Extraction] --> R1{Required fields<br/>present?}
    R1 --> ISS[validation_issues rows]
    R1 --> R2{subtotal + tax<br/>≈ total?}
    R2 --> ISS
    R2 --> R3{Σ line items<br/>≈ subtotal?}
    R3 --> ISS
    R3 --> R4{Dates, currency,<br/>tax rate plausible?}
    R4 --> ISS
    R4 --> R5{Duplicate?<br/>hash or supplier+number+total}
    R5 --> ISS
    R5 --> R6{Low confidence<br/>any critical field?}
    R6 --> ISS
    R6 --> ST{Final status}
    ISS --> ST
    ST -->|no errors, confidence ok| OK[ok]
    ST -->|warnings or low confidence| NR[needs_review]
    ST -->|processing failure| FL[failed]
```

Cross-document reconciliation (runs when related documents share supplier + invoice number, or on demand):

| Pair | Check |
|---|---|
| PDF vs PDF | Totals and line items for same invoice number |
| PDF vs Excel | PDF totals/line items vs ledger or PO rows matched by invoice number |

Results stored in `reconciliations` with per-field match/mismatch evidence.

## 9. Job lifecycle and queues

Document-level state machine:

```mermaid
stateDiagram-v2
    [*] --> queued: upload accepted
    queued --> processing: worker started
    processing --> processing: pages completed / retries
    processing --> ok: all checks passed
    processing --> needs_review: warnings or low confidence
    processing --> failed: unrecoverable or retries exhausted
    needs_review --> processing: reprocess after correction
    failed --> queued: manual reprocess
    ok --> [*]
```

Task-level rules:
- Queues: `ingest` (light routing), `ocr` (CPU-heavy), `extract` (LLM-bound), `index` (embeddings) — isolated so OCR backlog cannot starve extraction.
- Retries: exponential backoff + jitter, **only for idempotent tasks**; LLM timeouts and 429s handled gracefully.
- Dead-letter: retries exhausted → failure recorded in `processing_events`, document `failed`, reprocessable via API.
- Graceful shutdown: in-flight tasks finish or are requeued; temp files cleaned.

## 10. Sequence: upload → enqueue → monitor progress

```mermaid
sequenceDiagram
    actor U as User
    participant FE as Next.js UI
    participant API as FastAPI
    participant DB as PostgreSQL
    participant R as Redis
    participant W as Celery worker

    U->>FE: select multiple files
    FE->>API: POST /api/v1/auth/login
    API-->>FE: JWT
    FE->>API: POST /api/v1/documents (multipart, Bearer JWT)
    API->>API: magic-byte check, size/page limits, sanitize name
    API->>DB: INSERT documents (status=queued)
    API->>R: enqueue parent job (document_id)
    API-->>FE: 201 {document_id, status: queued}
    loop until terminal status
        FE->>API: GET /api/v1/documents/{id}/status (poll)
        API->>DB: read status + page progress
        API-->>FE: {status, pages_done, pages_total}
    end
    W->>R: claim task
    W->>DB: UPDATE status=processing, emit processing_events
    W-->>R: task complete (or retry / dead-letter)
```

## 11. Sequence: PDF fan-out → extract → validate

```mermaid
sequenceDiagram
    participant W as Parent task
    participant R as Redis
    participant PW as Page workers
    participant DB as PostgreSQL
    participant LLM as LLM API

    W->>DB: open PDF, count pages (vs MAX_PDF_PAGES)
    W->>R: enqueue page tasks 1..N (idempotent)
    par parallel page workers
        PW->>PW: text layer? extract : preprocess+OCR
        PW->>DB: UPSERT pages (text, confidence)
        PW->>DB: increment progress counter
    end
    W->>DB: group pages into invoice units (boundary detection)
    loop one call per invoice
        W->>LLM: extraction prompt + schema (timeout set)
        LLM-->>W: structured JSON
        W->>W: Pydantic validate + grounding check
        W->>DB: UPSERT extractions + line_items (Decimal)
    end
    W->>DB: run validation rules → validation_issues
    W->>DB: UPDATE document status (ok | needs_review | failed)
```

## 12. Sequence: cross-document reconciliation

```mermaid
sequenceDiagram
    participant API as FastAPI
    participant SVC as services.reconciliation
    participant DB as PostgreSQL
    participant W as Celery worker

    Note over SVC,W: Triggered automatically after extraction,<br/>or via GET /api/v1/reconciliations
    SVC->>DB: find candidate pairs (same supplier + invoice number,<br/>or explicit PDF–Excel link)
    SVC->>W: enqueue reconciliation task
    W->>DB: load extractions + line items for both sides
    W->>W: compare totals, currency, line items (Decimal, tolerance)
    W->>DB: INSERT reconciliations (match/mismatch + evidence)
    W->>DB: INSERT validation_issues on mismatch
    API->>DB: GET /api/v1/reconciliations
    DB-->>API: rows
    API-->>Client: reconciliation results
```

## 13. Sequence: manual correction → re-validate → audit

```mermaid
sequenceDiagram
    actor U as User
    participant FE as UI
    participant API as FastAPI
    participant DB as PostgreSQL
    participant W as Celery worker

    U->>FE: edit field on needs_review document
    FE->>API: PATCH /api/v1/documents/{id}/fields<br/>{field, new_value} (JWT)
    API->>API: validate value (schema, Decimal for money)
    API->>DB: insert corrections audit row (old, new, actor, timestamp)
    API->>DB: update extraction field
    API->>W: enqueue re-validation task
    W->>W: re-run validation rules (not full extraction)
    W->>DB: refresh validation_issues + document status
    FE->>API: GET /api/v1/documents/{id}/result
    API-->>FE: updated extraction + issues
    Note over DB: corrections table is append-only audit trail
```

## 14. Sequence: authentication

```mermaid
sequenceDiagram
    actor U as User
    participant FE as UI
    participant API as FastAPI
    participant DB as PostgreSQL

    U->>FE: credentials
    FE->>API: POST /api/v1/auth/login
    API->>DB: verify user + password hash
    API-->>FE: access token (JWT, short TTL)
    FE->>API: any protected route (Authorization: Bearer)
    API->>API: verify signature + expiry
    alt invalid / missing
        API-->>FE: 401 Unauthorized
    else valid
        API-->>FE: 200 response
    end
```

Every endpoint authenticated and authorized; rate limit applied on upload routes.

## 15. Sequence: reprocess failed job

```mermaid
sequenceDiagram
    actor U as User
    participant FE as UI
    participant API as FastAPI
    participant DB as PostgreSQL
    participant R as Redis
    participant W as Celery worker

    U->>FE: click reprocess
    FE->>API: POST /api/v1/documents/{id}/reprocess (JWT)
    API->>DB: check status in (failed, needs_review)
    API->>DB: status=queued, append processing_events (reprocess)
    API->>R: enqueue parent job
    API-->>FE: 202 {status: queued}
    W->>R: claim task (idempotent: overwrite prior page rows)
    W->>DB: status=processing → ok | needs_review | failed
```

## 16. Sequence: keyword and semantic search

```mermaid
sequenceDiagram
    actor U as User
    participant FE as UI
    participant API as FastAPI
    participant DB as PostgreSQL

    rect rgb(240,240,255)
    Note over FE,DB: Keyword path
    U->>FE: filters (q, status, supplier, date range)
    FE->>API: GET /api/v1/documents?q=...&status=... (paginated)
    API->>DB: parameterized WHERE on indexed columns
    DB-->>API: page of documents
    API-->>FE: {items, total, page, page_size}
    end

    rect rgb(240,255,240)
    Note over FE,DB: Semantic path
    U->>FE: semantic query
    FE->>API: POST /api/v1/search/semantic {query, limit}
    API->>DB: embed query (batched provider call)
    API->>DB: vector similarity search (pgvector, cosine)
    DB-->>API: ranked document/extraction matches
    API-->>FE: [{document_id, score, snippet}]
    end
```

## 17. Sequence: failure paths (corrupted file, LLM timeout, malformed output)

```mermaid
sequenceDiagram
    participant W as Worker
    participant DB as PostgreSQL
    participant LLM as LLM API
    participant R as Redis

    alt Corrupted / unreadable file
        W->>W: parser raises specific exception
        W->>DB: INSERT processing_events (failed, reason)
        W->>DB: document status=failed
        Note over W: worker does not crash, temp files cleaned
    else LLM timeout or 429
        W->>LLM: request (explicit timeout)
        LLM--xW: TimeoutError / rate limit
        W->>R: retry with backoff + jitter (idempotent)
        alt retries exhausted
            W->>DB: status=failed, event logged
            Note over DB: reprocessable via API
        end
    else Malformed LLM output
        W->>W: Pydantic ValidationError
        W->>R: retry (temperature/provider may differ)
        alt still malformed
            W->>DB: status=failed, reason=malformed_extraction
        end
    end
```

## 18. Search architecture

```mermaid
flowchart LR
    subgraph write [Write path]
        EX[Extractions] --> EM[Embedding task<br/>batched]
        EM --> V[(pgvector column<br/>embeddings)]
    end
    subgraph read [Read path]
        Q[Search query] --> KW[Keyword: indexed ILIKE / FTS<br/>supplier, invoice number, snippets]
        Q --> SE[Semantic: embed query<br/>cosine similarity]
        KW --> M[merged, paginated results]
        SE --> M
    end
    V --> SE
```

- Keyword filters hit DB indexes only; no scan of unindexed text columns.
- Embeddings built in background after extraction; never in the request path.
- All list endpoints paginated.

## 19. Security architecture

```mermaid
flowchart TB
    subgraph edge [Edge]
        TLS[HTTPS assumed in front]
        CORS[Restrictive CORS]
        HDR[Security headers]
        RL[Upload rate limit]
    end
    subgraph api [API]
        JWT[JWT authz on every route]
        MV[Pydantic request validation]
        ORM[ORM parameterized queries only]
    end
    subgraph worker [Worker / data]
        MB[Magic-byte type check<br/>size + page caps]
        FN[Filename sanitization<br/>never trust client paths]
        UN[LLM output + OCR text = untrusted<br/>schema + grounding]
        NL[No PII / document text / secrets in logs]
        ENV[Secrets via env only<br/>.env never committed]
    end
    edge --> api --> worker
```

Privacy: document text is sent to an external LLM API — flagged in README; zero-retention or self-hosted model for sensitive data.

## 20. Deployment topology

```mermaid
flowchart TB
    subgraph compose [docker compose]
        FE[frontend :3000]
        API[backend API :8000<br/>uvicorn, non-root image]
        WK1[worker: ocr scale N]
        WK2[worker: extract scale M]
        PG[(postgres :5432<br/>pgvector)]
        RD[(redis :6379)]
        VOL[uploads volume]
    end
    User --> FE
    User --> API
    FE --> API
    API --> PG
    API --> RD
    WK1 --> RD
    WK2 --> RD
    WK1 --> PG
    WK2 --> PG
    WK1 --> VOL
    WK2 --> VOL
```

- `docker compose up` works from a clean clone; dependency versions pinned.
- Config: env vars validated at startup (fail fast); `.env.example` tracked, `.env` never.
- Health: `/health` (liveness), `/ready` (DB, Redis, queue reachable); basic metrics (queue depth, job duration, failure rate).
- DB schema changes only via versioned, reversible Alembic migrations.

## 21. Scalability notes

| Concern | Response |
|---|---|
| CPU-bound OCR | Dedicated `ocr` queue; horizontal worker replicas |
| LLM rate limits / cost | Per-invoice calls, batching, cache identical documents by hash, token/cost tracking per document |
| Memory | Page-level tasks; streaming PDF open; no full-file loads |
| DB growth | Indexes on every filtered column; paginated lists; avoid N+1 via repositories |
| Hot document updates | Progress writes batched/atomic; single-writer per document parent task |

## 22. Decision and trade-off table

| Decision | Rationale | Trade-off |
|---|---|---|
| Python for backend | OCR, pandas, LLM libs are Python-native | Single language beats suggested NestJS split for this scope |
| PostgreSQL + pgvector | Relational + JSONB + vectors in one store | Dedicated vector DB scales further at extreme volume |
| Celery + Redis | Mature retries, routing, concurrency control | Heavier than minimal queues |
| Per-page parallelism | ~1000-page PDFs without memory blowup | Orchestration complexity |
| Grounding check | Blocks invented values | Can null valid values when OCR is poor |
| `Decimal` / `NUMERIC` for money | No float rounding errors | Care required at JSON/DB boundaries |
| LLM per invoice, not per page | Cost and latency control | Invoice boundary detection must be reliable |

## Related documents

- [`database_schema.md`](database_schema.md) — full tables, columns, indexes, ER diagram
- [`../README.md`](../README.md) — overview, API table, quick start
- [`PROGRESS.md`](PROGRESS.md) — status board and daily log
- [`ai_disclosure.md`](ai_disclosure.md) — AI-assisted development record
