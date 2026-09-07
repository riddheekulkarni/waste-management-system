<div align="center">

```
███████╗ ██████╗ ██████╗  ██████╗██╗     ███████╗ █████╗ ███╗   ██╗
██╔════╝██╔════╝██╔═══██╗██╔════╝██║     ██╔════╝██╔══██╗████╗  ██║
█████╗  ██║     ██║   ██║██║     ██║     █████╗  ███████║██╔██╗ ██║
██╔══╝  ██║     ██║   ██║██║     ██║     ██╔══╝  ██╔══██║██║╚██╗██║
███████╗╚██████╗╚██████╔╝╚██████╗███████╗███████╗██║  ██║██║ ╚████║
╚══════╝ ╚═════╝ ╚═════╝  ╚═════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝
                        ██████╗██╗██╗   ██╗██╗ ██████╗
                       ██╔════╝██║██║   ██║██║██╔════╝
                       ██║     ██║██║   ██║██║██║
                       ██║     ██║╚██╗ ██╔╝██║██║
                       ╚██████╗██║ ╚████╔╝ ██║╚██████╗
                        ╚═════╝╚═╝  ╚═══╝  ╚═╝ ╚═════╝
```

### 🗑️ AI-Powered Municipal Waste Reporting & Routing System

<br/>

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.x-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-FF5733?style=for-the-badge&logo=yolo&logoColor=white)](https://ultralytics.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-PostGIS-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![pytest](https://img.shields.io/badge/Tests-pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)](https://pytest.org)
[![License](https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge)](LICENSE)
[![Branch](https://img.shields.io/badge/Branch-chaitanya-8B5CF6?style=for-the-badge&logo=git&logoColor=white)](https://github.com/riddheekulkarni/waste-management-system/tree/chaitanya)

<br/>

> **Citizens snap. AI detects. Departments act.** — EcoClean Civic turns a photo of illegal dumping into a routed, tracked, and notified municipal complaint in seconds.

<br/>

---

</div>

## 🧠 How It Works

```
  📸 Citizen uploads photo
          │
          ▼
  ┌───────────────────┐
  │  Stage 1: YOLOv8  │  ← Detects waste items + bounding boxes
  │  Detection Engine │     (9 classes: plastic, glass, hazardous…)
  └────────┬──────────┘
           │
           ▼
  ┌───────────────────┐
  │  Stage 2a:        │  ← Coverage ratio + item count
  │  Severity Engine  │     → Low / Medium / High
  └────────┬──────────┘
           │
           ▼
  ┌───────────────────┐
  │  Stage 2b:        │  ← Waste class → Department mapping
  │  Smart Routing    │     Sanitation / Recycling / Hazmat / Public Works
  └────────┬──────────┘
           │
           ▼
  ┌───────────────────┐
  │  Duplicate Check  │  ← Haversine distance ≤ 50m?
  │  (Geospatial)     │     If yes → link to existing ticket
  └────────┬──────────┘
           │
           ▼
  ┌───────────────────┐
  │  Ticket Created   │  ← Stored in DB, citizen gets ticket ID
  │  + Notification   │     Admin dashboard updates in real time
  └───────────────────┘
```

---

## ⚡ Feature Matrix

| Feature | Status | Details |
|---------|:------:|---------|
| 🤖 YOLOv8 AI Detection | ✅ | Real model OR mock fallback — zero config needed |
| 📊 Severity Engine | ✅ | Coverage ratio + item count → Low/Medium/High |
| 🗺️ Smart Department Routing | ✅ | 9 waste classes mapped to 4 departments |
| 📍 Geospatial Duplicate Detection | ✅ | Haversine 50m radius dedup on every upload |
| 🔔 Citizen Notifications | ✅ | Status change hooks (log + Twilio/email ready) |
| 🔐 Auth + RBAC | ✅ | Session auth, `@require_role("admin")` decorator |
| 📈 Admin Analytics API | ✅ | Summary + geo endpoints for map + chart dashboards |
| 🐳 Docker Production Stack | ✅ | Flask + Gunicorn + PostgreSQL via Compose |
| 🧪 Automated Test Suite | ✅ | `pytest` — auth, detection, severity, dedup, analytics |
| 🏋️ Custom Model Training | 🔄 | Colab notebook ready → run once to get `best.pt` |

---

## 🚀 Quick Start

### Option A — Local Python (30 seconds)

```bash
git clone https://github.com/riddheekulkarni/waste-management-system.git
cd waste-management-system/backend
pip install -r requirements.txt
python app.py
```

Open → **[http://localhost:5050](http://localhost:5050)**

### Option B — Docker (production stack)

```bash
cp .env.example .env          # configure your secrets
docker-compose up --build     # Flask + Gunicorn + PostgreSQL
```

Open → **[http://localhost:5050](http://localhost:5050)**

### Run the Test Suite

```bash
cd backend
pytest tests -v
```

---

## 🤖 Training the Real AI Model

> By default, the app runs with a **mock detector** so you can demo everything instantly — no GPU needed.
> When you're ready for real inference, follow these steps:

```
Step 1 → Open train_waste_yolov8.ipynb in Google Colab
Step 2 → Runtime → Change runtime type → T4 GPU
Step 3 → Run all cells  (~35 min)
           ├── Downloads TACO dataset via Roboflow
           ├── Remaps 60 labels → 9 EcoClean classes
           ├── Fine-tunes yolov8s.pt (100 epochs)
           └── Saves best.pt to Google Drive
Step 4 → Download best.pt from Drive to your machine
Step 5 → Add to .env:
           WASTE_MODEL_WEIGHTS=/path/to/best.pt
Step 6 → Restart Flask
           🤖 WasteDetector: REAL mode ← look for this in logs
```

**The backend auto-switches. Zero code changes.**

---

## 🗂️ Project Structure

```
waste-management-system/
│
├── 🧠 backend/
│   ├── app.py                  # Flask factory — boots DB, seeds users, logs detector mode
│   ├── config.py               # All config from env vars
│   ├── models.py               # User · Complaint · DetectionItem + Haversine distance
│   ├── detection.py            # YOLOv8 wrapper: real mode ↔ mock fallback
│   ├── severity.py             # Coverage-ratio severity engine (Low/Medium/High)
│   ├── routing.py              # Waste class → department mapper
│   ├── notifications.py        # Notification engine (log + Twilio/email hooks)
│   ├── gunicorn.conf.py        # Production WSGI config
│   ├── Dockerfile              # Container image definition
│   │
│   ├── routes/
│   │   ├── auth.py             # /api/auth/* — register, login, logout, me + RBAC
│   │   ├── complaints.py       # /api/complaints/* — upload, dedup, list, status
│   │   └── analytics.py        # /api/analytics/* — summary + geo heatmap data
│   │
│   └── tests/
│       ├── conftest.py         # Fixtures: test app, test client, seeded DB
│       ├── test_app.py         # Auth, upload, status, analytics integration tests
│       └── test_engine.py      # Unit tests: severity engine, routing, detection
│
├── 🎨 frontend/
│   ├── index.html              # SPA: Report / Track / Admin tabs
│   ├── css/styles.css          # Full design system
│   └── js/app.js               # API calls, Leaflet map, Chart.js dashboards
│
├── 📓 train_waste_yolov8.ipynb # Colab notebook: TACO → 9-class → best.pt
├── 🐳 docker-compose.yml       # Flask + Postgres orchestration
├── 📋 .env.example             # All env vars documented with examples
└── 📖 future_scope_roadmap.md  # Feature status tracker
```

---

## 🔑 Demo Accounts

| Role | Email | Password | Access |
|------|-------|----------|--------|
| 👤 Citizen | `citizen@civic.gov` | `citizen123` | Submit & track own complaints |
| 🛡️ Admin | `admin@civic.gov` | `admin123` | Full dashboard, analytics, status updates |

---

## 📡 API Reference

### Complaints

| Method | Endpoint | Auth | Description |
|--------|----------|:----:|-------------|
| `POST` | `/api/complaints/upload` | Optional | Upload photo → detect → severity → route → store |
| `POST` | `/api/complaints/check-duplicate` | — | Check 50m radius for existing open ticket |
| `GET` | `/api/complaints` | Optional | List all (filter: `status`, `department`, `severity`, `my_complaints`) |
| `GET` | `/api/complaints/<id>` | — | Full ticket detail including detections |
| `PATCH` | `/api/complaints/<id>/status` | 🛡️ Admin | Update status + fire citizen notification |

### Analytics

| Method | Endpoint | Auth | Description |
|--------|----------|:----:|-------------|
| `GET` | `/api/analytics/summary` | 🛡️ Admin | Counts by severity / department / status |
| `GET` | `/api/analytics/geo` | 🛡️ Admin | Geo points + severity for map heatmap |

### Auth

| Method | Endpoint | Auth | Description |
|--------|----------|:----:|-------------|
| `POST` | `/api/auth/register` | — | Register new citizen account |
| `POST` | `/api/auth/login` | — | Sign in (username or email) |
| `POST` | `/api/auth/logout` | — | End session |
| `GET` | `/api/auth/me` | ✅ | Return current user |

---

## 🗺️ Roadmap

```
✅ Completed          🔄 In Progress          ⏳ Future
```

| # | Feature | Status |
|---|---------|:------:|
| 1 | Custom YOLOv8 model training (TACO dataset) | 🔄 Notebook ready — needs GPU run |
| 2 | Native mobile app (React Native / Flutter) | ⏳ |
| 3 | Real-time citizen notifications | ✅ |
| 4 | Authentication & Role-Based Access Control | ✅ |
| 5 | Production database & Docker deployment | ✅ |
| 6 | Admin geospatial map + analytics | ✅ |
| 7 | Duplicate complaint detection (Haversine) | ✅ |
| 8 | Continuous learning / model feedback loop | ⏳ |

---

## 🛠️ Tech Stack

<div align="center">

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.10 · Flask · SQLAlchemy |
| **AI / ML** | YOLOv8 (Ultralytics) · TACO Dataset · Roboflow |
| **Database** | SQLite (dev) · PostgreSQL + PostGIS (prod) |
| **Auth** | Werkzeug password hashing · Flask sessions · RBAC |
| **Geospatial** | Haversine distance · Leaflet.js |
| **Production** | Docker · Gunicorn · Docker Compose |
| **Testing** | pytest · Flask test client |
| **Frontend** | Vanilla HTML/CSS/JS · Chart.js · Leaflet |

</div>

---

<div align="center">

**Built with 🌱 to make cities cleaner.**

*EcoClean Civic — Branch `chaitanya`*

</div>
