# Future Scope — Roadmap & Status

This document tracks each roadmap item from the original plan: what is **done**,
what is **in progress**, and what remains for the future.

---

## ✅ 3. Real-Time Citizen Notifications — **IMPLEMENTED**

**Implemented in:** `backend/notifications.py`, called from `routes/complaints.py`
`update_status()`.

`notify_citizen(ticket_id, new_status)` fires on every ticket status transition.
The function logs the notification and contains ready-to-uncomment hooks for
Twilio SMS and email. Plug in credentials and uncomment to go live.

---

## ✅ 4. Authentication & Role-Based Access Control — **IMPLEMENTED**

**Implemented in:** `backend/routes/auth.py`

Three roles — Citizen, Admin — with `@require_role("admin")` decorators protecting
analytics and status-update routes. Session-based auth with hashed passwords via
Werkzeug. Demo accounts seeded on startup (see README).

---

## ✅ 5. Production Database & Cloud Deployment — **IMPLEMENTED**

**Implemented in:** `backend/Dockerfile`, `docker-compose.yml`,
`backend/gunicorn.conf.py`, `.env.example`

- `docker-compose.yml` wires Flask (gunicorn) to a PostgreSQL container.
- `DATABASE_URL` env var switches between SQLite (dev) and PostgreSQL (prod).
- `Dockerfile` and `gunicorn.conf.py` provide production-grade WSGI serving.

---

## ✅ 6. Municipal Admin Analytics — Map View — **IMPLEMENTED**

**Implemented in:** `backend/routes/analytics.py` (`GET /api/analytics/geo`),
`frontend/js/app.js` (Leaflet map rendering in Admin tab).

Returns all geo-tagged complaints with severity and department metadata for
the admin map view.

---

## ✅ 7. Geospatial Duplicate-Complaint Detection — **IMPLEMENTED**

**Implemented in:** `backend/routes/complaints.py` (`find_nearby_duplicate()`),
`backend/models.py` (`Complaint.haversine_distance()`).

Haversine distance calculation flags new complaints within 50 m of an existing
open ticket and links them, preventing redundant municipal dispatches.

---

## 🔄 1. Custom YOLOv8 Training Pipeline — **IN PROGRESS**

**What's done:** `train_waste_yolov8.ipynb` is in the project root — a fully
self-contained Google Colab notebook that:
- Downloads the public TACO dataset via Roboflow
- Remaps 60 TACO categories → 9 EcoClean waste classes
- Fine-tunes `yolov8s.pt` for 100 epochs on a free T4 GPU
- Exports `best.pt` to Google Drive
- Prints mAP50 / mAP50-95 validation metrics

**What still needs to happen:**
1. Run the notebook (~30–45 min on Colab T4)
2. Download `best.pt` from Google Drive
3. Set `WASTE_MODEL_WEIGHTS=/path/to/best.pt` in `.env`

The backend **auto-switches** from mock → real inference — no code changes needed.

**Training script skeleton** (inside the notebook):
```python
from ultralytics import YOLO
model = YOLO("yolov8s.pt")
model.train(data="taco_remapped/data.yaml", epochs=100, imgsz=640,
            batch=16, optimizer="AdamW", lr0=0.001, patience=20)
```

---

## ⏳ 2. Native Mobile App — **FUTURE**

**Why not done yet:** The current frontend is a responsive web app. Native
camera/GPS integration and push notification support require a React Native or
Flutter wrapper.

**What it involves:** wrap the existing `/api/complaints/*` endpoints (already
built) with native camera capture, background upload retry, and push
notifications (Firebase Cloud Messaging). The API is ready; only the shell app
needs building.

---

## ⏳ 8. Continuous Learning / Model Feedback Loop — **FUTURE**

**Why not done yet:** Requires the system to be live long enough for departments
to generate outcome data, and depends on item #1 being deployed.

**What it involves:** when a department resolves a ticket, let them confirm or
correct the detected waste type/severity via the admin UI. Periodically export
these corrections as new labeled training examples and re-run the notebook from
item #1 — closing the loop between real-world outcomes and model accuracy.

---

### Summary

| # | Feature | Status |
|---|---------|--------|
| 1 | Custom YOLOv8 training | 🔄 In progress — notebook ready, needs GPU run |
| 2 | Native mobile app | ⏳ Future |
| 3 | Real-time notifications | ✅ Implemented |
| 4 | Auth & RBAC | ✅ Implemented |
| 5 | Production DB & deployment | ✅ Implemented |
| 6 | Admin map view | ✅ Implemented |
| 7 | Duplicate detection | ✅ Implemented |
| 8 | Feedback loop | ⏳ Future (depends on #1 + live deployment) |
