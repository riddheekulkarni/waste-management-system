# EcoClean Civic

EcoClean Civic is an AI-powered municipal civic waste reporting system. Citizens upload
photos of illegal dumping or overflowing waste, the detection pipeline
identifies waste items, a rule-based engine grades severity, and the complaint
is automatically routed to the appropriate municipal department. Citizens can track reports
on an interactive map, while authenticated admins can review analytics, inspect geospatial distribution, and manage ticket resolution workflows.

---

## Key Features & Implementations (Branch: `chaitanya`)

- **AI Waste Detection Pipeline**: Supports real YOLOv8 custom weights or demo-ready mock detector fallback.
- **Rule-Based Severity & Department Routing**: Calculates waste area coverage and item counts to assign Low / Medium / High severity and route to Sanitation, Recycling, Health & Hazmat, or Public Works.
- **Geospatial Duplicate Complaint Detection**: Automatically calculates Haversine distance for location-tagged uploads. Issues within 50 meters of existing open reports are flagged and linked to prevent redundant municipal dispatches.
- **Real-Time Citizen Notification Hook**: Dispatches status update notifications to citizens when tickets transition between Open, In Progress, and Resolved.
- **Role-Based Access Control (RBAC)**: Secure authentication with citizen self-registration and protected admin portal routes (`@require_role("admin")`).
- **Geospatial Analytics API**: Provides `/api/analytics/geo` returning location coordinates and severity data for admin incident mapping.
- **Production-Ready Containerization & Deployment**: Dockerized architecture with `Dockerfile`, `docker-compose.yml` (Flask + Gunicorn + PostgreSQL), `gunicorn.conf.py`, and `.env.example`.
- **Comprehensive Test Suite**: Automated test suite (`pytest`) covering authentication, detection, severity engine, duplicate detection, and analytics.

---

## File Structure

```
waste-management-system/
├── backend/
│   ├── app.py                  # Flask app factory + entry point, serves frontend too
│   ├── config.py               # App configuration (DB path, upload folder, secrets)
│   ├── models.py               # SQLAlchemy models (User, Complaint, DetectionItem, distance calc)
│   ├── detection.py            # Stage 1 — YOLOv8 wrapper (real + mock modes, image validation)
│   ├── severity.py             # Stage 2a — coverage-ratio severity engine
│   ├── routing.py              # Stage 2b — waste-class → department mapping
│   ├── notifications.py        # Citizen notification engine (log, email, SMS hooks)
│   ├── gunicorn.conf.py        # WSGI production server configuration
│   ├── Dockerfile              # Container definition for backend service
│   ├── routes/
│   │   ├── auth.py             # Register, login, logout, me endpoints & RBAC decorators
│   │   ├── complaints.py       # /api/complaints/* endpoints & duplicate detection
│   │   └── analytics.py        # /api/analytics/* summary & geo endpoints
│   ├── tests/                  # Automated pytest test suite
│   │   ├── conftest.py
│   │   ├── test_app.py
│   │   └── test_engine.py
│   ├── requirements.txt
│   ├── uploads/                # Uploaded photos stored here (auto-created)
│   └── waste_management.db     # SQLite database (auto-created on first run)
├── frontend/
│   ├── index.html              # Single-page app: Report / Track / Admin tabs
│   ├── css/styles.css
│   └── js/app.js               # Fetch calls to backend API, map & chart rendering
├── docker-compose.yml          # Docker Compose orchestration (Flask + Postgres)
├── .env.example                # Environment variables template
├── future_scope_roadmap.md     # Detailed plan & completed milestones
└── README.md
```

---

## Setup & Local Execution

### Local Python Server

```bash
cd backend
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5050** in a browser — Flask serves both the REST API and the frontend single-page app.

### Running Tests

```bash
cd backend
pytest tests
```

---

## Docker Production Deployment

To run the application using Docker Compose (Flask backend + PostgreSQL database):

```bash
# Copy environment variables
cp .env.example .env

# Build and launch containers
docker-compose up --build
```

Access the production deployment at **http://localhost:5050**.

---

## Training the Real Detection Model

By default the app runs with a **mock detector** that generates plausible
synthetic detections — this lets you run and demo the full system without a GPU.

To switch to real YOLOv8 inference:

1. Open **`train_waste_yolov8.ipynb`** in [Google Colab](https://colab.research.google.com)
2. Set the runtime to **T4 GPU** (`Runtime → Change runtime type`)
3. Run all cells — the notebook will:
   - Download the TACO dataset via Roboflow (~30 s)
   - Remap 60 categories → 9 EcoClean waste classes
   - Train `yolov8s.pt` for up to 100 epochs (~30–45 min)
   - Save `best.pt` to your Google Drive
4. Download `best.pt` from Drive
5. Set the env var and restart the server:
   ```bash
   WASTE_MODEL_WEIGHTS=/path/to/best.pt python app.py
   ```

The app **auto-switches** to real inference — no code changes needed.
The startup log will confirm: `🤖 WasteDetector: REAL mode`.

## Demo Accounts

| Role | Email | Password |
|---|---|---|
| Citizen | `citizen@civic.gov` | `citizen123` |
| Admin | `admin@civic.gov` | `admin123` |

---

## API Reference

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/complaints/upload` | Submit a photo (+ optional lat/lng), runs detection, duplicate check & severity pipeline |
| POST | `/api/complaints/check-duplicate` | Check if an open complaint exists within 50m radius |
| GET | `/api/complaints` | List complaints (filter by `status`, `department`, `severity`, `my_complaints`) |
| GET | `/api/complaints/<id>` | Full detail for one ticket, incl. detections |
| PATCH | `/api/complaints/<id>/status` | Update ticket status (`Open` / `In Progress` / `Resolved`) & notify citizen |
| GET | `/api/analytics/summary` | Aggregate counts by severity/department/status (Admin only) |
| GET | `/api/analytics/geo` | Geospatial points with severities and departments (Admin only) |
| POST | `/api/auth/register` | Register a citizen account |
| POST | `/api/auth/login` | Sign in with username or email |
| POST | `/api/auth/logout` | End current session |
| GET | `/api/auth/me` | Return currently signed-in user |

