<div align="center">

```
███████╗ ██████╗  ██████╗  ██████╗██╗     ███████╗ █████╗ ███╗   ██╗
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

### AI-Powered Municipal Waste Reporting & Civic Issue Management Platform

> **Cleaner streets. Smarter civic response.**

<br/>

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.x-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-FF5733?style=for-the-badge)](https://ultralytics.com)
[![Redis](https://img.shields.io/badge/Redis-RQ-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![Tests](https://img.shields.io/badge/Tests-119%20passing-22C55E?style=for-the-badge&logo=pytest&logoColor=white)](https://pytest.org)

</div>

---

## What It Does

EcoClean Civic turns a citizen photo of illegal waste dumping into a **fully tracked, AI-verified, departmentally routed, and resolved municipal complaint** — with real-time updates at every step.

```
  Citizen uploads photo
          │
          ▼
  YOLOv8 Detection     ← 9 waste classes: plastic, glass, hazardous, metal, …
          │
          ▼
  Severity Engine      ← Coverage ratio + item count → Low / Medium / High
          │
          ▼
  Smart Routing        ← Waste class → Department (Sanitation / Recycling / Hazmat / Works)
          │
          ▼
  Duplicate Check      ← Haversine ≤ 50m → linked to existing ticket if found
          │
          ▼
  Ticket Created       ← Real-time SSE updates to citizen + admin dashboard
          │
          ▼
  Field Resolution     ← Admin submits evidence photo + note
          │
          ▼
  Citizen Feedback     ← CONFIRMED → RESOLVED  |  NEEDS ATTENTION → back to IN_PROGRESS
```

---

## Feature Matrix

| Feature | Status |
|---------|:------:|
| YOLOv8 AI waste detection (REAL_YOLO / MOCK_DEMO) | ✅ |
| Overlap-aware severity engine (Low / Medium / High) | ✅ |
| Smart department routing (9 waste classes → 4 departments) | ✅ |
| Geospatial duplicate detection (Haversine 50m radius) | ✅ |
| Flask-Migrate / Alembic database migrations | ✅ |
| Authentication + Role-Based Access Control (citizen / admin) | ✅ |
| Complaint ownership enforcement on all citizen endpoints | ✅ |
| Secure private image access (resolution + feedback photos) | ✅ |
| Async AI processing with RQ + Redis background workers | ✅ |
| Complaint lifecycle state machine (7 canonical states) | ✅ |
| Job retry and idempotency | ✅ |
| Real-time Server-Sent Events (SSE) | ✅ |
| Citizen reporting wizard (guided 3-step flow) | ✅ |
| Citizen complaint tracking dashboard | ✅ |
| Municipal Operations Center (admin dashboard) | ✅ |
| Live admin complaint queue + triage | ✅ |
| Live incident map (Leaflet.js) | ✅ |
| Chart.js analytics (severity, department, timeline) | ✅ |
| Civic Intelligence Layer (geospatial clustering, hotspots) | ✅ |
| Operational alerts + notification center | ✅ |
| System health diagnostics | ✅ |
| Field resolution evidence submission (photo + note) | ✅ |
| Citizen feedback loop (CONFIRMED / NEEDS ATTENTION) | ✅ |
| Admin feedback queue + operational metrics | ✅ |
| Docker + Gunicorn production stack | ✅ |
| 119 automated tests (pytest) | ✅ |
| Rate limiting (Flask-Limiter) | ✅ |
| Security headers (X-Frame, X-Content-Type, HSTS) | ✅ |

---

## Quick Start

### Local Python (30 seconds)

```bash
git clone https://github.com/riddheekulkarni/waste-management-system.git
cd waste-management-system
pip install -r backend/requirements.txt
python run.py
# Or with custom options: python run.py --port 5050 --host 0.0.0.0
```

Open → **http://localhost:5050**

### Seed Demo Data

```bash
cd backend
python seed.py
```

Creates demo accounts and 6 realistic sample complaints.

### Docker (production stack)

```bash
cp .env.example .env     # configure your secrets (SECRET_KEY, POSTGRES_PASSWORD)
docker-compose up --build
```

Open → **http://localhost:5050**

Migration runs automatically on container start:

```bash
flask db upgrade
```

### Run Tests

```bash
pytest -q
# 119 passed
```

---

## Demo Accounts

| Role | Username | Password | Access |
|------|----------|----------|--------|
| Citizen | `citizen` | `citizen123` | Submit & track own complaints |
| Admin | `admin` | `admin123` | Full Municipal Operations Center |

> ⚠️ Demo credentials are for local development only. Never deploy with these credentials.

---

## Enabling Real YOLOv8 Inference

By default the app runs `MOCK_DEMO` mode — no GPU needed, perfect for demos.

To enable real inference:

```
1. Open train_waste_yolov8.ipynb in Google Colab
2. Runtime → T4 GPU → Run all cells (~35 min)
   - Downloads TACO dataset via Roboflow
   - Fine-tunes yolov8s.pt (100 epochs, 9 EcoClean classes)
   - Saves best.pt to Google Drive
3. Download best.pt to your machine
4. In .env:
   WASTE_MODEL_WEIGHTS=/absolute/path/to/best.pt
   AI_EXECUTION_MODE=REAL_YOLO
5. Restart the server — logs will confirm: REAL mode active
```

---

## AI Model Evaluation & Benchmark Metrics

The EcoClean Civic waste detection pipeline is powered by a fine-tuned **YOLOv8s** architecture trained on the open-source **TACO** (Trash Annotations in Context) dataset mapped to 9 canonical civic categories: `plastic_bottle`, `polythene_bag`, `can_metal`, `cardboard`, `paper`, `glass`, `organic_waste`, `hazardous`, and `mixed_litter`.

### Benchmark Performance Summary

| Metric | Target | Achieved | Status |
|--------|:------:|:--------:|:------:|
| **mAP@0.50** | ≥ 0.700 | **0.760** | ✅ Passed |
| **mAP@0.50-0.95** | ≥ 0.450 | **0.521** | ✅ Passed |
| **Precision** | ≥ 0.750 | **0.821** | ✅ Passed |
| **Recall** | ≥ 0.700 | **0.778** | ✅ Passed |
| **Inference Latency (T4 GPU)** | ≤ 30 ms | **18.4 ms** | ✅ Passed |

Comprehensive high-resolution evaluation figures and confusion matrices are maintained in [`report_assets/`](report_assets/README.md):

| Training Dashboard & Curves | Per-Class mAP@50 Scores |
|:---:|:---:|
| [![Training Dashboard](report_assets/03_training_dashboard.png)](report_assets/03_training_dashboard.png) | [![Per-Class mAP@50](report_assets/04_per_class_map50.png)](report_assets/04_per_class_map50.png) |
| *Figure 1: Full training dashboard across 100 epochs* | *Figure 2: Per-class mAP@50 performance across 9 waste classes* |

| Precision-Recall Curves | Metrics Summary & Hyperparameters |
|:---:|:---:|
| [![Precision-Recall Curve](report_assets/06_pr_curve.png)](report_assets/06_pr_curve.png) | [![Metrics Summary](report_assets/07_metrics_summary_table.png)](report_assets/07_metrics_summary_table.png) |
| *Figure 3: Multi-class Precision-Recall curves with AUC scores* | *Figure 4: Final model evaluation summary table* |

For deeper architecture analysis, bounding box normalization, and sweep-line severity calculations, see [YOLO_INTEGRATION.md](YOLO_INTEGRATION.md).

---

## API Reference

### Auth

| Method | Endpoint | Auth | Description |
|--------|----------|:----:|-------------|
| `POST` | `/api/auth/register` | — | Register citizen account |
| `POST` | `/api/auth/login` | — | Sign in (username or email) |
| `POST` | `/api/auth/logout` | — | End session |
| `GET` | `/api/auth/me` | ✅ | Current user |
| `GET` | `/api/auth/users` | 🛡️ | List users (paginated) |

### Complaints

| Method | Endpoint | Auth | Description |
|--------|----------|:----:|-------------|
| `POST` | `/api/complaints/upload` | ✅ | Upload photo → AI pipeline |
| `POST` | `/api/complaints/check-duplicate` | ✅ | Geospatial duplicate check |
| `GET` | `/api/complaints` | ✅ | List complaints (paginated, filterable) |
| `GET` | `/api/complaints/<id>` | ✅ | Ticket detail + detections |
| `GET` | `/api/complaints/<id>/processing-status` | ✅ | Lightweight async status poll |
| `POST` | `/api/complaints/<id>/retry-processing` | 🛡️ | Retry failed AI job |
| `PATCH` | `/api/complaints/<id>/status` | 🛡️ | Update status + notify citizen |
| `POST` | `/api/complaints/<id>/resolution` | 🛡️ | Submit field resolution evidence |
| `GET` | `/api/complaints/<id>/resolution` | ✅ | View resolution details |
| `POST` | `/api/complaints/<id>/feedback` | ✅ | Citizen feedback (CONFIRMED / NEEDS_ATTENTION) |
| `GET` | `/api/complaints/<id>/feedback` | ✅ | Feedback history |
| `GET` | `/api/complaints/<id>/events` | ✅ | SSE stream (citizen) |
| `GET` | `/api/complaints/admin/events` | 🛡️ | SSE stream (admin) |

### Admin

| Method | Endpoint | Auth | Description |
|--------|----------|:----:|-------------|
| `GET` | `/api/admin/overview` | 🛡️ | Operations center metrics |
| `GET` | `/api/admin/analytics` | 🛡️ | Time-range analytics |
| `GET` | `/api/admin/departments` | 🛡️ | Department workload |
| `GET` | `/api/admin/map` | 🛡️ | Live incident map points |
| `GET` | `/api/admin/map/aggregate` | 🛡️ | Geospatial heatmap cells |
| `GET` | `/api/admin/geospatial` | 🛡️ | Cluster hotspot analysis |
| `GET` | `/api/admin/insights` | 🛡️ | Operational intelligence metrics |
| `GET` | `/api/admin/feedback` | 🛡️ | Citizen feedback queue |
| `GET` | `/api/admin/system-health` | 🛡️ | System diagnostics |
| `GET` | `/api/admin/notifications` | 🛡️ | Operational alerts |
| `PATCH` | `/api/admin/notifications/<id>/read` | 🛡️ | Mark alert read |
| `POST` | `/api/admin/notifications/read-all` | 🛡️ | Mark all alerts read |
| `GET` | `/api/health` | — | System health check probe (Docker / K8s) |

### Images

| Method | Endpoint | Auth | Description |
|--------|----------|:----:|-------------|
| `GET` | `/uploads/<filename>` | ✅ | Secured private image access |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.10 · Flask · SQLAlchemy · Flask-Migrate (Alembic) |
| **AI / ML** | YOLOv8 (Ultralytics) · TACO Dataset · Roboflow |
| **Async Processing** | RQ (Redis Queue) · Redis Pub/Sub |
| **Real-time** | Server-Sent Events (SSE) |
| **Database** | SQLite (dev) · PostgreSQL (prod) |
| **Auth** | Werkzeug password hashing · Flask sessions · RBAC |
| **Geospatial** | Haversine distance · Leaflet.js |
| **Rate Limiting** | Flask-Limiter |
| **Production** | Docker · Gunicorn · Docker Compose |
| **Testing** | pytest · Flask test client — 119 tests |
| **Frontend** | Vanilla HTML/CSS/JS · Chart.js · Leaflet |

---

## Project Structure

```
waste-management-system/
│
├── backend/
│   ├── app.py              # Flask factory — security headers, error handlers
│   ├── config.py           # All config from env vars; production secret validation
│   ├── models.py           # User · Complaint · DetectionItem · Notification · CitizenFeedback
│   ├── lifecycle.py        # Canonical state machine — 7 lifecycle states
│   ├── detection.py        # YOLOv8 wrapper: REAL_YOLO ↔ MOCK_DEMO
│   ├── severity.py         # Overlap-aware severity engine
│   ├── routing.py          # Waste class → department mapper
│   ├── events.py           # SSE + Redis Pub/Sub event layer
│   ├── tasks.py            # RQ background AI processing pipeline
│   ├── notifications.py    # Notification engine (log / SMTP / SendGrid)
│   ├── ai_config.py        # Canonical waste classes + department map
│   ├── job_queue.py        # RQ queue / sync fallback
│   ├── worker.py           # RQ worker process entrypoint
│   ├── seed.py             # Demo data seeder (dev only)
│   ├── gunicorn.conf.py    # Production WSGI config
│   ├── Dockerfile          # Container image
│   ├── requirements.txt
│   ├── migrations/         # Alembic migration scripts
│   ├── routes/
│   │   ├── auth.py         # /api/auth/*
│   │   ├── complaints.py   # /api/complaints/*
│   │   ├── admin.py        # /api/admin/*
│   │   ├── analytics.py    # /api/analytics/*
│   │   └── notifications.py # /api/notifications/*
│   └── tests/              # 119 pytest tests (Phases 1–8)
│
├── frontend/
│   ├── index.html          # SPA — citizen + admin views
│   ├── css/styles.css      # Design system
│   └── js/app.js           # API integration, SSE, maps, charts
│
├── docker-compose.yml      # Flask + PostgreSQL + Redis + Worker
├── .env.example            # All env vars documented
├── best.pt                 # YOLOv8 waste detection model weights
└── train_waste_yolov8.ipynb # Colab training notebook
```

---

## Production Deployment

### Required Environment Variables (production)

```bash
SECRET_KEY=<cryptographically-random-64-char-hex>  # MANDATORY
DATABASE_URL=postgresql://user:pass@host:5432/db   # MANDATORY
FLASK_ENV=production
REDIS_URL=redis://redis:6379/0
ASYNC_MODE=redis
AI_EXECUTION_MODE=REAL_YOLO         # or MOCK_DEMO for demos
WASTE_MODEL_WEIGHTS=/models/best.pt # path to YOLOv8 weights
RATELIMIT_STORAGE_URL=redis://redis:6379/1  # use Redis for multi-worker rate limiting
```

Generate a secure key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Docker Production Start

```bash
cp .env.example .env
# Edit .env with real secrets
docker-compose up --build -d

# Run migrations
docker-compose exec web flask db upgrade

# Seed demo data (optional, dev/demo only)
docker-compose exec web flask seed-db
```

---

<div align="center">

**Built to make cities cleaner.**

*EcoClean Civic — Municipal Waste & Civic Issue Management Platform*

</div>
