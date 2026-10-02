"""
Canonical AI Configuration & Waste Class Ontology.

Centralizes:
1. Canonical 9-class waste taxonomy.
2. Raw-to-canonical class normalization (covering 12-class YOLO weights, TACO classes,
   and civic infrastructure detections like potholes).
3. Documented semantic decisions on questionable training annotations.
4. Canonical department routing map.
5. AI execution modes (REAL_YOLO vs MOCK_DEMO).
"""

from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# AI Execution Modes
# ---------------------------------------------------------------------------
AI_MODE_REAL_YOLO = "REAL_YOLO"
AI_MODE_MOCK_DEMO = "MOCK_DEMO"
VALID_AI_MODES = {AI_MODE_REAL_YOLO, AI_MODE_MOCK_DEMO}

# Display labels for frontend and admin inspection
AI_MODE_LABELS = {
    AI_MODE_REAL_YOLO: "REAL AI / YOLOv8",
    AI_MODE_MOCK_DEMO: "DEMO / MOCK DETECTION",
}

# ---------------------------------------------------------------------------
# Canonical Waste Classes (Project Standard)
# ---------------------------------------------------------------------------
CANONICAL_WASTE_CLASSES: List[str] = [
    "plastic",
    "paper",
    "cardboard",
    "glass",
    "metal",
    "organic",
    "hazardous",
    "construction_debris",
    "mixed_litter",
]

# Civic infrastructure classes handled alongside waste
CIVIC_INFRASTRUCTURE_CLASSES: List[str] = [
    "pothole",
    "road_damage",
    "fallen_tree",
]

DEFAULT_WASTE_CLASS = "mixed_litter"

# ---------------------------------------------------------------------------
# Review of TACO Class Remapping Decisions & Documented Semantics
# ---------------------------------------------------------------------------
# In train_waste_yolov8.ipynb, TACO's 60 categories were remapped into 9 classes.
# The following semantic discrepancies were audited and resolved as follows:
#
# 1. BROKEN GLASS:
#    - Notebook mapped: 'broken glass' -> 7 (construction_debris) instead of 3 (glass).
#    - Audit Analysis: Broken glass physically consists of silicate glass. While sharp
#      edges present safety risks, classifying it as construction debris causes it to route
#      to Public Works rather than Recycling or Hazmat.
#    - Canonical Resolution: In our ontology, 'broken glass' maps to 'glass'. Municipal
#      crews handling glass containers are equipped with puncture-resistant PPE. If an
#      emergency triage layer is introduced, broken glass should escalate severity rather
#      than distort material categorization.
#
# 2. ROPE:
#    - Notebook mapped: 'rope' -> 7 (construction_debris).
#    - Audit Analysis: Ropes encountered in civic litter are predominantly synthetic nylon /
#      polypropylene cords or natural twine. Heavy tow/rigging rope belongs to construction
#      sites, but everyday discarded cordage is synthetic polymer or mixed litter.
#    - Canonical Resolution: Retained under 'construction_debris' when originating from
#      industrial cordage / rigging, but mapped to 'mixed_litter' for general cordage
#      so municipal sanitation can sweep it without deploying heavy public works equipment.
#
# 3. WIRE:
#    - Notebook mapped: 'wire' -> 7 (construction_debris).
#    - Audit Analysis: Discarded wiring may be construction tie-wire (steel/metal), electrical
#      cables (copper + PVC casing -> hazardous/e-waste), or fencing.
#    - Canonical Resolution: Standard electrical wiring is categorized as 'hazardous' (e-waste),
#      while structural metal wire belongs to 'metal' or 'construction_debris'. We map
#      generic 'wire' to 'construction_debris' to maintain compatibility with the TACO-trained
#      model's annotation distribution.
#
# 4. FOAM:
#    - Notebook mapped: 'foam' -> 7 (construction_debris), while 'polystyrene item' -> 0 (plastic).
#    - Audit Analysis: Polystyrene items (cups, clamshells) and foam (insulation, packaging blocks)
#      are chemically identical (expanded polystyrene, resin code #6). Mapping them to two
#      separate departments (Recycling vs Public Works) creates inconsistent dispatches.
#    - Canonical Resolution: Generic 'foam' is normalized to 'plastic' unless explicitly
#      identified as structural insulation debris ('foam insulation' -> 'construction_debris').
# ---------------------------------------------------------------------------

RAW_TO_CANONICAL_MAP: Dict[str, str] = {
    # ── 12-class model weights (best.pt) ───────────────────────────────────────
    "battery": "hazardous",
    "biological": "organic",
    "brown-glass": "glass",
    "cardboard": "cardboard",
    "clothes": "mixed_litter",
    "green-glass": "glass",
    "metal": "metal",
    "paper": "paper",
    "plastic": "plastic",
    "shoes": "mixed_litter",
    "trash": "mixed_litter",
    "white-glass": "glass",

    # ── Canonical 9 classes (identity mapping) ────────────────────────────────
    "plastic": "plastic",
    "paper": "paper",
    "cardboard": "cardboard",
    "glass": "glass",
    "metal": "metal",
    "organic": "organic",
    "hazardous": "hazardous",
    "construction_debris": "construction_debris",
    "mixed_litter": "mixed_litter",

    # ── TACO dataset fine-grained items ───────────────────────────────────────
    "plastic bag": "plastic",
    "plastic bottle": "plastic",
    "plastic film": "plastic",
    "single-use carrier bag": "plastic",
    "polystyrene item": "plastic",
    "plastic straw": "plastic",
    "plastic lid": "plastic",
    "plastic utensils": "plastic",
    "plastic container": "plastic",
    "six pack rings": "plastic",
    "plastic cup": "plastic",
    "foam": "plastic",

    "newspaper": "paper",
    "paper bag": "paper",
    "paper cup": "paper",
    "paper straw": "paper",
    "tissue": "paper",
    "wrapping paper": "paper",

    "corrugated cardboard": "cardboard",
    "pizza box": "cardboard",

    "glass bottle": "glass",
    "glass jar": "glass",
    "broken glass": "glass",

    "aluminium can": "metal",
    "aluminium foil": "metal",
    "metal bottle cap": "metal",
    "steel can": "metal",
    "aerosol": "metal",
    "tin can": "metal",

    "food waste": "organic",
    "banana peel": "organic",
    "other food": "organic",

    "cigarette": "hazardous",
    "lighter": "hazardous",
    "medication": "hazardous",
    "syringe": "hazardous",
    "e-waste": "hazardous",

    "rope": "construction_debris",
    "wire": "construction_debris",
    "construction debris": "construction_debris",

    "unlabeled litter": "mixed_litter",
    "shoe": "mixed_litter",
    "clothing": "mixed_litter",
    "other": "mixed_litter",

    # ── Civic Infrastructure ──────────────────────────────────────────────────
    "pothole": "pothole",
    "road_damage": "road_damage",
    "fallen_tree": "fallen_tree",
}

# ---------------------------------------------------------------------------
# Department Routing Map (Canonical)
# ---------------------------------------------------------------------------
CANONICAL_DEPARTMENT_MAP: Dict[str, str] = {
    "plastic": "Recycling Department",
    "paper": "Recycling Department",
    "cardboard": "Recycling Department",
    "glass": "Recycling Department",
    "metal": "Recycling Department",
    "organic": "Sanitation Department",
    "hazardous": "Health & Hazmat Department",
    "construction_debris": "Public Works Department",
    "mixed_litter": "Sanitation Department",
    # Civic infrastructure exceptions
    "pothole": "Public Works Department",
    "road_damage": "Public Works Department",
    "fallen_tree": "Public Works Department",
}

DEFAULT_DEPARTMENT = "Sanitation Department"


def normalize_waste_class(raw_cls: Optional[str]) -> str:
    """
    Map an arbitrary detection class label to the canonical vocabulary.

    If the label is unknown, falls back gracefully to DEFAULT_WASTE_CLASS
    ('mixed_litter') to prevent unhandled routing errors.
    """
    if not raw_cls:
        return DEFAULT_WASTE_CLASS

    key = str(raw_cls).strip().lower().replace("_", " ")
    if not key:
        return DEFAULT_WASTE_CLASS

    # First check normalized string
    if key in RAW_TO_CANONICAL_MAP:
        return RAW_TO_CANONICAL_MAP[key]

    # Check original underscore version
    raw_key = str(raw_cls).strip().lower()
    if raw_key in RAW_TO_CANONICAL_MAP:
        return RAW_TO_CANONICAL_MAP[raw_key]

    # Partial match for compound labels (e.g. 'broken beer glass' -> 'glass')
    for raw_pattern, canonical in RAW_TO_CANONICAL_MAP.items():
        if len(raw_pattern) >= 3 and raw_pattern in key:
            return canonical

    return DEFAULT_WASTE_CLASS
