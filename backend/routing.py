"""
Stage 2b — Department Routing Engine.

Maps the dominant detected waste class to the municipal department
responsible for handling it.
"""

from typing import Dict, List

from detection import Detection

DEPARTMENT_MAP: Dict[str, str] = {
    "plastic": "Recycling Department",
    "paper": "Recycling Department",
    "cardboard": "Recycling Department",
    "glass": "Recycling Department",
    "metal": "Recycling Department",
    "organic": "Sanitation Department",
    "mixed_litter": "Sanitation Department",
    "hazardous": "Health & Hazmat Department",
    "construction_debris": "Public Works Department",
}

DEFAULT_DEPARTMENT = "Sanitation Department"


def determine_department(detections: List[Detection]) -> str:
    if not detections:
        return DEFAULT_DEPARTMENT

    counts: Dict[str, int] = {}
    for d in detections:
        counts[d.cls] = counts.get(d.cls, 0) + 1

    dominant_class = max(counts, key=counts.get)
    return DEPARTMENT_MAP.get(dominant_class, DEFAULT_DEPARTMENT)
