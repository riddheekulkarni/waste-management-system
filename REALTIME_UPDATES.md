# EcoClean Civic — Real-Time Updates with Server-Sent Events (Phase 4)

This document describes the Phase 4 real-time update architecture using Server-Sent Events (SSE) and Redis Pub/Sub, detailing event protocols, authorization, connection lifecycle, and graceful fallback behaviors.

---

## 1. Architecture Overview

Phase 4 replaces client-side HTTP polling with an event-driven server-to-browser stream using **Server-Sent Events (SSE)**.

The authoritative source of truth remains the relational database. Redis Pub/Sub provides low-latency distribution from RQ workers to Flask SSE streams.

```text
Browser (Citizen / Admin)
       │
       │ (1) GET /api/complaints/<ticket_id>/events (text/event-stream)
       ▼
Flask SSE Generator (backend/events.py)
       │
       ├─► (2) Yields initial authoritative state directly from Database
       │
       ├─► (3) Subscribes to Redis Pub/Sub channel: "complaints:<ticket_id>"
       │
       ▲
       │ (4) Redis Publish (EVENT_STAGE_CHANGED, EVENT_PROCESSING_COMPLETED, ...)
RQ Worker (backend/tasks.py)
       │
       ├─► Commits stage / status changes to Database
       └─► Emits sanitized event envelope to Redis Pub/Sub channel
```

### Key Design Principles:
1. **Database as Single Source of Truth**: The event layer never acts as an independent datastore. Upon client connection, the current database record is immediately yielded as the first event.
2. **Simple, Reliable Infrastructure**: Reuses the Redis service already introduced in Phase 3. No extra broker (Kafka, RabbitMQ) or protocol overhead (WebSockets) is introduced.
3. **Dual Transport Support**: Uses Redis Pub/Sub in production/async mode with an automatic in-memory queue fallback for isolated unit tests or synchronous execution modes.
4. **Strict RBAC & Privacy**: Citizens can only subscribe to their own complaint streams; admins can monitor individual complaints or global municipal events.
5. **No Leaked Internals**: All events scrub stack traces, server filesystem paths, and internal exceptions before publishing.

---

## 2. Server-Sent Events (SSE) Endpoints

### 2.1 Citizen Complaint Event Stream
* **URL**: `GET /api/complaints/<ticket_id>/events`
* **Content-Type**: `text/event-stream`
* **Headers**:
  * `Cache-Control: no-cache, no-transform`
  * `X-Accel-Buffering: no`
  * `Connection: keep-alive`
* **Authorization**:
  * Authenticated user session required (`@login_required`).
  * Citizen role strictly limited to their own complaints (`user_id == complaint.user_id`). Unauthorized requests return `403 Forbidden`.
  * Admin role permitted to subscribe to any complaint.
  * Invalid or nonexistent `ticket_id` returns `404 Not Found`.

### 2.2 Admin Global Municipal Event Stream
* **URL**: `GET /api/complaints/admin/events`
* **Content-Type**: `text/event-stream`
* **Authorization**:
  * Administrator role required (`@require_role('admin')`). Citizens receive `403 Forbidden`.
  * Streams events across all tickets (new complaint submissions, triage completions, high-severity detections, status updates).

---

## 3. Standardized Event Types & Schemas

All Server-Sent Events follow the standard envelope format:

```text
event: <event_type>
id: <ticket_id>-<timestamp_or_seq>
data: {"event": "<event_type>", "ticket_id": "...", ...}
```

### Canonical Event Types

| Event Type | Source | Description |
|---|---|---|
| `complaint_status` | Flask SSE Generator | Initial authoritative state emitted immediately upon connection. |
| `complaint_submitted` | Flask API | Emitted when complaint is registered and queued for AI analysis. |
| `processing_started` | RQ Worker | Emitted when background worker picks up the job. |
| `processing_stage_changed` | RQ Worker | Emitted on every pipeline stage transition (`ANALYZING_IMAGE`, `CALCULATING_SEVERITY`, etc.). |
| `processing_completed` | RQ Worker | Emitted when AI verification succeeds or marks ticket as duplicate. |
| `processing_failed` | RQ Worker | Emitted when processing fails; includes safe sanitized error. |
| `complaint_status_changed` | Flask API | Emitted when admin updates complaint lifecycle status (`ASSIGNED`, `RESOLVED`, etc.). |
| `heartbeat` | Flask SSE Generator | Emitted every 15 seconds to prevent browser/proxy timeouts. |

### Example Payloads

#### 1. Initial State (`complaint_status`)
```json
{
  "ticket_id": "8a3f91bc",
  "status": "AI_PROCESSING",
  "processing_status": "ANALYZING_IMAGE",
  "stage": "ANALYZING_IMAGE",
  "progress_message": "Complaint currently in stage: ANALYZING_IMAGE",
  "ai_mode": "REAL_YOLO",
  "severity": null,
  "department": null
}
```

#### 2. Stage Progression (`processing_stage_changed`)
```json
{
  "event": "processing_stage_changed",
  "ticket_id": "8a3f91bc",
  "complaint_id": "8a3f91bc",
  "timestamp": "2026-10-02T10:15:30.123456+00:00",
  "status": "AI_PROCESSING",
  "processing_status": "CALCULATING_SEVERITY",
  "stage": "CALCULATING_SEVERITY",
  "progress_message": "Calculating overlap-aware waste severity score",
  "ai_mode": "REAL_YOLO"
}
```

#### 3. Successful Completion (`processing_completed`)
```json
{
  "event": "processing_completed",
  "ticket_id": "8a3f91bc",
  "status": "VERIFIED",
  "processing_status": "COMPLETED",
  "stage": "COMPLETED",
  "severity": "High",
  "department": "Solid Waste Management",
  "ai_mode": "REAL_YOLO",
  "item_count": 4,
  "coverage_ratio": 0.385,
  "is_duplicate": false,
  "duration_ms": 142,
  "progress_message": "AI processing completed successfully. Routed to Solid Waste Management (High severity)."
}
```

#### 4. Safe Failure (`processing_failed`)
```json
{
  "event": "processing_failed",
  "ticket_id": "8a3f91bc",
  "status": "PROCESSING_FAILED",
  "processing_status": "FAILED",
  "stage": "FAILED",
  "error": "Uploaded image file appears corrupted or unreadable.",
  "retry_available": true,
  "duration_ms": 25
}
```

---

## 4. Connection Lifecycle & Terminal States

### Terminal Processing States
* `COMPLETED`
* `FAILED`

### Terminal Lifecycle States
* `VERIFIED`
* `DUPLICATE`
* `PROCESSING_FAILED`

When a complaint reaches a terminal processing state:
1. The completion or failure event is delivered to the browser.
2. The server-side generator cleanly exits the loop and unsubscribes from Redis Pub/Sub.
3. The frontend closes the `EventSource` connection, preventing hanging idle streams.

If a client connects to `GET /api/complaints/<ticket_id>/events` for a complaint that is **already in a terminal state**, the initial `complaint_status` event is emitted immediately, after which the stream terminates gracefully.

---

## 5. Frontend Integration & Controlled Fallback

### Frontend Behavior (`frontend/js/app.js`)
1. Upon complaint submission, the frontend initializes `new EventSource('/api/complaints/<ticket_id>/events')`.
2. Event listeners update the upload card in real-time as each stage executes:
   * Displays dynamic stage progress (`ANALYZING_IMAGE`, `CALCULATING_SEVERITY`, `CHECKING_DUPLICATES`, `ASSIGNING_DEPARTMENT`).
   * When `processing_completed` fires: immediately updates the card with AI severity, department, item count, and toasts success.
   * When `processing_failed` fires: updates the card with the sanitized error message and notifies the user.
3. **Controlled Fallback Polling**:
   * If `window.EventSource` is unsupported in the browser, OR if the SSE stream disconnects unexpectedly (`onerror`), the application automatically activates fallback polling to `GET /api/complaints/<ticket_id>`.
   * Fallback interval: 2.5 seconds (avoiding aggressive hammering).
   * Polling automatically terminates upon reaching any terminal state or 25 attempts.
   * If SSE reconnects successfully, fallback polling is stopped.

---

## 6. Docker & Local Development Verification

### Starting with Docker Compose
```bash
docker compose up
```
Services running:
* `web`: Flask application handling REST and SSE streaming endpoints.
* `worker`: Background RQ worker processing AI pipeline jobs and publishing events.
* `redis`: Redis server acting as RQ job broker and Pub/Sub event bus.
* `db`: Database storing authoritative complaint records.

### Local Development (without Docker)
1. Start Redis:
   ```bash
   redis-server
   ```
2. Start Flask Web Server:
   ```bash
   python backend/app.py
   ```
3. Start Background Worker:
   ```bash
   python backend/worker.py
   ```

---

## 7. Known Limitations & Future Roadmap
* **Horizontal Scaling of Flask SSE Workers**: In high-load production deployments with thousands of concurrent long-lived SSE connections, an asynchronous WSGI server (such as Gunicorn with gevent/eventlet workers) or an edge proxy (such as NGINX `proxy_buffering off`) is recommended.
* **Phase 5 Future Scope**: Expanding admin real-time streams to power live operational command centers and municipal heatmaps.
