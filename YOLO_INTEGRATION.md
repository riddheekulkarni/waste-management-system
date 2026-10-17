# EcoClean Civic — YOLO Model Integration (Deep Dive)

This document explains exactly how the YOLOv8 model is integrated into EcoClean Civic — from model loading, inference, class normalization, severity calculation, and department routing, to the full async pipeline.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Models Used](#2-models-used)
3. [File Map](#3-file-map)
4. [Stage 0 — Configuration & Class Ontology](#4-stage-0--configuration--class-ontology)
5. [Stage 1 — Object Detection](#5-stage-1--object-detection)
6. [Stage 2a — Severity Engine](#6-stage-2a--severity-engine)
7. [Stage 2b — Department Routing](#7-stage-2b--department-routing)
8. [Stage 3 — Async Pipeline](#8-stage-3--async-pipeline)
9. [End-to-End Flow Diagram](#9-end-to-end-flow-diagram)
10. [Key Design Decisions](#10-key-design-decisions)

---

## 1. Overview

When a citizen submits a waste complaint with a photo, EcoClean Civic runs it through a multi-stage AI pipeline:

```
Photo Upload → YOLO Detection → Severity Score → Duplicate Check → Department Routing → VERIFIED
```

Everything after the upload runs **asynchronously in the background** so the citizen gets an immediate response (HTTP 201) and the AI processes without blocking.

---

## 2. Models Used

| Model File | Purpose | Confidence Threshold |
|------------|---------|---------------------|
| `best.pt` (root) | Custom-trained YOLOv8 — detects **12 waste classes** | `0.15` (sensitive) |
| `pothole_model.pt` (root) | Civic infrastructure — detects **potholes / road damage** | `0.30` |

> **Why 0.15 for waste?** A low threshold captures distant debris, partially obscured piles, and roadside scattered litter that a higher threshold would miss. The trade-off (more false positives) is acceptable since a human admin reviews flagged complaints.

> **Why 0.30 for potholes?** Road surface defects have higher visual contrast and more distinguishable features, so a stricter threshold avoids false pothole flags on road markings or shadows.

---

## 3. File Map

```
backend/
├── ai_config.py      ← Class ontology, normalization map, department map, AI modes
├── detection.py      ← WasteDetector: loads YOLO, runs inference, draws bounding boxes
├── severity.py       ← Overlap-aware severity calculation (Low / Medium / High)
├── routing.py        ← Maps dominant waste class → municipal department
├── tasks.py          ← Full async AI pipeline (orchestrates all stages above)
└── worker.py         ← RQ worker that picks up jobs from the Redis queue

root/
├── best.pt           ← Custom YOLOv8 waste detection weights
└── pothole_model.pt  ← Pothole / road damage detection weights
```

---

## 4. Stage 0 — Configuration & Class Ontology

**File:** `backend/ai_config.py`

### AI Execution Modes

Two modes exist at runtime:

| Mode | Constant | Description |
|------|----------|-------------|
| Real | `AI_MODE_REAL_YOLO = "REAL_YOLO"` | Actual YOLOv8 inference on uploaded image |
| Demo | `AI_MODE_MOCK_DEMO = "MOCK_DEMO"` | Synthetic random detections (fallback) |

Mode is displayed to admins on the complaint detail page so they always know whether detections are real or synthetic.

### Canonical 9-Class Waste Taxonomy

The project standardises all detections into exactly **9 canonical waste classes** regardless of what the model outputs:

```python
CANONICAL_WASTE_CLASSES = [
    "plastic",             # Bottles, bags, films, foam
    "paper",               # Newspaper, cups, bags
    "cardboard",           # Corrugated boxes, pizza boxes
    "glass",               # Bottles, jars, broken glass
    "metal",               # Cans, foil, aerosols
    "organic",             # Food waste, banana peels
    "hazardous",           # Batteries, syringes, e-waste, cigarettes
    "construction_debris", # Rope, wire, debris
    "mixed_litter",        # Shoes, clothes, unlabeled items
]
```

Plus 3 **civic infrastructure classes** handled alongside waste:
```python
CIVIC_INFRASTRUCTURE_CLASSES = ["pothole", "road_damage", "fallen_tree"]
```

### Class Normalization — `normalize_waste_class()`

The `best.pt` model was trained on 12 raw YOLO classes. `normalize_waste_class()` maps any raw label → canonical class:

```python
# Examples from RAW_TO_CANONICAL_MAP:
"battery"       → "hazardous"
"brown-glass"   → "glass"
"shoes"         → "mixed_litter"
"plastic bag"   → "plastic"
"foam"          → "plastic"       # polystyrene = plastic (see design note)
"broken glass"  → "glass"         # NOT construction_debris (see design note)
"cigarette"     → "hazardous"
"syringe"       → "hazardous"
```

The function also handles **partial matching** for compound labels:
```python
# "broken beer glass" → matches "glass" via substring scan
for raw_pattern, canonical in RAW_TO_CANONICAL_MAP.items():
    if len(raw_pattern) >= 3 and raw_pattern in key:
        return canonical
```

Unknown classes fall back to `"mixed_litter"` — never crashes on an unseen label.

### Documented Semantic Decisions

The TACO training dataset had some ambiguous category mappings that were explicitly resolved:

| Raw Class | Notebook Mapped To | Our Canonical | Reason |
|-----------|-------------------|---------------|--------|
| `broken glass` | `construction_debris` | `glass` | Broken glass is silicate glass; routing to Recycling (with PPE) is more correct than Public Works |
| `foam` | `construction_debris` | `plastic` | EPS foam and polystyrene items are chemically identical (#6 resin); inconsistent routing was eliminated |
| `rope` | `construction_debris` | `construction_debris` | Retained for industrial cordage; general cordage → `mixed_litter` |
| `wire` | `construction_debris` | `construction_debris` | Generic mapping retained; electrical wire → `hazardous` if identified specifically |

---

## 5. Stage 1 — Object Detection

**File:** `backend/detection.py`

### Model Loading & Modes

The `WasteDetector` class is the core YOLO wrapper:

```
mode = "mock"  →  Always use synthetic detections
mode = "real"  →  Try to load real model; error if unavailable
mode = "auto"  →  Try real; silently fall back to mock if unavailable
```

In `tasks.py`, mode is derived from the app config:
```python
mode = "mock" if mode_cfg == "MOCK_DEMO" else "auto"
```

**Pre-flight checks before loading (`_can_load_model`):**
1. Is `ultralytics` package installed?
2. Is `weights_path` provided?
3. Does the `.pt` file actually exist on disk?

If any check fails → fall back to `MOCK_DEMO` (no silent real-inference claims).

**Pothole model auto-discovery:**
After the waste model loads, the detector scans 3 candidate paths for `pothole_model.pt`:
```python
possible_pothole_paths = [
    "<root>/pothole_model.pt",
    "<backend>/pothole_model.pt",
    "<root>/models/pothole_model.pt",
]
```

### Real YOLO Inference

```python
def _detect_real(self, image_path):
    results = self.model(image_path, conf=0.15)[0]

    for box in results.boxes:
        cls_id      = int(box.cls[0])
        raw_cls     = self.model.names.get(cls_id, "unknown")
        canonical   = normalize_waste_class(raw_cls)   # → 9-class ontology
        confidence  = float(box.conf[0])
        xyxy        = tuple(float(v) for v in box.xyxy[0])  # pixel coords

        detections.append(Detection(
            cls=canonical,
            confidence=confidence,
            box=xyxy,           # (x1, y1, x2, y2)
            raw_cls=raw_cls,    # preserved for audit trail
        ))
```

**Then the pothole model runs separately:**
```python
if self.pothole_model:
    p_results = self.pothole_model(image_path, conf=0.30)[0]
    if len(p_results.boxes) > 0:
        # Filter false positives: shoes/clothes misdetected on road surfaces
        detections = [d for d in detections if d.raw_cls not in ("shoes", "clothes")]
        detections.append(Detection(cls="pothole", ...))
```

> **Why filter shoes/clothes when potholes found?** The waste model sometimes misidentifies road surface texture near potholes as "shoes" or "clothes". When the pothole model confirms road damage, those waste detections are treated as noise and dropped.

### Mock / Demo Mode

When real inference is unavailable, `_detect_mock()` generates synthetic detections **sized proportionally against the actual image dimensions**:

```python
w, h = image_size
num_items = random.randint(1, 6)

for _ in range(num_items):
    box_w = random.uniform(0.05, 0.35) * w   # 5-35% of image width
    box_h = random.uniform(0.05, 0.35) * h
    x1 = random.uniform(0, max(w - box_w, 1))
    y1 = random.uniform(0, max(h - box_h, 1))
    confidence = round(random.uniform(0.60, 0.95), 2)
```

Mock boxes are proportional to the real image so the annotated image overlay still looks realistic.

### Annotated Image Generation

After detection (both real and mock), an annotated image is saved to the uploads folder:

| Mode | Box Color | Label Format |
|------|-----------|-------------|
| Real — waste | `#10b981` (green) | `plastic 87%` |
| Real — hazardous / pothole | `#ef4444` (red) | `hazardous 92%` |
| Mock / Demo | `#f59e0b` (amber) | `[DEMO] plastic 87%` |

File saved as: `annotated_<original_filename>.<ext>`

---

## 6. Stage 2a — Severity Engine

**File:** `backend/severity.py`

### The Problem With Naive Area Sum

If 5 bounding boxes all overlap a single waste pile, naive summing gives 5× the real area — artificially inflating severity. The engine instead computes the **exact union area** using a coordinate-compressed sweep-line algorithm.

### Sweep-Line Union Area Algorithm

```
1. Collect all unique X coordinates from all bounding boxes.
2. For each adjacent X-slice [x_left, x_right]:
   a. Find all boxes that span that slice.
   b. Extract their Y-intervals.
   c. Merge overlapping Y-intervals into a 1D union.
   d. Add  dx × merged_y_length  to the running union total.

Result: exact pixel count covered by at least one bounding box.
```

### Severity Thresholds

```
coverage_ratio = union_area / (image_width × image_height)

Low:    coverage < 10%  AND  item_count ≤ 3
Medium: coverage < 30%  AND  item_count ≤ 7
High:   coverage ≥ 30%  OR   item_count > 7
        OR hazardous class detected
        OR pothole / road_damage / fallen_tree detected
```

> **Hazardous materials and civic infrastructure damage always escalate to High** regardless of coverage or count — a single syringe or pothole is a public safety issue.

---

## 7. Stage 2b — Department Routing

**File:** `backend/routing.py`

```python
def determine_department(detections):
    counts = {}
    for d in detections:
        canonical_cls = normalize_waste_class(d.cls)
        counts[canonical_cls] = counts.get(canonical_cls, 0) + 1

    dominant_class = max(counts, key=counts.get)   # most frequent class wins
    return CANONICAL_DEPARTMENT_MAP.get(dominant_class, DEFAULT_DEPARTMENT)
```

**Routing table:**

| Waste Class | Department |
|-------------|-----------|
| plastic, paper, cardboard, glass, metal | Recycling Department |
| organic, mixed_litter | Sanitation Department |
| hazardous | Health & Hazmat Department |
| construction_debris | Public Works Department |
| pothole, road_damage, fallen_tree | Public Works Department |

Default fallback (no detections): **Sanitation Department**

---

## 8. Stage 3 — Async Pipeline

**File:** `backend/tasks.py`

The function `process_complaint_job(complaint_id)` runs as a background RQ job:

### 9-Step Pipeline

```
Step 1: Idempotency Check
        → If complaint already in-progress for <300s, skip job
          (prevents double-processing on worker restart)

Step 2: Image Validation
        → File exists on disk?
        → PIL can decode it? (not corrupted)

Step 3: YOLO Detection
        → detector.detect(image_path) → (detections, image_size, ai_mode)
        → Sets complaint.ai_mode  ("REAL_YOLO" or "MOCK_DEMO")
        → Sets complaint.model_name, model_version

Step 4: Store DetectionItems
        → Deletes existing items first (safe retry)
        → Writes each Detection → DetectionItem row in SQLite/Postgres

Step 5: Severity Calculation
        → compute_severity(detections, image_size)
        → Sets complaint.severity_level, coverage_ratio, item_count

Step 6: Duplicate Detection
        → Haversine distance check vs. all open complaints within 50m
        → If duplicate found: complaint.status = "DUPLICATE"
                              complaint.duplicate_of_id = <original>

Step 7: Department Routing
        → determine_department(detections)
        → Sets complaint.department

Step 8: Finalize
        → complaint.status = "VERIFIED" (or keeps "DUPLICATE")
        → Records processing_duration_ms and processing_completed_at

Step 9: Error Handling (wraps all above)
        → On any exception: db.session.rollback()
        → complaint.status = "PROCESSING_FAILED"
        → Safe error message stored (no internal stack traces exposed to client)
        → Publishes processing_failed SSE event
```

### SSE Events Published at Each Stage

At every stage transition, an event is published to Redis Pub/Sub, which streams to the citizen's browser via SSE:

| Stage | SSE Event Type | Key Payload Fields |
|-------|---------------|-------------------|
| Job starts | `processing_started` | status, stage, ai_mode |
| Analyzing image | `stage_changed` | progress_message |
| Calculating severity | `stage_changed` | progress_message |
| Checking duplicates | `stage_changed` | progress_message |
| Assigning department | `stage_changed` | progress_message |
| Done | `processing_completed` | severity, department, item_count, coverage_ratio, is_duplicate, duration_ms |
| Failed | `processing_failed` | error, retry_available, duration_ms |

---

## 9. End-to-End Flow Diagram

```
Citizen uploads photo
        │
        ▼
POST /api/complaints/upload
        │
        ├─ Save image to /uploads/
        ├─ Create Complaint record (status: AI_PROCESSING)
        ├─ Enqueue job → Redis Queue
        └─ Return HTTP 201 immediately
                │
                ▼
        [RQ Worker picks up job]
                │
        ┌───────▼────────────────┐
        │  1. Idempotency Check  │
        └───────┬────────────────┘
                │
        ┌───────▼────────────────┐
        │  2. Validate image     │ ← PIL verify
        └───────┬────────────────┘
                │
        ┌───────▼────────────────┐
        │  3. YOLO Detection     │ ← best.pt       conf=0.15
        │                        │ ← pothole_model conf=0.30
        └───────┬────────────────┘
                │
        ┌───────▼────────────────┐
        │  4. Normalize classes  │ ← normalize_waste_class()
        │     Save DetectionItems│ ← DB rows
        └───────┬────────────────┘
                │
        ┌───────▼────────────────┐
        │  5. Severity Score     │ ← sweep-line union area
        │     Low / Medium / High│
        └───────┬────────────────┘
                │
        ┌───────▼────────────────┐
        │  6. Duplicate Check    │ ← Haversine ≤ 50m radius
        └───────┬────────────────┘
                │
        ┌───────▼────────────────┐
        │  7. Department Routing │ ← dominant class → dept.
        └───────┬────────────────┘
                │
        ┌───────▼────────────────┐
        │  8. status = VERIFIED  │
        │     Publish SSE event  │ → Browser live update
        └───────┬────────────────┘
                │
        ┌───────▼────────────────────────────┐
        │  9. Operational Notification Rules  │
        │     High severity alert             │
        │     Duplicate notification          │
        │     User status-change notification │
        └────────────────────────────────────┘
```

---

## 10. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Dual-mode (REAL_YOLO / MOCK_DEMO)** | System runs as a live demo without real weights; admins always see which mode produced the detections |
| **Low waste conf threshold (0.15)** | Maximises recall for messy outdoor scenes; false positives caught by admin review |
| **Separate pothole model** | Road damage has a different visual signature from loose waste; a dedicated model gives better accuracy |
| **9-class canonical ontology** | Raw YOLO model has 12 inconsistent classes; normalization keeps routing logic clean regardless of model retraining |
| **Sweep-line union area** | Prevents severity inflation when waste items cluster and overlap in the same pile |
| **50m duplicate radius** | Prevents the same dump being reported dozens of times by neighbours; links duplicates to the original work order |
| **Annotated image saved at detection time** | Frontend can serve the bounding-box overlay immediately without post-processing latency |
| **Idempotent job design** | Worker crash + retry is safe — old DetectionItem rows are deleted before re-inserting |
| **300s idempotency window** | Prevents two workers processing the same job concurrently after a crash recovery |
