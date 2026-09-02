"""
Stage 1 — Object Detection Module.

Real mode: loads a custom-trained YOLOv8 .pt file with ultralytics.
Mock mode: generates plausible synthetic detections sized against the
actual uploaded image's real dimensions, so the severity engine downstream
still behaves realistically. This lets the full application run today,
before a custom-trained waste-detection model exists (see future scope
item #1 in the roadmap).
"""

import os
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

from PIL import Image

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False


WASTE_CLASSES = [
    "plastic", "paper", "cardboard", "glass", "metal",
    "organic", "hazardous", "construction_debris", "mixed_litter",
]


@dataclass
class Detection:
    cls: str
    confidence: float
    box: Tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels


class WasteDetector:
    def __init__(self, weights_path: Optional[str] = None, mode: str = "auto"):
        self.weights_path = weights_path
        if mode == "auto":
            mode = "real" if (weights_path and os.path.exists(weights_path)
                               and ULTRALYTICS_AVAILABLE) else "mock"
        self.mode = mode
        self.model = YOLO(weights_path) if self.mode == "real" else None

    def get_image_size(self, image_path: str) -> Tuple[int, int]:
        try:
            with Image.open(image_path) as img:
                return img.size  # (width, height)
        except Exception:
            return (1280, 960)  # fallback default

    def detect(self, image_path: str) -> Tuple[List[Detection], Tuple[int, int]]:
        image_size = self.get_image_size(image_path)
        if self.mode == "real":
            return self._detect_real(image_path), image_size
        return self._detect_mock(image_size), image_size

    def _detect_real(self, image_path: str) -> List[Detection]:
        results = self.model(image_path)[0]
        detections = []
        for box in results.boxes:
            cls_id = int(box.cls[0])
            cls_name = self.model.names.get(cls_id, "unknown")
            conf = float(box.conf[0])
            xyxy = tuple(float(v) for v in box.xyxy[0])
            detections.append(Detection(cls=cls_name, confidence=conf, box=xyxy))
        return detections

    def _detect_mock(self, image_size) -> List[Detection]:
        w, h = image_size
        num_items = random.randint(1, 6)
        detections = []
        for _ in range(num_items):
            box_w = random.uniform(0.05, 0.35) * w
            box_h = random.uniform(0.05, 0.35) * h
            x1 = random.uniform(0, max(w - box_w, 1))
            y1 = random.uniform(0, max(h - box_h, 1))
            detections.append(Detection(
                cls=random.choice(WASTE_CLASSES),
                confidence=round(random.uniform(0.55, 0.97), 2),
                box=(x1, y1, x1 + box_w, y1 + box_h),
            ))
        return detections
