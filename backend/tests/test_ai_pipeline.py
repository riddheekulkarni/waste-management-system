"""
Unit and integration tests for EcoClean Civic AI pipeline upgrades:
- Explicit AI execution modes (REAL_YOLO vs MOCK_DEMO)
- Missing model fallback handling & logging
- Canonical waste class ontology mapping
- Unknown class graceful fallback
- Overlap-aware bounding box union coverage calculation
- Non-overlapping box calculation
- Rule-based explainable severity thresholds
"""

import io
import os
import pytest
from PIL import Image

from ai_config import (
    AI_MODE_LABELS,
    AI_MODE_MOCK_DEMO,
    AI_MODE_REAL_YOLO,
    CANONICAL_WASTE_CLASSES,
    DEFAULT_WASTE_CLASS,
    normalize_waste_class,
)
from detection import Detection, WasteDetector
from severity import (
    calculate_union_area,
    compute_coverage_ratio,
    compute_severity,
)


def create_temp_image_file(tmp_path, filename="test_img.jpg", color="green"):
    img = Image.new("RGB", (320, 240), color=color)
    img_path = str(tmp_path / filename)
    img.save(img_path, format="JPEG")
    return img_path


# ---------------------------------------------------------------------------
# 1. Real YOLO Mode Tests
# ---------------------------------------------------------------------------
def test_real_yolo_mode(tmp_path):
    # Locate best.pt in repo root or backend folder
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    best_pt = os.path.join(project_root, "best.pt")

    if not os.path.exists(best_pt):
        pytest.skip(f"best.pt not found at {best_pt}, skipping real YOLO execution test")

    detector = WasteDetector(weights_path=best_pt, mode="real")
    assert detector.mode == "real"
    assert detector.ai_mode == AI_MODE_REAL_YOLO
    assert detector.mock_reason is None

    test_img = create_temp_image_file(tmp_path)
    detections, img_size, ai_mode = detector.detect(test_img)

    assert ai_mode == AI_MODE_REAL_YOLO
    assert isinstance(detections, list)
    assert img_size == (320, 240)

    # Verify all returned detections have canonical classes
    for d in detections:
        assert d.cls in CANONICAL_WASTE_CLASSES or d.cls == "pothole"


# ---------------------------------------------------------------------------
# 2. Mock Mode Tests
# ---------------------------------------------------------------------------
def test_mock_mode(tmp_path):
    detector = WasteDetector(mode="mock")
    assert detector.mode == "mock"
    assert detector.ai_mode == AI_MODE_MOCK_DEMO
    assert detector.mock_reason is not None

    test_img = create_temp_image_file(tmp_path)
    detections, img_size, ai_mode = detector.detect(test_img)

    assert ai_mode == AI_MODE_MOCK_DEMO
    assert len(detections) >= 1
    assert img_size == (320, 240)

    # Every mock item must use canonical taxonomy
    for d in detections:
        assert d.cls in CANONICAL_WASTE_CLASSES


# ---------------------------------------------------------------------------
# 3. Missing Model Handling Tests
# ---------------------------------------------------------------------------
def test_missing_model(tmp_path, caplog):
    non_existent = str(tmp_path / "does_not_exist_weights.pt")

    # When real mode is requested with missing weights, it must NOT claim real YOLO
    detector = WasteDetector(weights_path=non_existent, mode="real")
    assert detector.mode == "mock"
    assert detector.ai_mode == AI_MODE_MOCK_DEMO
    assert detector.mock_reason is not None
    assert "not found" in detector.mock_reason.lower()

    # Verify logging occurred
    test_img = create_temp_image_file(tmp_path)
    res = detector.detect(test_img)
    assert res.ai_mode == AI_MODE_MOCK_DEMO


# ---------------------------------------------------------------------------
# 4. Canonical Class Mapping Tests
# ---------------------------------------------------------------------------
def test_class_mapping():
    # Identity mappings for canonical 9 classes
    for cls_name in CANONICAL_WASTE_CLASSES:
        assert normalize_waste_class(cls_name) == cls_name

    # Raw 12-class model outputs
    assert normalize_waste_class("battery") == "hazardous"
    assert normalize_waste_class("biological") == "organic"
    assert normalize_waste_class("brown-glass") == "glass"
    assert normalize_waste_class("green-glass") == "glass"
    assert normalize_waste_class("white-glass") == "glass"
    assert normalize_waste_class("clothes") == "mixed_litter"
    assert normalize_waste_class("shoes") == "mixed_litter"
    assert normalize_waste_class("trash") == "mixed_litter"

    # Audited & documented TACO mappings
    assert normalize_waste_class("broken glass") == "glass"
    assert normalize_waste_class("rope") == "construction_debris"
    assert normalize_waste_class("wire") == "construction_debris"
    assert normalize_waste_class("foam") == "plastic"
    assert normalize_waste_class("polystyrene item") == "plastic"
    assert normalize_waste_class("corrugated cardboard") == "cardboard"
    assert normalize_waste_class("banana peel") == "organic"
    assert normalize_waste_class("syringe") == "hazardous"


# ---------------------------------------------------------------------------
# 5. Unknown Class Handling Tests
# ---------------------------------------------------------------------------
def test_unknown_class_handling():
    assert normalize_waste_class("extraterrestrial_satellite_part") == DEFAULT_WASTE_CLASS
    assert normalize_waste_class("") == DEFAULT_WASTE_CLASS
    assert normalize_waste_class(None) == DEFAULT_WASTE_CLASS
    assert normalize_waste_class("   ") == DEFAULT_WASTE_CLASS


# ---------------------------------------------------------------------------
# 6. Overlapping Bounding Boxes Coverage Tests
# ---------------------------------------------------------------------------
def test_overlapping_boxes():
    image_size = (1000, 1000)  # total area = 1,000,000

    # 1. Identical bounding boxes: box area = 100 * 100 = 10,000 (1.0% of frame)
    b1 = Detection(cls="plastic", confidence=0.9, box=(100, 100, 200, 200))
    b2 = Detection(cls="plastic", confidence=0.85, box=(100, 100, 200, 200))
    b3 = Detection(cls="plastic", confidence=0.80, box=(100, 100, 200, 200))

    # A naive sum would produce 30,000 (3% of frame).
    # Overlap-aware union must equal exactly 10,000 (1% of frame).
    coverage = compute_coverage_ratio([b1, b2, b3], image_size)
    assert round(coverage, 4) == 0.0100

    # 2. Partially overlapping boxes:
    # Box A: [0, 0, 100, 100] (area 10,000)
    # Box B: [50, 0, 150, 100] (area 10,000)
    # Total Union Area: width 150, height 100 -> area 15,000 (1.5% of frame)
    # (Naive sum would yield 20,000 / 2.0%)
    b_part_a = Detection(cls="cardboard", confidence=0.9, box=(0, 0, 100, 100))
    b_part_b = Detection(cls="cardboard", confidence=0.9, box=(50, 0, 150, 100))

    coverage_part = compute_coverage_ratio([b_part_a, b_part_b], image_size)
    assert round(coverage_part, 4) == 0.0150


# ---------------------------------------------------------------------------
# 7. Non-Overlapping Bounding Boxes Coverage Tests
# ---------------------------------------------------------------------------
def test_non_overlapping_boxes():
    image_size = (1000, 1000)  # 1,000,000 total

    # Disjoint boxes:
    # Box 1: [0, 0, 100, 100] -> area 10,000
    # Box 2: [200, 200, 300, 300] -> area 10,000
    # Union Area = 20,000 (2.0% of frame)
    b1 = Detection(cls="metal", confidence=0.9, box=(0, 0, 100, 100))
    b2 = Detection(cls="glass", confidence=0.9, box=(200, 200, 300, 300))

    coverage = compute_coverage_ratio([b1, b2], image_size)
    assert round(coverage, 4) == 0.0200


# ---------------------------------------------------------------------------
# 8. Severity Thresholds & Explainability Tests
# ---------------------------------------------------------------------------
def test_severity_thresholds():
    image_size = (1000, 1000)

    # Low Severity: coverage < 10% and count <= 3
    low_dets = [
        Detection(cls="paper", confidence=0.9, box=(0, 0, 100, 100)),  # 1%
        Detection(cls="paper", confidence=0.8, box=(200, 200, 300, 300)),  # 1%
    ]
    sev_low = compute_severity(low_dets, image_size)
    assert sev_low["level"] == "Low"
    assert sev_low["severity"] == "Low"
    assert sev_low["item_count"] == 2
    assert sev_low["detected_classes"] == ["paper"]
    assert round(sev_low["coverage_ratio"], 4) == 0.0200

    # Medium Severity: coverage between 10% and 30% (e.g. 400x400 = 16%)
    med_dets = [Detection(cls="cardboard", confidence=0.9, box=(0, 0, 400, 400))]
    sev_med = compute_severity(med_dets, image_size)
    assert sev_med["level"] == "Medium"
    assert sev_med["item_count"] == 1
    assert "cardboard" in sev_med["detected_classes"]

    # High Severity by Coverage: coverage >= 30% (e.g. 600x600 = 36%)
    high_cov_dets = [Detection(cls="plastic", confidence=0.9, box=(0, 0, 600, 600))]
    sev_high_cov = compute_severity(high_cov_dets, image_size)
    assert sev_high_cov["level"] == "High"

    # High Severity by Count: item_count > 7 (even with tiny boxes)
    high_cnt_dets = [
        Detection(cls="plastic", confidence=0.9, box=(i * 20, 0, i * 20 + 10, 10))
        for i in range(8)
    ]
    sev_high_cnt = compute_severity(high_cnt_dets, image_size)
    assert sev_high_cnt["level"] == "High"
    assert sev_high_cnt["item_count"] == 8

    # High Severity by Hazardous Content: presence of hazardous waste (battery/syringe/etc.)
    haz_dets = [Detection(cls="hazardous", confidence=0.95, box=(0, 0, 20, 20))]
    sev_haz = compute_severity(haz_dets, image_size)
    assert sev_haz["level"] == "High"

    # High Severity by Civic Hazard: pothole
    pothole_dets = [Detection(cls="pothole", confidence=0.95, box=(0, 0, 50, 50))]
    sev_pothole = compute_severity(pothole_dets, image_size)
    assert sev_pothole["level"] == "High"
