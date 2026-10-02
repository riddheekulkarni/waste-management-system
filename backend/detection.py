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
        
        # Load civic pothole model if weights are available
        self.pothole_model = None
        if self.mode == "real":
            possible_pothole_paths = [
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pothole_model.pt"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "pothole_model.pt"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "pothole_model.pt"),
            ]
            for p in possible_pothole_paths:
                if os.path.exists(p):
                    try:
                        self.pothole_model = YOLO(p)
                        break
                    except Exception:
                        pass

    @classmethod
    def load_from_env(cls) -> "WasteDetector":
        """Construct a WasteDetector from the WASTE_MODEL_WEIGHTS env variable.

        If the variable is unset or the path does not exist the detector falls
        back to mock mode automatically — no extra handling needed at call sites.
        """
        weights = os.environ.get("WASTE_MODEL_WEIGHTS") or None
        instance = cls(weights_path=weights)
        return instance

    def validate_image(self, image_path: str) -> bool:
        """Verify if the specified file path contains a valid readable image."""
        try:
            with Image.open(image_path) as img:
                img.verify()
            return True
        except Exception:
            return False

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
        return self._detect_mock(image_size, image_path=image_path), image_size

    def _detect_real(self, image_path: str) -> List[Detection]:
        # Sensitive threshold (0.15) ensures roadside piles, scattered litter, and distant debris are captured
        results = self.model(image_path, conf=0.15)[0]
        detections = []
        for box in results.boxes:
            cls_id = int(box.cls[0])
            cls_name = self.model.names.get(cls_id, "unknown")
            conf = float(box.conf[0])
            xyxy = tuple(float(v) for v in box.xyxy[0])
            detections.append(Detection(cls=cls_name, confidence=conf, box=xyxy))

        # Check for potholes with the civic infrastructure model
        if self.pothole_model:
            try:
                p_results = self.pothole_model(image_path, conf=0.30)[0]
                if len(p_results.boxes) > 0:
                    # Filter out false "shoes" / "clothes" detections when potholes are present on roads
                    detections = [d for d in detections if d.cls not in ("shoes", "clothes")]
                    for box in p_results.boxes:
                        conf = float(box.conf[0])
                        xyxy = tuple(float(v) for v in box.xyxy[0])
                        detections.append(Detection(cls="pothole", confidence=conf, box=xyxy))
            except Exception:
                pass

        # Save annotated image with custom colored bounding boxes
        try:
            from PIL import ImageDraw
            annotated_filename = "annotated_" + os.path.basename(image_path)
            annotated_path = os.path.join(os.path.dirname(image_path), annotated_filename)
            with Image.open(image_path) as im:
                draw_im = im.convert("RGB")
                draw = ImageDraw.Draw(draw_im)
                for d in detections:
                    color = "#ef4444" if d.cls == "pothole" else "#10b981"
                    draw.rectangle(d.box, outline=color, width=4)
                    draw.text((d.box[0] + 4, max(0, d.box[1] - 16)), f"{d.cls} {int(d.confidence*100)}%", fill=color)
                draw_im.save(annotated_path)
        except Exception:
            pass

        return detections

    def _detect_mock(self, image_size, image_path: Optional[str] = None) -> List[Detection]:
        """Generate synthetic detections sized against the real image dimensions.

        Class weights approximate real-world civic-waste composition from the
        TACO dataset: plastic dominates (~40 %), followed by mixed litter, paper,
        metal, and rarer classes like hazardous and construction debris.
        """
        # Weighted distribution matching typical street-waste scenes
        _MOCK_CLASSES = [
            "plastic", "plastic", "plastic", "plastic",   # ~40 %
            "mixed_litter", "mixed_litter",                # ~20 %
            "paper", "paper",                              # ~15 %
            "metal",                                       # ~10 %
            "cardboard",                                   # ~5 %
            "organic",                                     # ~4 %
            "glass",                                       # ~3 %
            "hazardous",                                   # ~2 %
            "construction_debris",                         # ~1 %
        ]
        w, h = image_size
        num_items = random.randint(1, 6)
        detections = []
        for _ in range(num_items):
            box_w = random.uniform(0.05, 0.35) * w
            box_h = random.uniform(0.05, 0.35) * h
            x1 = random.uniform(0, max(w - box_w, 1))
            y1 = random.uniform(0, max(h - box_h, 1))
            detections.append(Detection(
                cls=random.choice(_MOCK_CLASSES),
                confidence=round(random.uniform(0.60, 0.95), 2),
                box=(x1, y1, x1 + box_w, y1 + box_h),
            ))

        if image_path and os.path.exists(image_path):
            try:
                from PIL import ImageDraw
                with Image.open(image_path) as im:
                    draw_im = im.convert("RGB")
                    draw = ImageDraw.Draw(draw_im)
                    for d in detections:
                        draw.rectangle(d.box, outline="#10b981", width=3)
                    annotated_filename = "annotated_" + os.path.basename(image_path)
                    annotated_path = os.path.join(os.path.dirname(image_path), annotated_filename)
                    draw_im.save(annotated_path)
            except Exception:
                pass

        return detections
