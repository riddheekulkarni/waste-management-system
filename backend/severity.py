"""
Stage 2a — Rule-Based Severity Engine.

Severity is derived from YOLO's bounding-box metadata using an overlap-aware
union coverage calculation and item count.

Unlike a naive sum of bounding-box areas, which artificially inflates coverage
when multiple boxes cluster over the same waste pile, this engine calculates the
exact union area of all bounding boxes (eliminating duplicate overlap counting).

Thresholds:
- Low:    coverage < 10% and item_count <= 3
- Medium: coverage < 30% and item_count <= 7
- High:   coverage >= 30% or item_count > 7 (or hazardous materials present)
"""

from typing import Dict, List, Sequence, Tuple

from ai_config import normalize_waste_class
from detection import Detection

COVERAGE_THRESHOLDS = {
    "Low": 0.10,     # < 10% of frame covered by waste
    "Medium": 0.30,  # 10% - 30%
    # >= 30% -> High
}
COUNT_THRESHOLDS = {
    "Low": 3,
    "Medium": 7,
}


def box_area(box: Sequence[float]) -> float:
    """Calculate 2D area of a single bounding box."""
    x1, y1, x2, y2 = box
    return max(0.0, float(x2) - float(x1)) * max(0.0, float(y2) - float(y1))


def calculate_union_area(boxes: Sequence[Sequence[float]], frame_width: float, frame_height: float) -> float:
    """
    Compute the exact 2D union area of axis-aligned rectangles.

    Uses an exact 1D interval sweep-line over coordinate-compressed x-intervals.
    This guarantees overlapping bounding boxes are not double-counted.
    """
    valid_boxes: List[Tuple[float, float, float, float]] = []
    for b in boxes:
        x1 = max(0.0, min(float(b[0]), frame_width))
        y1 = max(0.0, min(float(b[1]), frame_height))
        x2 = max(0.0, min(float(b[2]), frame_width))
        y2 = max(0.0, min(float(b[3]), frame_height))
        if x2 > x1 and y2 > y1:
            valid_boxes.append((x1, y1, x2, y2))

    if not valid_boxes:
        return 0.0

    # Collect unique sorted x-coordinates
    xs = sorted(set([b[0] for b in valid_boxes] + [b[2] for b in valid_boxes]))
    total_union_area = 0.0

    # Sweep across adjacent x-slices
    for i in range(len(xs) - 1):
        x_left = xs[i]
        x_right = xs[i + 1]
        dx = x_right - x_left
        if dx <= 0.0:
            continue

        # Find all boxes that span [x_left, x_right]
        y_intervals: List[Tuple[float, float]] = []
        for b in valid_boxes:
            if b[0] <= x_left and b[2] >= x_right:
                y_intervals.append((b[1], b[3]))

        if not y_intervals:
            continue

        # Merge overlapping 1D y-intervals
        y_intervals.sort(key=lambda iv: iv[0])
        total_dy = 0.0
        cur_y1, cur_y2 = y_intervals[0]

        for next_y1, next_y2 in y_intervals[1:]:
            if next_y1 <= cur_y2:
                cur_y2 = max(cur_y2, next_y2)
            else:
                total_dy += cur_y2 - cur_y1
                cur_y1, cur_y2 = next_y1, next_y2
        total_dy += cur_y2 - cur_y1

        total_union_area += dx * total_dy

    return total_union_area


def compute_coverage_ratio(detections: List[Detection], image_size: Tuple[int, int]) -> float:
    """
    Calculate the overlap-aware coverage ratio of waste items in the image.

    Returns a float between 0.0 and 1.0 representing the exact fraction of the
    image covered by waste bounding boxes.
    """
    w, h = image_size
    total_area = float(w * h)
    if total_area <= 0:
        return 0.0

    boxes = [d.box for d in detections]
    union_area = calculate_union_area(boxes, float(w), float(h))
    return min(max(0.0, union_area / total_area), 1.0)


def compute_severity(detections: List[Detection], image_size: Tuple[int, int]) -> Dict:
    """
    Evaluate complaint severity based on overlap-aware coverage, item count,
    and detected waste classifications.

    Returns:
        dict:
            - level: 'Low' | 'Medium' | 'High'
            - severity: alias for level
            - coverage_ratio: exact union area / total area (0.0 to 1.0)
            - item_count: total detected items
            - detected_classes: list of canonical waste classes detected
    """
    coverage = compute_coverage_ratio(detections, image_size)
    count = len(detections)
    detected_classes = sorted(list(set(normalize_waste_class(d.cls) for d in detections)))

    # Hazardous materials or infrastructure damage escalate severity
    has_hazardous = "hazardous" in detected_classes
    has_infrastructure_hazard = any(c in detected_classes for c in ("pothole", "road_damage", "fallen_tree"))

    if has_hazardous or has_infrastructure_hazard:
        level = "High"
    elif coverage < COVERAGE_THRESHOLDS["Low"] and count <= COUNT_THRESHOLDS["Low"]:
        level = "Low"
    elif coverage < COVERAGE_THRESHOLDS["Medium"] and count <= COUNT_THRESHOLDS["Medium"]:
        level = "Medium"
    else:
        level = "High"

    return {
        "level": level,
        "severity": level,
        "coverage_ratio": coverage,
        "item_count": count,
        "detected_classes": detected_classes,
    }
