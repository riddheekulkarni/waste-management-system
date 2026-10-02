# EcoClean Civic — Municipal Operations Center Architecture (Phase 6)

This document describes the Phase 6 administrative control surface, operational architecture, complaint lifecycle state machine, real-time SSE dispatch feeds, GIS incident mapping, and system health diagnostics for EcoClean Civic.

---

## 1. Product Positioning & Architecture

* **Product Role**: **Municipal Operations Command Center**
* **Operating Persona**: Municipal Dispatchers, Department Officers, Sanitation Supervisors, and System Engineers.
* **Core Philosophy**:
  * High signal-to-noise ratio, decision-supporting operational interface.
  * Map-centric, dense data grids with instant triage actions.
  * Direct synchronization with background AI inference workers (`REAL_YOLO` vs `MOCK_DEMO`).
  * Real-time Server-Sent Events (SSE) dispatch feed.

---

## 2. Navigation & Operational Hierarchy

The Operations Center provides persistent navigation with real-time operational badges:

1. **Overview (`#admin-view-overview`)**:
   * 8 top-level real-time counters: *Total Reports*, *New / Queued*, *AI Processing*, *High Severity*, *Awaiting Dispatch*, *In Progress*, *Resolved*, and *Job Failures*.
   * Split-pane workspace:
     * **Urgent Attention Queue (60%)**: Instant triage for high-severity alerts and failed AI jobs.
     * **Live Operations Feed (40%)**: Streaming SSE updates showing timestamps, incident tags, and progress messages.
2. **Complaints Queue (`#admin-view-complaints`)**:
   * Operational search (Ticket ID, street address, or landmark query).
   * Multi-attribute filtering (Status, Severity, Department, AI Mode).
   * Server-side pagination with row-level actions: *Inspect Details*, *Assign Department*, *Update Status*, *Retry AI*.
3. **AI Processing Center (`#admin-view-processing`)**:
   * Execution mode banner distinguishing `REAL_YOLO` (production inference) from `MOCK_DEMO` (demonstration pipeline).
   * Job queue table displaying processing stages (`QUEUED`, `ANALYZING_IMAGE`, `CALCULATING_SEVERITY`, `COMPLETED`, `FAILED`), duration in milliseconds, retry counts, and safe error diagnostics.
   * Direct re-enqueue action for failed jobs.
4. **Live Incident Map (`#admin-view-map`)**:
   * Leaflet GIS operations map with color-coded severity markers (Red = High, Amber = Medium, Emerald = Low).
   * Real-time marker filtering by department and severity.
   * Interactive incident popup cards with one-click *Inspect Incident* action.
5. **Department Operations (`#admin-view-departments`)**:
   * Workload allocation across canonical departments: *Sanitation Department*, *Recycling Department*, *Health & Hazmat Department*, *Public Works Department*.
   * Metrics: Total Assigned, Pending Active Workload, Resolved Cases, High Severity Alerts.
   * One-click department queue filtering.
6. **Municipal Analytics (`#admin-view-analytics`)**:
   * Configurable reporting timeframes: *Today (1D)*, *7 Days*, *30 Days*, *90 Days*.
   * Chart.js visualizations:
     * Daily incident volume inflow timeline.
     * Severity breakdown distribution.
     * Department workload distribution.
     * AI inference success vs failure rates.
7. **Users Management (`#admin-view-users`)**:
   * Directory of registered citizens and municipal staff.
   * Enforces role isolation; credential hashes and passwords are never exposed.
8. **System Health (`#admin-view-system`)**:
   * Relational database connection verification (active transaction probe).
   * Redis Pub/Sub event bus status.
   * Background RQ Queue backlog metrics.
   * Computer vision pipeline status (weights file verification).

---

## 3. Complaint Lifecycle & Operational State Machine

EcoClean Civic enforces a canonical, server-side validated state machine (`backend/lifecycle.py`):

```text
[SUBMITTED]
    │
    ▼
[AI_PROCESSING] ──────────► [PROCESSING_FAILED] ──(Admin Retry)──┐
    │                                                            │
    ├──► [DUPLICATE]                                             │
    ▼                                                            │
[VERIFIED] ◄─────────────────────────────────────────────────────┘
    │
    ├──► [ASSIGNED] ──► [IN_PROGRESS] ──► [RESOLUTION_SUBMITTED] ──► [RESOLVED]
    │         │               │
    │         └───────────────┴─────────────────────────────────────► [RESOLVED]
    │
    └──► [REJECTED] / [NEEDS_INFORMATION]
```

### Transition Rules
* **Terminal States**: `RESOLVED` and `REJECTED` are terminal. They cannot transition back to active processing.
* **Triage Validation**: Tickets cannot transition directly from `SUBMITTED` or `PROCESSING_FAILED` to `RESOLVED` without undergoing verification.
* **Server-Authoritative**: Attempting an illegal transition via the UI or API returns HTTP 400 with a descriptive error: `Illegal status transition from '<current>' to '<target>'`.

---

## 4. Admin API Contracts

All endpoints in `/api/admin/*`, `/api/complaints/admin/*`, and administrative endpoints are strictly protected with `@require_role("admin")`.

| Method | Endpoint | Description | Query / Body Params |
|---|---|---|---|
| `GET` | `/api/admin/overview` | Aggregated lifecycle counts, urgent backlog, recent tickets | — |
| `GET` | `/api/admin/departments` | Workload metrics per canonical department | — |
| `GET` | `/api/admin/analytics` | Trend timeline, severity, dept, and outcome charts | `?days=7` (1, 7, 30, 90) |
| `GET` | `/api/admin/system-health` | Diagnostic probe of DB, Redis, Queue, AI weights | — |
| `GET` | `/api/complaints` | Server-paginated queue with multi-filters and search | `?q=...&status=...&severity=...&department=...&ai_mode=...&page=1&per_page=20` |
| `GET` | `/api/complaints/<id>` | Full complaint record including AI detections | — |
| `PATCH` | `/api/complaints/<id>/status` | Update lifecycle state and/or assign department | `{"status": "ASSIGNED", "department": "Recycling Department"}` |
| `POST` | `/api/complaints/<id>/retry-processing` | Re-enqueue a failed complaint for AI analysis | — |
| `GET` | `/api/complaints/admin/queue` | Background RQ/AI processing jobs and error states | `?processing_status=FAILED&page=1` |
| `GET` | `/api/complaints/admin/events` | SSE stream broadcasting municipal updates | — |
| `GET` | `/api/analytics/geo` | All geolocated complaints for map plotting | — |
| `GET` | `/api/auth/users` | List registered accounts without password hashes | — |

---

## 5. Security & Role-Based Access Control (RBAC)

1. **Authentication Enforcement**: Unauthenticated requests to administrative endpoints receive HTTP 401.
2. **Citizen Isolation**: Citizens attempting to access `/api/admin/*`, `/api/auth/users`, or `/api/complaints/admin/events` receive HTTP 403 Forbidden.
3. **Data Protection**: User password hashes, internal server tracebacks, and local filesystem paths are scrubbed from all API responses.
4. **Audit Trail**: Operational status and department changes are published to SSE and logged in the database audit log.

---

## 6. Performance & Scalability

1. **Database Indexing**: Filter queries utilize existing compound indexes (`idx_complaints_lat_lng`, `idx_complaints_proc_status`, `idx_complaints_created_at`).
2. **Efficient Aggregation**: Counts and metrics are calculated using SQL `GROUP BY` and `COUNT` queries rather than fetching full records into Python.
3. **Server-Side Pagination**: Operations queues are capped at `MAX_PER_PAGE = 100` (default 20), avoiding browser DOM exhaustion.
4. **Non-Blocking SSE**: Event streaming utilizes Redis Pub/Sub channels (`admin:events`) with lightweight in-memory fallback during local testing.
