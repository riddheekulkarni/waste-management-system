# EcoClean Civic — Runtime Storage & Asset Structure

This document outlines the directory structure and separation of source assets from runtime-generated artifacts in EcoClean Civic.

---

## Storage Architecture

```
waste-management-system/
├── backend/
│   ├── instance/              # [RUNTIME] Local instance folder (git-ignored)
│   ├── migrations/            # [SOURCE] Version-controlled Alembic migrations
│   ├── routes/                # [SOURCE] Flask API blueprints
│   ├── tests/                 # [SOURCE] Automated test suite
│   ├── uploads/               # [RUNTIME] Uploaded complaint photos & AI bounding box images
│   │   └── .gitkeep           # [SOURCE] Preserves folder structure in git
│   ├── waste_management.db    # [RUNTIME] Local dev SQLite database (git-ignored)
│   ├── app.py                 # [SOURCE] Application factory & entrypoint
│   ├── config.py              # [SOURCE] Environment configuration & secrets
│   └── seed.py                # [SOURCE] Controlled development seeding script
├── frontend/                  # [SOURCE] Client UI HTML5/CSS3/JavaScript
├── best.pt                    # [ASSET] Trained YOLOv8s waste detection weights
├── pothole_model.pt           # [ASSET] Civic infrastructure pothole detection weights
├── .env.example               # [SOURCE] Environment configuration template
├── .gitignore                 # [SOURCE] Version control exclusion rules
├── docker-compose.yml         # [SOURCE] Container orchestration definition
└── MIGRATIONS.md              # [SOURCE] Migration & schema documentation
```

---

## Asset Classification

### 1. Source-Controlled Assets (Tracked in Git)
- **Application Code**: All Python modules, routes, models, configuration, and frontend files.
- **Migration Scripts**: Everything under `backend/migrations/` (Alembic environment and version files).
- **Core ML Model Weights**:
  - `best.pt`: Custom-trained YOLOv8s waste detector weights (~50MB).
  - `pothole_model.pt`: Infrastructure damage detector weights (~22MB).
- **Configuration Templates**: `.env.example`, `docker-compose.yml`, `Procfile`.
- **Directory Keepers**: `backend/uploads/.gitkeep`.

### 2. Runtime Artifacts (Excluded from Git)
- **SQLite Database Files**: `backend/waste_management.db`, `*.db`, `*.sqlite`, `*.sqlite3`.
- **Uploaded Complaint Images**: All citizen photo uploads and annotated AI evidence (`backend/uploads/*.jpg`, `*.jpeg`, `*.png`, `*.webp`).
- **Python Cache Files**: `__pycache__/`, `*.pyc`, `*.pyo`, `*.pyd`.
- **Test & Coverage Artifacts**: `.pytest_cache/`, `.coverage`, `htmlcov/`.
- **Local Secrets & Environment Variables**: `.env`, `.env.local`.
- **Application Logs**: `*.log`, `logs/`.

---

## Production Storage Strategy

- In containerized production deployments (`docker-compose.yml`), image uploads are persisted via a dedicated named volume (`complaint_uploads:/app/backend/uploads`).
- Relational database records are stored in PostgreSQL managed via the `postgres_data` Docker volume.
- In multi-instance or cloud-native Kubernetes deployments, `backend/uploads` should be backed by an S3-compatible object store (e.g., AWS S3, MinIO, or Google Cloud Storage) with presigned secure URLs.
