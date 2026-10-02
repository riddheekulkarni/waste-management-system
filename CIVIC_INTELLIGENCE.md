# EcoClean Civic — Phase 7: Integrated Civic Intelligence Layer

> **"See what is happening across the city. Understand where problems concentrate. Notify the right people. Help operations teams act faster."**

---

## 1. Executive Overview

Phase 7 introduces the **Integrated Civic Intelligence Layer** on top of the established EcoClean Civic platform (Phases 1–6). Rather than acting simply as a passive repository and dispatch tracker for complaints, the platform now provides **city-level operational intelligence**.

The intelligence layer is structured around four foundational pillars:
1. **Live Civic Intelligence Map**: Upgrades the Leaflet GIS interface with server-side multi-filtering and four operational layers (Incidents, Observed Concentration, Department Workload, Resolution Activity).
2. **Advanced Geospatial Analytics**: Mathematical geographic cell bucketing (~1.1 km grid cells) and spatial clustering (<= 50m) to identify recurring report concentrations without external heavy GIS dependencies.
3. **Operational Notifications**: An internal notification center for dispatchers with automated operational alert rules and in-app status updates for citizens, coupled to the real-time SSE stream.
4. **Municipal Operational Insights**: Evidence-based comparative indicators evaluating period-over-period civic inflow, operational age thresholds (aging unassigned, high-severity delays), and empirical lifecycle milestone durations with explicit *"Insufficient data"* handling.

> [!IMPORTANT]
> **Strict Operational Design Rule**: EcoClean Civic does **NOT** use predictive policing, future incident forecasting, or speculative algorithms. All concentrations, heat distributions, and clusters represent **observed historical incident density**.

---

## 2. Live Civic Intelligence Map

### 2.1 Architectural Integration
The map builds upon the existing Leaflet engine (`#admin-ops-map`), replacing client-side array filtering with server-side query endpoints and dedicated Leaflet `L.layerGroup` instances.

```
┌────────────────────────────────────────────────────────┐
│                   Admin Filter Bar                     │
│  [Days] [Severity] [Status] [Dept] [AI Mode] [Category]│
└──────────────────────────┬─────────────────────────────┘
                           │ Query params (days, sev, ...)
                           ▼
             GET /api/admin/map (Points)
             GET /api/admin/map/aggregate (Cells)
                           │
       ┌───────────────────┴───────────────────┐
       ▼                                       ▼
┌────────────────────────┐           ┌────────────────────────┐
│  Point Layers          │           │  Density Layer         │
│  • Layer A: Incidents  │           │  • Layer B: Incident   │
│  • Layer C: Dept Work  │           │    Concentration       │
│  • Layer D: Resolution │           │    (Historical Grid)   │
└────────────────────────┘           └────────────────────────┘
```

### 2.2 Operational Map Layers
Operators can toggle four distinct operational layers via dedicated layer pill controls:

* **Layer A — Incidents (📍)**:
  * Individual incident circle markers colored by severity:
    * High: `#dc2626` (Red, 9px radius)
    * Medium: `#d97706` (Amber, 7px radius)
    * Low: `#059669` (Emerald, 7px radius)
  * Rich popup showing ticket ID, lifecycle status, assigned department, detected category, AI execution mode, street address, and direct **Inspect Incident** trigger.
* **Layer B — Incident Concentration (🔥)**:
  * Visualizes concentrations of observed incidents using mathematical grid cell centroids.
  * Radius dynamically scaled: `clamp(16px, count * 5, 50px)`.
  * Highlighted red (`#ef4444`) when high-severity incidents are present in the cell, otherwise amber (`#f59e0b`).
  * Explicitly labeled in popup: *"Historical Incident Density — Observed incident concentration. Not predictive risk."*
* **Layer C — Department Workload (🏛️)**:
  * Displays spatial distribution of active, unresolved complaints color-coded by assigned municipal department:
    * Sanitation: `#0284c7` (Sky Blue)
    * Recycling: `#10b981` (Emerald)
    * Health & Hazmat: `#f43f5e` (Rose)
    * Public Works: `#8b5cf6` (Purple)
* **Layer D — Resolution Activity (✅)**:
  * Highlights locations where complaints have achieved `RESOLVED` status, displaying completed triage and resolution timestamps.

### 2.3 Server-Side Multi-Filtering
The backend endpoint `GET /api/admin/map` filters before serialization, preventing unbounded client memory overhead:
* `days`: Bounded time window (e.g. 1, 7, 30, 90 days).
* `severity`: `Low`, `Medium`, `High`.
* `status`: `SUBMITTED`, `AI_PROCESSING`, `VERIFIED`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`, `PROCESSING_FAILED`, `DUPLICATE`.
* `department`: Sanitation, Recycling, Health & Hazmat, Public Works.
* `ai_mode`: `REAL_YOLO`, `MOCK_DEMO`.
* `category`: Canonical waste classes (`plastic_bottle`, `organic_waste`, `hazardous_materials`, etc.).

---

## 3. Geospatial Aggregation Strategy

EcoClean Civic avoids external spatial databases (e.g. PostGIS) by utilizing efficient geographic grid bucketing directly on database records:

### 3.1 Grid Cell Bucketing Algorithm
Latitude and longitude coordinates are quantized to a grid with resolution `DELTA = 0.01` degrees (~1.11 km at Pune / civic latitudes):

$$\text{lat}_{\text{bucket}} = \text{round}\left(\frac{\text{lat}}{\text{DELTA}}\right) \times \text{DELTA}$$
$$\text{lng}_{\text{bucket}} = \text{round}\left(\frac{\text{lng}}{\text{DELTA}}\right) \times \text{DELTA}$$

Each cell aggregates:
* `incident_count`: Total reports in cell during time window.
* `high_severity`: Count of High-severity incidents.
* `resolved`: Count of resolved incidents.
* `active`: Count of pending/active incidents.
* `departments`: Distribution of departments operating in the cell.

### 3.2 Recurring Report Concentrations (Spatial Clustering)
To identify hyper-local repeated dumping or chronic waste issues, reports are clustered using spherical distance calculation:
* Points within **$\le 50$ meters** are grouped.
* Reports must exceed $\ge 2$ instances to form a recurring cluster.
* Calculated metrics: cluster report count, time span between first and latest report, active vs. resolved ratio, and involved departments.

---

## 4. Operational Notification Architecture

### 4.1 Internal Data Model
Notifications are persisted in SQLite/PostgreSQL via the `Notification` model:

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `String(36)` | UUID primary key |
| `user_id` | `Integer` (Nullable) | Target citizen user (NULL for global admin alerts) |
| `ticket_id` | `String(32)` (Nullable) | Linked complaint ID |
| `category` | `String(64)` | Standardized alert category enum |
| `title` | `String(255)` | Short headline |
| `message` | `Text` | Contextual alert message |
| `severity` | `String(32)` (Nullable) | `Low`, `Medium`, `High`, or `CRITICAL` |
| `department` | `String(128)` (Nullable) | Related municipal department |
| `is_read` | `Boolean` | Read/unread state (default `False`) |
| `created_at` | `DateTime` | Generation timestamp |

**Indexes applied**:
* `ix_notifications_user_id`
* `ix_notifications_category`
* `ix_notifications_is_read`
* `ix_notifications_created_at`
* `ix_notifications_ticket_id`

### 4.2 Standard Alert Categories
* `NEW_HIGH_SEVERITY`: Broadcast when AI or triage identifies a high-severity civic hazard.
* `AI_PROCESSING_FAILED`: Triggered when vision inference encounters non-retryable failure or maximum retries.
* `DUPLICATE_DETECTED`: Triggered when spatial deduplication associates a complaint with an existing active issue.
* `UNASSIGNED_REPORT`: Operational warning for verified reports awaiting department assignment.
* `SLA_WARNING`: Operational age warning when active reports exceed configured guidelines.
* `STATUS_CHANGED`: Status progress notifications dispatched to the report's owner.
* `SYSTEM_ALERT`: General municipal infrastructure alerts.

### 4.3 Deduplication & Rate Limiting
To prevent notification storms, `create_notification` applies an automated deduplication cooldown:
* Identical category + ticket ID alerts are throttled within a **30-minute deduplication window**.
* Ensures repeated background worker evaluations or status refreshes do not create duplicate noise.

---

## 5. Operational Rules Engine

A lightweight, idempotent operational rule engine evaluates system conditions during events and periodic reviews:

1. **High Severity Incident Rule**:
   * *Trigger*: Incident status changes or AI completes with `severity_level == 'High'`.
   * *Action*: Emits `NEW_HIGH_SEVERITY` admin alert and publishes SSE event `high_severity_alert`.
2. **AI Failure Rule**:
   * *Trigger*: Background RQ worker records `PROCESSING_FAILED`.
   * *Action*: Emits `AI_PROCESSING_FAILED` admin alert with error reason; informs citizen that manual dispatcher review is underway.
3. **Duplicate Detection Rule**:
   * *Trigger*: Proximity engine links complaint to an active existing ticket.
   * *Action*: Emits `DUPLICATE_DETECTED` notification with cross-reference to primary ticket.
4. **Operational Age Monitoring Rule**:
   * *Trigger*: Periodic evaluation of active backlog against operational guidelines:
     * Unassigned verified reports $> 12$ hours.
     * High-severity active reports $> 6$ hours.
     * Active unresolved reports $> 24$ hours.
   * *Action*: Generates actionable operational age alerts for municipal dispatchers.

---

## 6. Real-Time SSE Notification Integration

EcoClean Civic extends its existing single-connection Server-Sent Events architecture without introducing secondary transports or WebSocket overhead:

### Admin Event Stream (`/api/complaints/admin/events`)
Authorized officers receive:
* `notification_created`: Live payload with unread counts and alert details.
* `high_severity_alert`: Urgent priority popups and audio/visual cues.
* `processing_failure_alert`: Instant visibility of failed vision jobs.
* `assignment_alert`: Department workload dispatch updates.
* `resolution_alert`: Real-time resolution notifications.

### Citizen Event Stream (`/api/complaints/<ticket_id>/events`)
Authenticated citizens receive events scoped strictly to their ticket:
* `notification_created`: In-app notification toast and unread indicator badge.
* `complaint_status`: Stage progression (`VERIFIED` $\to$ `ASSIGNED` $\to$ `IN_PROGRESS` $\to$ `RESOLVED`).

---

## 7. Municipal Operational Insights

The **Operational Insights** pane (`#admin-view-insights`) provides evidence-based municipal performance indicators:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Municipal Insights                              │
│   [7 Days] [30 Days] [90 Days]                                         │
├────────────────────────────────────────────────────────────────────────┤
│  Civic Trends (vs Previous Equivalent Period)                          │
│  • Volume Inflow:    28  (+16.7%)  | High Severity:    8 (+33.3%)      │
│  • Resolved Volume:  19  (+11.8%)  | Resolution Rate: 67.9% (+2.4%)    │
├────────────────────────────────────────────────────────────────────────┤
│  Operational Age Thresholds        │ Resolution Milestones             │
│  • Unassigned >12h:    3 tickets   │ • Submitted → Verified: 4.2 min   │
│  • High Severity >6h:  1 ticket    │ • Verified → Assigned:  1.4 hrs   │
│  • Pending Total >24h: 5 tickets   │ • Assigned → Resolved:  18.6 hrs  │
│                                    │   (Explicit "Insufficient data")  │
├────────────────────────────────────────────────────────────────────────┤
│  Recurring Report Concentrations (Observed Spatial Clusters ≤ 50m)     │
│  • Cluster [18.5204, 73.8567]: 4 reports | Sanitation | [Map Area]    │
└────────────────────────────────────────────────────────────────────────┘
```

### 7.1 Trend Analysis with Normalized Comparative Windows
For a selected window of $D$ days:
* **Current Period**: $[T - D, T]$
* **Previous Equivalent Period**: $[T - 2D, T - D]$
* Metrics calculated:
  $$\Delta\% = \frac{\text{Current} - \text{Previous}}{\max(1, \text{Previous})} \times 100$$
* Compares total inflow, high-severity incidence, resolved count, and net resolution rate.

### 7.2 Resolution Performance Milestones
Calculates true duration between recorded lifecycle timestamps:
* `SUBMITTED` $\to$ `VERIFIED` (AI & manual verification latency)
* `VERIFIED` $\to$ `ASSIGNED` (Dispatch latency)
* `ASSIGNED` $\to$ `IN_PROGRESS` (Field response latency)
* `IN_PROGRESS` $\to$ `RESOLVED` (Remediation latency)

> [!NOTE]
> If timestamps for a lifecycle stage do not exist in the database, the system outputs **"Insufficient data"** instead of inventing dummy averages.

---

## 8. API Reference

### 8.1 Administrative Intelligence Endpoints
All admin endpoints require `@require_role("admin")` with Bearer JWT or active session.

* `GET /api/admin/map`
  * *Query params*: `days`, `severity`, `status`, `department`, `ai_mode`, `category`
  * *Returns*: `{ points: [...], count: 24 }`
* `GET /api/admin/map/aggregate`
  * *Query params*: identical to map filter
  * *Returns*: `{ cells: [...], total_incidents: 24, cell_size_deg: 0.01 }`
* `GET /api/admin/geospatial`
  * *Returns*: High-level bounding box, cell aggregation, and recurring clusters $\le 50$m.
* `GET /api/admin/insights`
  * *Query params*: `days` (default 7)
  * *Returns*: Comprehensive trends, workload age metrics, AI operations, resolution milestones, recurring report concentrations.
* `GET /api/admin/notifications`
  * *Query params*: `unread_only`, `category`, `limit`
  * *Returns*: `{ notifications: [...], unread_count: 3, total: 12 }`
* `PATCH /api/admin/notifications/<id>/read`
  * *Returns*: `{ success: true, notification: {...} }`
* `POST /api/admin/notifications/read-all`
  * *Returns*: `{ success: true, updated_count: 3 }`

### 8.2 Citizen Notification Endpoints
Scoped strictly to the authenticated user via `@require_auth`.

* `GET /api/notifications`
  * *Returns*: User's notifications and unread count.
* `PATCH /api/notifications/<id>/read`
  * *Returns*: Updated notification (403/404 if not owned by user).
* `POST /api/notifications/read-all`
  * *Returns*: Marks all notifications for the authenticated user as read.

---

## 9. Security & Access Control

1. **Role-Based Access Control (RBAC)**:
   * Citizen accounts cannot access administrative map aggregation, operational alerts, or cross-department insights (`HTTP 403 Forbidden`).
2. **Notification Isolation**:
   * Citizen queries filter strictly by `user_id == current_user.id`.
   * An attacker attempting to mark another citizen's notification as read receives `HTTP 404 Not Found`.
3. **No Event Leakage**:
   * Admin SSE channel requires admin role validation before yielding the generator.
   * Citizen ticket SSE channel validates ticket ownership or admin privileges before connection.

---

## 10. Performance & Database Optimization

* **Indexed Lookups**: All notification queries leverage compound and single-column B-tree indexes.
* **Server-Side Filtering**: Leaflet map points are bounded and filtered at SQL query execution time.
* **Bounded Serialization**: Aggregation queries limit coordinate precision and summarize points into cell buckets.
* **Zero Client-Side Flooding**: Markers on the client are handled within managed `L.layerGroup` collections, cleared before re-population.

---

## 11. Known Limitations & Phase 8 Readiness

* **Leaflet High Density**: On low-powered mobile devices, rendering $> 1,000$ simultaneous DOM markers can decrease frame rates; Leaflet canvas rendering or clustering can be added if city-wide density exceeds thousands of active pins.
* **Database Driver**: The default development deployment uses SQLite with standard Python rounding for grid bucketing. In high-concurrency production deployments on PostgreSQL, standard PostGIS point indexes can be adopted transparently if needed.
* **Phase 8 Readiness**: The intelligence layer establishes the clean data contracts, event structures, and operational surfaces required for Phase 8 field crew dispatching and citizen feedback loops.
