# EcoClean Civic — Field Operations & Citizen Feedback Loop (Phase 8)

## 1. Overview

Phase 8 completes the civic accountability and field operations loop for the EcoClean Civic platform:

```text
Citizen Report → AI Verification → Department Assignment → Field Work → Resolution Evidence → Citizen Feedback → Confirm / Needs Attention
```

This ensures municipal departments cannot mark issues resolved without auditable resolution evidence, and citizens directly validate field work on their complaints.

---

## 2. Operational Lifecycle

The system builds upon the existing canonical state machine in `backend/lifecycle.py`:

```text
SUBMITTED
   ↓
AI_PROCESSING
   ↓
VERIFIED
   ↓
ASSIGNED
   ↓
IN_PROGRESS
   ↓
RESOLUTION_SUBMITTED ───(Citizen Feedback)───┐
   │                                          │
   ├── [CONFIRMED] ──────────────────────────→ RESOLVED
   │
   └── [NEEDS_ATTENTION] ────────────────────→ IN_PROGRESS (Returned to field team)
```

### State Definitions
* **`ASSIGNED`**: Department assigned to incident based on automated AI classification or dispatcher triage.
* **`IN_PROGRESS`**: Field crew deployed and undertaking remediation.
* **`RESOLUTION_SUBMITTED`**: Field crew has submitted resolution evidence (operational note + optional photo). Awaiting citizen review.
* **`RESOLVED`**: Citizen confirmed resolution, or municipal administrative closure. `resolved_at` timestamp recorded.

---

## 3. APIs

### Field Resolution Evidence
* **`POST /api/complaints/<ticket_id>/resolution`**
  * **Role**: Admin / Municipal Officer (`@require_role("admin")`)
  * **Payload**: `multipart/form-data` or `application/json`
    * `note` (string, required if no image): Description of field remediation work.
    * `image` (file, optional): Photo evidence of completed work.
  * **Lifecycle Effect**: Moves complaint status to `RESOLUTION_SUBMITTED`, sets `resolution_submitted_at`.
  * **Events & Alerts**: Emits SSE `resolution_submitted` and sends in-app notification to the citizen owner.

* **`GET /api/complaints/<ticket_id>/resolution`**
  * **Role**: Admin or Ticket Owner Citizen
  * **Returns**: Resolution note, evidence photo path, submission timestamp, and department.

### Citizen Feedback
* **`POST /api/complaints/<ticket_id>/feedback`**
  * **Role**: Authenticated Citizen Owner (`@login_required`, strictly scoped to `complaint.user_id`)
  * **Payload**: `multipart/form-data` or `application/json`
    * `result` (string, required): Either `"CONFIRMED"` or `"NEEDS_ATTENTION"`.
    * `comment` (string, optional): Citizen remarks on site condition.
    * `image` (file, optional): Citizen follow-up photo evidence.
  * **Duplicate Prevention**: 60-second duplicate submission throttle prevents accidental double-clicks.
  * **Lifecycle Effect**:
    * `"CONFIRMED"` $\to$ transitions complaint status to `RESOLVED`, sets `resolved_at`.
    * `"NEEDS_ATTENTION"` $\to$ returns complaint status to `IN_PROGRESS` for follow-up work.
  * **Events & Alerts**: Emits SSE `citizen_feedback_received`, `resolution_confirmed` / `resolution_needs_attention`, and generates administrative alert.

* **`GET /api/complaints/<ticket_id>/feedback`**
  * **Role**: Admin or Ticket Owner Citizen
  * **Returns**: Complete historical ledger of citizen feedback for the ticket.

### Administrative Feedback Queue & Metrics
* **`GET /api/admin/feedback`**
  * **Role**: Admin (`@require_role("admin")`)
  * **Query Parameters**:
    * `result`: Filter by `CONFIRMED` or `NEEDS_ATTENTION`.
    * `department`: Filter by department name.
    * `page`, `per_page`: Server-side pagination.
  * **Returns**: Paginated list of all citizen feedback with incident context and resolution notes.

* **`GET /api/admin/insights?days=N`**
  * **Role**: Admin (`@require_role("admin")`)
  * **Extended with `field_operations`**:
    * `resolution_submissions`: Count of field resolution submissions in window.
    * `total_resolution_submissions`: Total all-time resolution submissions.
    * `citizen_confirmations`: Number of citizen confirmations.
    * `needs_attention_responses`: Number of citizen "needs attention" reports.
    * `feedback_response_rate_pct`: Ratio of feedback submissions to resolutions.
    * `reopened_returned_cases`: Count of cases returned to `IN_PROGRESS`.
    * `avg_resolution_to_feedback_hours`: Average turnaround hours from field work submission to citizen feedback.

---

## 4. Notifications & SSE Event Distribution

### Notification Categories
* `CATEGORY_RESOLUTION_SUBMITTED` (`"resolution_submitted"`): Directed to citizen owner when municipal field team submits evidence.
* `CATEGORY_CITIZEN_FEEDBACK_RECEIVED` (`"citizen_feedback"`): Alert to operations center when citizen inputs feedback.
* `CATEGORY_RESOLUTION_CONFIRMED` (`"resolution_confirmed"`): Broadcast to operations center when incident is citizen-confirmed.
* `CATEGORY_RESOLUTION_NEEDS_ATTENTION` (`"resolution_needs_attention"`): Priority alert when citizen reports issue requires further work.

### Real-Time SSE Channels
* `complaints:<ticket_id>`: Dispatches `resolution_submitted`, `citizen_feedback_received`, `resolution_confirmed`, `resolution_needs_attention`, and `complaint_status_changed`.
* `admin:events`: Broadcasts to Municipal Operations Command Center live feed and updates queue badges in real time.

---

## 5. Security & Access Authorization

1. **Role-Based Authorization**:
   * Only admins can submit field resolution evidence.
   * Only the citizen who submitted the complaint can submit feedback (enforced via server-side session checks).
2. **Private Evidence Storage & Serving**:
   * Both resolution photos (`resolution_{ticket_id}_{uuid}.ext`) and citizen feedback photos (`feedback_{ticket_id}_{uuid}.ext`) are stored in the server upload folder.
   * Access via `/uploads/<filename>` strictly validates:
     - Authentication required (401).
     - Admin access permitted for all complaints.
     - Citizen access strictly verified against complaint ownership (403 for unauthorized users).
     - Strict path traversal prevention (rejects `..`, slashes, and non-canonical basenames).

---

## 6. Database Migration

Migration version: `a7b8c9d0e1f2_add_phase8_field_ops_and_feedback.py`
* **Table `complaints`**:
  * `resolution_note` (`TEXT`, nullable)
  * `resolution_image_path` (`VARCHAR(255)`, nullable)
  * `resolution_submitted_at` (`DATETIME`, nullable)
  * `resolved_at` (`DATETIME`, nullable)
* **Table `citizen_feedback`**:
  * `id` (`INTEGER`, Primary Key, autoincrement)
  * `complaint_id` (`VARCHAR(8)`, Foreign Key to `complaints.id`, indexed)
  * `user_id` (`INTEGER`, Foreign Key to `users.id`, indexed)
  * `result` (`VARCHAR(32)`, index: `"CONFIRMED"` / `"NEEDS_ATTENTION"`)
  * `comment` (`TEXT`, nullable)
  * `image_path` (`VARCHAR(255)`, nullable)
  * `created_at` (`DATETIME`, default UTC, indexed)

---

## 7. Known Limitations

* Field crew submissions currently interface through the Municipal Operations Center web portal. Dedicated field mobile client / offline PWA synchronization is deferred to future scopes.
* Images are stored locally on the server filesystem. For multi-node cloud deployments, an S3/GCS blob store driver can be plugged in without changing API semantics.
