"""
Stage 2b — Department Routing Engine.

Maps the dominant detected waste class to the municipal department
responsible for handling it.
"""

from typing import Dict, List

from detection import Detection

DEPARTMENT_MAP: Dict[str, str] = {
    # 12-class waste model mapping
    "plastic": "Recycling Department",
    "paper": "Recycling Department",
    "cardboard": "Recycling Department",
    "glass": "Recycling Department",
    "metal": "Recycling Department",
    "brown-glass": "Recycling Department",
    "green-glass": "Recycling Department",
    "white-glass": "Recycling Department",
    "organic": "Sanitation Department",
    "biological": "Sanitation Department",
    "mixed_litter": "Sanitation Department",
    "trash": "Sanitation Department",
    "clothes": "Sanitation Department",
    "shoes": "Sanitation Department",
    "hazardous": "Health & Hazmat Department",
    "battery": "Health & Hazmat Department",
    "construction_debris": "Public Works Department",
    "pothole": "Public Works Department",
    "road_damage": "Public Works Department",
    "fallen_tree": "Public Works Department",
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
