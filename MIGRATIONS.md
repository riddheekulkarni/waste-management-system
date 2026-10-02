# EcoClean Civic — Database Migration & Schema Guide

This document details the database schema migration workflow using **Flask-Migrate** (built on top of **Alembic** and **SQLAlchemy**).

---

## Architecture Overview

All database schema evolutions are version-controlled inside [`backend/migrations`](file:///c:/projects/waste-management-system/backend/migrations). Dynamic runtime schema alterations (`PRAGMA table_info` checks) have been deprecated and removed.

The schema comprises:
- `users`: Citizen and municipal administrator accounts with hashed credentials and roles.
- `complaints`: Geotagged waste reports with department dispatch routing, AI severity ratings, duplicate detection linkage, and explicit `ai_mode` (`REAL_YOLO` vs `MOCK_DEMO`).
- `detection_items`: Computer vision bounding boxes, classified waste labels, and detection confidence scores.

### Justified Database Indexes
- `ix_complaints_user_id`: Citizen ownership queries (`WHERE user_id = :id`).
- `ix_complaints_status`: Municipal operational workflow queries (`WHERE status = :status`).
- `ix_complaints_department`: Department workload filtering (`WHERE department = :dept`).
- `ix_complaints_created_at`: Chronological timeline sorting (`ORDER BY created_at DESC`).
- `ix_complaints_is_duplicate`: Duplicate triage filtering.
- `idx_complaints_lat_lng`: Compound spatial index on `(latitude, longitude)` for high-performance Haversine duplicate radius queries.
- `ix_detection_items_complaint_id`: Foreign key join and cascading deletions.
- `ix_detection_items_cls`: Waste composition analytics and aggregate reporting.

---

## Developer Workflow

All migration commands are executed from the `backend/` directory or with `--app app`:

### 1. Fresh Developer Database Setup
For a developer setting up a brand-new local development environment:

```bash
cd backend

# 1. Apply all versioned migrations up to the latest revision
python -m flask --app app db upgrade

# 2. (Optional) Seed development demo accounts
python seed.py
# Or using the Flask CLI:
python -m flask --app app seed-db
```

### 2. Generating a New Migration
When modifying model structures in [`backend/models.py`](file:///c:/projects/waste-management-system/backend/models.py):

```bash
cd backend

# Generate a migration script comparing current models against database
python -m flask --app app db migrate -m "describe_your_schema_change"
```

Inspect the generated Python file under `backend/migrations/versions/<revision_id>_....py` to verify the generated operations.

### 3. Applying Migrations
Apply pending migrations:

```bash
cd backend
python -m flask --app app db upgrade
```

### 4. Downgrading Migrations
Roll back the database schema to the previous revision:

```bash
cd backend
python -m flask --app app db downgrade
```

To rollback to a specific revision:
```bash
python -m flask --app app db downgrade <revision_id>
```

### 5. Checking Current Migration Version
```bash
cd backend
python -m flask --app app db current
```

---

## Production Deployment Guidelines

1. Never run destructive table drops or automatic seeding in production.
2. In production container entrypoints, run:
   ```bash
   flask db upgrade
   ```
   prior to starting the Gunicorn server workers.
3. Ensure `DATABASE_URL` is set to the production PostgreSQL instance.
