from detection import WasteDetector, Detection
from severity import compute_severity, compute_coverage_ratio
from routing import determine_department
from models import Complaint


def test_haversine_distance():
    # Distance between same coordinates should be 0
    d0 = Complaint.haversine_distance(18.5204, 73.8567, 18.5204, 73.8567)
    assert round(d0, 2) == 0.0

    # Distance between two known points (~1.1 km apart)
    d1 = Complaint.haversine_distance(18.5204, 73.8567, 18.5300, 73.8567)
    assert 1000 < d1 < 1200


def test_routing_engine():
    d_plastic = [Detection(cls="plastic", confidence=0.9, box=(0, 0, 100, 100))]
    assert determine_department(d_plastic) == "Recycling Department"

    d_organic = [Detection(cls="organic", confidence=0.8, box=(0, 0, 100, 100))]
    assert determine_department(d_organic) == "Sanitation Department"

    d_hazmat = [Detection(cls="hazardous", confidence=0.95, box=(0, 0, 100, 100))]
    assert determine_department(d_hazmat) == "Health & Hazmat Department"

    assert determine_department([]) == "Sanitation Department"


def test_severity_engine():
    # Small box, 1 item -> Low severity
    small_det = [Detection(cls="plastic", confidence=0.9, box=(0, 0, 50, 50))]
    sev = compute_severity(small_det, (1000, 1000))
    assert sev["level"] == "Low"

    # Many items -> High severity
    many_det = [Detection(cls="plastic", confidence=0.9, box=(i*10, i*10, i*10+20, i*10+20)) for i in range(10)]
    sev_high = compute_severity(many_det, (1000, 1000))
    assert sev_high["level"] == "High"


def test_mock_detector():
    detector = WasteDetector(mode="mock")
    detections, img_size = detector.detect("dummy_path.jpg")
    assert len(detections) >= 1
    assert img_size == (1280, 960)
