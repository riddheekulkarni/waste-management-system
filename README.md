# Civic Waste Reporting System

An AI-based system where citizens photograph waste issues, a YOLOv8 pipeline
detects and localizes waste items, a rule-based engine grades severity and
routes the complaint to the right municipal department, and both citizens
and admins can track status through a web app.

Status: **~85% complete**, fully runnable end-to-end today using a mock
detector (see `future_scope_roadmap.md` for what remains, e.g. training a
real waste-detection model).

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

## Database

SQLite (`waste_management.db`), created automatically on first run via
SQLAlchemy. Two tables:

- **complaints** — one row per submitted ticket (severity, department,
  status, GPS coordinates if provided)
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

## What's Implemented vs. What's Future Scope

**Implemented (this project):** detection pipeline (with demo-ready mock
fallback), severity grading, department routing, SQLite persistence, full
REST API, and a working three-tab frontend (citizen report form, citizen
tracker, admin dashboard with live charts).

**Future scope (see `future_scope_roadmap.md`):** training a real waste
model on an annotated dataset, mobile app, SMS/push notifications,
authentication & roles, production DB/cloud deployment, duplicate-complaint
detection, and a model feedback loop.
