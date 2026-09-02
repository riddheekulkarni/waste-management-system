# EcoClean Civic

EcoClean Civic is a Flask-based civic waste reporting system. Citizens upload
photos of illegal dumping or overflowing waste, the detection pipeline
identifies waste items, a rule-based engine grades severity, and the complaint
is routed to the appropriate municipal department. Citizens can track reports
on a map, while authenticated admins can review analytics and update ticket
status.

The project is designed as a working local prototype: it runs without trained
model weights by using a mock detector, but can switch to YOLOv8 inference when
custom weights are available.



## File Structure

```
waste-management-system/
├── backend/
│   ├── app.py                  # Flask app factory + entry point, serves frontend too
│   ├── config.py                # App configuration (DB path, upload folder, etc.)
│   ├── models.py                # SQLAlchemy models: Complaint, DetectionItem
│   ├── detection.py             # Stage 1 — YOLOv8 wrapper (real + mock modes)
│   ├── severity.py              # Stage 2a — coverage-ratio severity engine
│   ├── routing.py               # Stage 2b — waste-class → department mapping
│   ├── routes/
│   │   ├── auth.py             # Register, login, logout, and current-user endpoints
│   │   ├── complaints.py        # /api/complaints/* endpoints
│   │   └── analytics.py         # /api/analytics/* endpoints (admin dashboard)
│   ├── requirements.txt
│   ├── uploads/                 # Uploaded photos are stored here (auto-created)
│   └── waste_management.db      # SQLite database (auto-created on first run)
├── frontend/
│   ├── index.html               # Single-page app: Report / Track / Admin tabs
│   ├── css/styles.css
│   └── js/app.js                # Fetch calls to the backend API, chart rendering
├── future_scope_roadmap.md      # Detailed plan for the remaining ~10-20%
└── README.md
```

## How It Works

```
Citizen uploads photo (frontend)
        |
        v
POST /api/complaints/upload (backend)
        |
        v
Stage 1: WasteDetector.detect()        -> bounding boxes + classes
        |
        v
Stage 2: compute_severity()            -> Low / Medium / High
         determine_department()        -> which dept handles it
        |
        v
Stage 3: Complaint + DetectionItem rows saved to SQLite
        |
        v
Citizen tracks status in "Track Complaints" tab
Admin manages tickets + views charts in "Admin Dashboard" tab
```

## Setup & Run

```bash
cd backend
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5050** in a browser — the Flask server serves
both the API and the frontend, so nothing else needs to run separately.

On Windows PowerShell, set optional model weights for the current session with:

```powershell
$env:WASTE_MODEL_WEIGHTS = "C:\path\to\best.pt"
python app.py
```

The app works immediately with no trained model, using a **mock detector**
that generates realistic synthetic detections sized against each uploaded
photo's real dimensions (so severity scoring still behaves sensibly for a
demo). Once a custom-trained YOLOv8 model exists (see
`future_scope_roadmap.md` item #1), point the app at it:

```bash
export WASTE_MODEL_WEIGHTS=/path/to/best.pt
python app.py
```

No code changes are needed — `WasteDetector` automatically switches to real
inference mode when a valid weights file is found.

### Demo Accounts

The first application start creates these accounts if they do not already
exist:

| Role | Email | Password |
|---|---|---|
| Citizen | `citizen@civic.gov` | `citizen123` |
| Admin | `admin@civic.gov` | `admin123` |

Change these credentials before using the application beyond local demos.
Citizen registration is available from the sign-in dialog. Guest users can
also submit complaints, but signing in enables the **My Reports** filter.

## Database

SQLite (`waste_management.db`), created automatically on first run via
SQLAlchemy. Three tables:

- **users** — local accounts with hashed passwords and `citizen` or `admin`
  roles
- **complaints** — one row per submitted ticket (severity, department,
  status, address, and GPS coordinates if provided)
- **detection_items** — one row per detected waste object, linked to its
  parent complaint (class, confidence, bounding box)

This is intentionally lightweight for local development and demoing to a
reviewer. `future_scope_roadmap.md` item #5 covers migrating to PostgreSQL
+ PostGIS for a real deployment.

## API Reference

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/complaints/upload` | Submit a photo (+ optional lat/lng), runs the full pipeline |
| GET | `/api/complaints` | List complaints (filter by `status`, `department`, `severity`) |
| GET | `/api/complaints/<id>` | Full detail for one ticket, incl. detections |
| PATCH | `/api/complaints/<id>/status` | Update status: `Open` / `In Progress` / `Resolved` |
| GET | `/api/analytics/summary` | Counts by severity/department/status, for the admin dashboard |
| POST | `/api/auth/register` | Register a citizen account |
| POST | `/api/auth/login` | Sign in with username or email |
| POST | `/api/auth/logout` | End the current session |
| GET | `/api/auth/me` | Return the currently signed-in user |

`POST /api/complaints/upload` accepts a multipart form with an `image` field
and optional `latitude`, `longitude`, and `address` fields. Status updates
require an authenticated admin session. The API currently allows complaint
listing and detail lookups without authentication for local demonstration.

## What's Implemented vs. What's Future Scope

**Implemented (this project):** detection pipeline (with demo-ready mock
fallback), severity grading, department routing, SQLite persistence, session
authentication with citizen/admin roles, full REST API, interactive address
and tracking maps, and a working three-tab frontend (citizen report form,
citizen tracker, admin dashboard with live charts).

**Future scope (see `future_scope_roadmap.md`):** training a real waste
model on an annotated dataset, mobile app, SMS/push notifications, stronger
production authentication and authorization, production DB/cloud deployment,
duplicate-complaint detection, an admin geospatial heatmap, and a model
feedback loop.
