# Future Scope — Detailed Roadmap (Remaining ~10–20%)

This expands each remaining item referenced in the README. Each section
explains **why** it isn't built yet, **what** it involves, and includes a
design sketch or skeleton so it can be picked up next.

---

## 1. Custom YOLOv8 Training Pipeline on an Annotated Civic-Waste Dataset

**Why not done yet:** requires an annotated dataset (YOLO-format bounding
boxes) of civic waste images and GPU time to fine-tune — `backend/detection.py`
uses a mock detector precisely so the rest of the system (severity, routing,
API, frontend, database) can be built and tested before this is ready.

**What it involves:**
- Combine a public base (TACO — Trash Annotations in Context) with custom
  photos of local street-waste scenes.
- Annotate into the 9 classes already defined in `detection.py`
  (`WASTE_CLASSES`) using Roboflow or CVAT.
- Fine-tune on a free Google Colab T4 GPU.

**Training script skeleton:**
```python
from ultralytics import YOLO

model = YOLO("yolov8s.pt")
model.train(data="waste_dataset/data.yaml", epochs=100, imgsz=640,
            batch=16, optimizer="AdamW", lr0=0.001)
model.val()
model.export(format="onnx")
```
Point the app at the result: `export WASTE_MODEL_WEIGHTS=/path/to/best.pt`
— `WasteDetector` already auto-switches to real inference, no code changes
needed.

---

## 2. Native Mobile App

**Why not done yet:** the current frontend is a responsive web page, which
covers the "upload a photo" use case but not offline capture or native
camera/GPS integration.

**What it involves:** a React Native or Flutter wrapper around the same
`/api/complaints/*` endpoints already built, adding native camera capture,
background upload retry, and push notification support (see item #3).

---

## 3. Real-Time Citizen Notifications

**Why not done yet:** requires a third-party service account (Twilio for
SMS, Firebase Cloud Messaging for push) not set up at this stage.

**What it involves:** trigger a notification inside the status-update route.

**Skeleton hook — add to `backend/routes/complaints.py`:**
```python
def notify_citizen(ticket_id: str, new_status: str):
    # twilio_client.messages.create(
    #     body=f"Your complaint {ticket_id} is now '{new_status}'.",
    #     from_=TWILIO_NUMBER, to=citizen_phone_number,
    # )
    pass

# call notify_citizen(ticket_id, new_status) after db.session.commit()
# inside update_status()
```

---

## 4. Authentication & Role-Based Access Control

**Why not done yet:** the API is currently open for local development/demo
purposes.

**What it involves:** three roles — Citizen (submit/view own complaints),
Department Staff (view/update only their department's tickets), Admin (full
access + analytics). Implement with Flask-JWT-Extended; add a `role` column
to a new `users` table and check it in each route via a decorator, e.g.
`@require_role("admin")`.

---

## 5. Production Database & Cloud Deployment

**Why not done yet:** SQLite (used now) is ideal for local development and
demoing, but not for concurrent multi-user production traffic or geospatial
queries.

**What it involves:**
- Migrate `backend/models.py` from SQLite to PostgreSQL + PostGIS (for
  proper geospatial queries — needed by item #7 below). SQLAlchemy makes
  this mostly a config change (`SQLALCHEMY_DATABASE_URI`) plus changing the
  `latitude`/`longitude` float columns to a single `GEOGRAPHY(POINT)` column.
- Containerize with Docker (`backend/Dockerfile` + `docker-compose.yml`
  wiring the Flask app to a Postgres container).
- Deploy behind gunicorn on a cloud host; add CI/CD for automated
  test/deploy on push.

---

## 6. Municipal Admin Analytics — Map View

**Why not done yet:** the current admin dashboard (already implemented)
shows severity/department charts and a sortable table, but not a
geospatial heatmap — that needs enough live GPS-tagged complaints to be
meaningful, plus a mapping library.

**What it involves:** add a Leaflet or Mapbox map to `frontend/js/app.js`'s
admin tab, plotting each complaint's `latitude`/`longitude` colored by
severity, backed by a new `GET /api/analytics/geo` endpoint.

---

## 7. Geospatial Duplicate-Complaint Detection

**Why not done yet:** depends on the production geospatial database (#5)
and enough real GPS-tagged submissions.

**What it involves:** when a new complaint arrives, query existing open
tickets within a small radius (e.g. 50m) and a recent time window; if
found, link the new report to the existing ticket instead of creating a
duplicate, reducing redundant department dispatches.

---

## 8. Continuous Learning / Model Feedback Loop

**Why not done yet:** requires the system to be live long enough for
departments to generate outcome data.

**What it involves:** when a department resolves a ticket, let them confirm
or correct the detected waste type/severity via the admin UI. Periodically
export these corrections as new labeled training examples and re-run the
training pipeline from item #1 — closing the loop between real-world
outcomes and model accuracy.

---

### Summary

| # | Feature | Depends on |
|---|---------|-----------|
| 1 | Custom YOLOv8 training | Annotated dataset, GPU |
| 2 | Native mobile app | Existing API (already built) |
| 3 | Notifications | Twilio/Firebase account |
| 4 | Auth & RBAC | — |
| 5 | Production DB & deployment | — |
| 6 | Admin map view | Live GPS data, #5 |
| 7 | Duplicate detection | #5, #6 |
| 8 | Feedback loop | #1, live deployment |

These are the pieces that take the working application in this repository
from a functioning prototype to a deployable municipal system.
