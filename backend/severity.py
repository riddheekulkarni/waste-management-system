"""
Stage 2a — Rule-Based Severity Engine.

Severity is derived directly from YOLO's own output metadata (bounding-box
coverage ratio + item count) rather than a separately trained model, since
no public dataset provides severity labels. This mirrors the formula given
in the literature survey:

    coverage_ratio = sum(area of each box) / total image area
"""

from typing import Dict, List, Tuple

from detection import Detection

COVERAGE_THRESHOLDS = {
    "Low": 0.10,     # < 10% of frame covered by waste
    "Medium": 0.30,  # 10% - 30%
    # >= 30% -> High
}
COUNT_THRESHOLDS = {"Low": 3, "Medium": 7}  # item-count escalation


def box_area(box) -> float:
    x1, y1, x2, y2 = box
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def compute_coverage_ratio(detections: List[Detection], image_size: Tuple[int, int]) -> float:
    w, h = image_size
    total_area = float(w * h)
    if total_area <= 0:
        return 0.0
    covered = sum(box_area(d.box) for d in detections)
    return min(covered / total_area, 1.0)


def compute_severity(detections: List[Detection], image_size: Tuple[int, int]) -> Dict:
    coverage = compute_coverage_ratio(detections, image_size)
    count = len(detections)

    if coverage < COVERAGE_THRESHOLDS["Low"] and count <= COUNT_THRESHOLDS["Low"]:
        level = "Low"
    elif coverage < COVERAGE_THRESHOLDS["Medium"] and count <= COUNT_THRESHOLDS["Medium"]:
        level = "Medium"
    else:
        level = "High"

    return {"level": level, "coverage_ratio": coverage, "item_count": count}
