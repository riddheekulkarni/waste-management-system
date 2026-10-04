# EcoClean Civic — Asynchronous AI Processing Architecture (Phase 3)

This document describes the Phase 3 asynchronous AI processing architecture, background worker dispatch system, canonical complaint lifecycle, failure isolation, and operational procedures for EcoClean Civic.

---

## 1. Overview & Architecture Diagram

Prior to Phase 3, the complaint submission endpoint held the citizen's HTTP request open until YOLOv8 bounding-box inference, overlap area union computation, duplicate detection, and department routing finished synchronously.

In Phase 3, the architecture decouples ingestion from heavy AI inference:

```text
[ Citizen / Web Client ]
       │
       ▼  (1) POST /api/complaints/upload
[ Flask Web API ]
       │
       ├─► (2) Create Complaint (Status: AI_PROCESSING, Stage: QUEUED)
       ├─► (3) Enqueue Job on Redis Queue ("complaints")
       │
       ▼  (4) HTTP 201 Created (Ticket ID returned in <25ms)
[ Citizen / Web Client ] (Polls /api/complaints/<ticket_id>/processing-status)

-------------------------------------------------------------------------
(Asynchronous Processing Pipeline)

[ Redis Broker (Queue: "complaints") ]
       │
       ▼  (5) Dequeue Job
[ Background AI Worker (worker.py) ]
       │
       ├─► (6) Verify Eligibility & Idempotency Lock
       ├─► (7) Stage: ANALYZING_IMAGE (YOLOv8 or Mock Demo inference)
       ├─► (8) Clean prior detection items & write new DetectionItem records
       ├─► (9) Stage: CALCULATING_SEVERITY (Exact sweep-line overlap-aware union)
       ├─► (10) Stage: CHECKING_DUPLICATES (50m proximity Haversine check)
       ├─► (11) Stage: ASSIGNING_DEPARTMENT (Dominant class ontology routing)
       ├─► (12) Stage: COMPLETED (Status: VERIFIED or DUPLICATE)
       │
       ▼  (13) Record duration_ms, timestamps, commit transaction
[ Relational Database (PostgreSQL / SQLite) ]
```

---

## 2. Canonical Complaint Lifecycle

EcoClean Civic defines a canonical lifecycle status machine (`backend/lifecycle.py`) supporting standard and exceptional states:

### Lifecycle States

| Status | Type | Description |
|---|---|---|
| `SUBMITTED` | Intermediate | Complaint payload received and validated. |
| `AI_PROCESSING` | Intermediate | Complaint ticket created; background job active in AI queue. |
| `VERIFIED` | Standard | AI analysis completed, severity computed, department assigned. |
| `ASSIGNED` | Standard | Complaint dispatched to departmental field crew. |
| `IN_PROGRESS` | Standard | Municipal sanitation team is on-site actively clearing waste. |
| `RESOLUTION_SUBMITTED` | Standard | Field crew submitted completion proof and clearance photos. |
| `RESOLVED` | Final | Closed out following municipal supervisor verification. |
| `PROCESSING_FAILED` | Exceptional | AI model or decoding failed; eligible for admin retry. |
| `DUPLICATE` | Exceptional | Nearby open ticket found within 50m; linked to parent. |
| `REJECTED` | Exceptional | Spurious, unreadable, or invalid citizen report. |
| `NEEDS_INFORMATION` | Exceptional | Awaiting clarifying photos or location details from citizen. |

### Valid Transitions

```text
SUBMITTED ─────────► AI_PROCESSING ─────────► VERIFIED ─────────► ASSIGNED ─────────► IN_PROGRESS ─────────► RESOLUTION_SUBMITTED ─────────► RESOLVED
                         │                       ▲                     │                     │
                         ├─► DUPLICATE ──────────┤                     ├─► REJECTED          ├─► RESOLVED
                         │                       │                     │                     │
                         └─► PROCESSING_FAILED   │                     └─► NEEDS_INFO ◄──────┘
                                  │ (Retry)      │
                                  └──────────────┘
```

---

## 3. Background Job Processing Stages

Within the `AI_PROCESSING` status, the background worker reports fine-grained progress via `processing_status`:

1. `QUEUED`: Job is waiting in Redis for an available worker thread.
2. `ANALYZING_IMAGE`: YOLOv8 model running inference against uploaded image.
3. `CALCULATING_SEVERITY`: Computing bounding-box union coverage ratio and count.
4. `CHECKING_DUPLICATES`: Querying database for open complaints within 50 meters.
5. `ASSIGNING_DEPARTMENT`: Mapping canonical classes to municipal department.
6. `COMPLETED`: Processing finished successfully (`status = VERIFIED` or `DUPLICATE`).
7. `FAILED`: Processing failed (`status = PROCESSING_FAILED`).

Citizens and admins inspect this via `GET /api/complaints/<ticket_id>/processing-status`:

```json
{
  "ticket_id": "8a3f91bc",
  "status": "AI_PROCESSING",
  "processing_status": "ANALYZING_IMAGE",
  "stage": "ANALYZING_IMAGE",
  "progress": "Analyzing uploaded image",
  "ai_mode": "REAL_YOLO",
  "duration_ms": null,
  "retry_count": 0,
  "error": null
}
```

---

## 4. Idempotency & Concurrency Safety

To prevent duplicate execution or race conditions:
1. **Worker Stage Lock**: When a worker begins processing, it sets `processing_status = ANALYZING_IMAGE` and records `processing_started_at`.
2. **Duplicate Refusal**: If another job or worker attempts to process the same complaint while `processing_status` is in an active stage (`ANALYZING_IMAGE`, `CALCULATING_SEVERITY`, etc.) within the timeout threshold (<300s), the request is refused.
3. **Clean Detection Items on Retry**: Prior `DetectionItem` rows for the complaint are cleared before inserting new items, preventing duplicate bounding box rows across retries.
4. **Database Transactions**: All stage changes and final verification are wrapped in a database transaction (`db.session.commit()`), rolling back cleanly on any uncaught exception.

---

## 5. Failure Handling & Admin Retry

If an error occurs during AI processing (e.g. invalid image format, disk I/O error, model exception):
- The complaint remains safely in the database.
- `status` is set to `PROCESSING_FAILED`.
- `processing_status` is set to `FAILED`.
- `processing_error` stores a safe, non-revealing error message (no stack traces exposed to citizens).
- Full technical traceback is logged server-side via `logger.exception()`.
- **REAL_YOLO vs MOCK_DEMO**: The system does NOT silently downgrade `REAL_YOLO` to `MOCK_DEMO` on failure; the failure is recorded honestly with provenance preserved.

### Retrying a Failed Job

Municipal administrators can retry failed jobs via:

```http
POST /api/complaints/<ticket_id>/retry-processing
Authorization: Cookie (Admin session required)
```

Response:
```json
{
  "success": true,
  "ticket_id": "8a3f91bc",
  "status": "AI_PROCESSING",
  "processing_status": "QUEUED",
  "retry_count": 1,
  "job_id": "rq-job-uuid",
  "message": "AI processing job re-enqueued successfully."
}
```

---

## 6. Local Development & Testing Modes

EcoClean Civic supports two queue operational modes via the `ASYNC_MODE` environment variable:

### Mode 1: Synchronous / Testing Mode (`ASYNC_MODE=sync` or `TESTING=True`)
- Executes AI analysis inline synchronously inside the caller thread.
- Requires no Redis service or external worker process.
- Used by automated pytest test suites for fast, 100% deterministic test execution.

### Mode 2: Redis Asynchronous Mode (`ASYNC_MODE=redis`)
- Default for production and multi-container Docker development.
- Uses RQ (Redis Queue) with a dedicated worker process (`python backend/worker.py`).

### Running Locally with Docker Compose

```bash
# 1. Start all services (PostgreSQL, Redis, Flask API, AI Worker)
docker compose up --build

# 2. Inspect worker logs
docker compose logs -f worker

# 3. Scale workers if needed
docker compose up --scale worker=2
```

### Running Locally without Docker

```bash
# Terminal 1: Start Redis (if available locally)
redis-server

# Terminal 2: Start Flask API
python backend/app.py

# Terminal 3: Start AI Worker
python backend/worker.py
```
*(Note: If Redis is not running locally, the dev server automatically falls back to synchronous inline processing with an informational warning, allowing full functionality).*

---

## 7. Real-Time Updates Integration (Phase 4)

In Phase 4, the background worker and Flask API integrate with Server-Sent Events (SSE) via Redis Pub/Sub:
* **Event Distribution**: As worker transitions through stages (`ANALYZING_IMAGE`, `CALCULATING_SEVERITY`, etc.), events are published to `complaints:<ticket_id>` and `admin:events`.
* **Streaming Endpoint**: `GET /api/complaints/<ticket_id>/events` streams real-time updates directly to citizen and admin browsers.
* **Controlled Fallback**: If SSE disconnects or is unsupported, frontend automatically falls back to polling `GET /api/complaints/<ticket_id>`.
* **Full Details**: See [`REALTIME_UPDATES.md`](file:///c:/projects/waste-management-system/REALTIME_UPDATES.md) for the complete protocol specifications.

