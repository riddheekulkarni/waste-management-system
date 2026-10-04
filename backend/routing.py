"""
Stage 2b — Department Routing Engine.

Maps the dominant detected waste class to the municipal department
responsible for handling it, using the canonical ontology from ai_config.
"""

from typing import Dict, List

from ai_config import (
    CANONICAL_DEPARTMENT_MAP,
    DEFAULT_DEPARTMENT,
    normalize_waste_class,
)
from detection import Detection

# Backward-compatibility alias
DEPARTMENT_MAP: Dict[str, str] = CANONICAL_DEPARTMENT_MAP


def determine_department(detections: List[Detection]) -> str:
    """
    Determine the responsible municipal department from detections.

    Normalizes detected classes using canonical ontology and finds the dominant
    class by frequency.
    """
    if not detections:
        return DEFAULT_DEPARTMENT

    counts: Dict[str, int] = {}
    for d in detections:
        canonical_cls = normalize_waste_class(d.cls)
        counts[canonical_cls] = counts.get(canonical_cls, 0) + 1

    dominant_class = max(counts, key=counts.get)
    return CANONICAL_DEPARTMENT_MAP.get(dominant_class, DEFAULT_DEPARTMENT)
