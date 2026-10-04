"""
Stage 1 — Object Detection Module.

Real mode: loads a custom-trained YOLOv8 .pt file with ultralytics.
Mock mode: generates synthetic detections sized against the actual uploaded
image's real dimensions.

Key requirements:
- Explicit AI execution mode: REAL_YOLO vs MOCK_DEMO.
- Never silently claim real inference when falling back to mock mode.
- Log explicit reasons when configured weights or dependencies are unavailable.
- Normalize all detected classes to the project's canonical 9-class ontology.
"""

import logging
import os
import random
from dataclasses import dataclass
from typing import List, NamedTuple, Optional, Tuple

from PIL import Image

from ai_config import (
    AI_MODE_LABELS,
    AI_MODE_MOCK_DEMO,
    AI_MODE_REAL_YOLO,
    CANONICAL_WASTE_CLASSES,
    normalize_waste_class,
)

logger = logging.getLogger(__name__)

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False


@dataclass
class Detection:
    cls: str  # canonical waste class
    confidence: float
    box: Tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels
    raw_cls: Optional[str] = None  # original class name from raw model output


class DetectionResult(NamedTuple):
    detections: List[Detection]
    image_size: Tuple[int, int]
    ai_mode: str


class WasteDetector:
    def __init__(self, weights_path: Optional[str] = None, mode: str = "auto"):
        self.weights_path = weights_path
        self.mock_reason: Optional[str] = None
        self.model = None
        self.pothole_model = None

        if mode == "mock":
            self.mode = "mock"
            self.ai_mode = AI_MODE_MOCK_DEMO
            self.mock_reason = "Explicitly initialized in mock mode."
        elif mode in ("real", "auto"):
            can_load_real, reason = self._can_load_model(weights_path)
            if can_load_real:
                try:
                    self.model = YOLO(weights_path)
                    self.mode = "real"
                    self.ai_mode = AI_MODE_REAL_YOLO
                    self.mock_reason = None
                    logger.info("🤖 WasteDetector: REAL mode active with weights: %s", weights_path)
                except Exception as exc:
                    self.mode = "mock"
                    self.ai_mode = AI_MODE_MOCK_DEMO
                    self.mock_reason = f"Failed to initialize YOLO model from '{weights_path}': {exc}"
                    logger.warning(
                        "⚠️ WasteDetector: Model load failure. Falling back to MOCK_DEMO mode: %s",
                        self.mock_reason,
                    )
            else:
                self.mode = "mock"
                self.ai_mode = AI_MODE_MOCK_DEMO
                self.mock_reason = reason
                if mode == "real" or weights_path:
                    logger.warning(
                        "⚠️ WasteDetector: Configured YOLO model unavailable (%s). "
                        "Executing in MOCK_DEMO mode. Real inference will NOT be claimed.",
                        reason,
                    )
        else:
            self.mode = "mock"
            self.ai_mode = AI_MODE_MOCK_DEMO
            self.mock_reason = f"Unrecognized mode '{mode}', defaulting to mock."

        # Load civic pothole model if weights are available and real mode is active
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
                        logger.info("Civil infrastructure pothole model loaded: %s", p)
                        break
                    except Exception as exc:
                        logger.debug("Could not load pothole model: %s", exc)

    @staticmethod
    def _can_load_model(weights_path: Optional[str]) -> Tuple[bool, Optional[str]]:
        if not ULTRALYTICS_AVAILABLE:
            return False, "ultralytics package is not installed."
        if not weights_path:
            return False, "No YOLO model weights file path specified."
        if not os.path.exists(weights_path):
            return False, f"Model weights file not found on disk: {weights_path}"
        return True, None

    @classmethod
    def load_from_env(cls) -> "WasteDetector":
        """Construct a WasteDetector using WASTE_MODEL_WEIGHTS from environment."""
        weights = os.environ.get("WASTE_MODEL_WEIGHTS") or None
        return cls(weights_path=weights)

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

    def detect(self, image_path: str) -> DetectionResult:
        """
        Run detection on image.

        Returns DetectionResult tuple: (detections, image_size, ai_mode).
        Can be unpacked as 2-item (detections, image_size) or 3-item (detections, image_size, ai_mode).
        """
        image_size = self.get_image_size(image_path)
        if self.mode == "real" and self.model is not None:
            try:
                detections = self._detect_real(image_path)
                return DetectionResult(detections, image_size, AI_MODE_REAL_YOLO)
            except Exception as exc:
                logger.error("Real YOLO detection failed at runtime: %s. Falling back to MOCK_DEMO.", exc)
                detections = self._detect_mock(image_size, image_path=image_path)
                return DetectionResult(detections, image_size, AI_MODE_MOCK_DEMO)

        detections = self._detect_mock(image_size, image_path=image_path)
        return DetectionResult(detections, image_size, AI_MODE_MOCK_DEMO)

    def _detect_real(self, image_path: str) -> List[Detection]:
        # Sensitive threshold (0.15) ensures roadside piles, scattered litter, and distant debris are captured
        results = self.model(image_path, conf=0.15)[0]
        detections: List[Detection] = []

        for box in results.boxes:
            cls_id = int(box.cls[0])
            raw_cls_name = self.model.names.get(cls_id, "unknown")
            canonical_cls = normalize_waste_class(raw_cls_name)
            conf = float(box.conf[0])
            xyxy = tuple(float(v) for v in box.xyxy[0])
            detections.append(Detection(cls=canonical_cls, confidence=conf, box=xyxy, raw_cls=raw_cls_name))

        # Check for potholes with the civic infrastructure model
        if self.pothole_model:
            try:
                p_results = self.pothole_model(image_path, conf=0.30)[0]
                if len(p_results.boxes) > 0:
                    # Filter out false "shoes" / "clothes" / "mixed_litter" detections when potholes are present on roads
                    detections = [d for d in detections if d.raw_cls not in ("shoes", "clothes")]
                    for box in p_results.boxes:
                        conf = float(box.conf[0])
                        xyxy = tuple(float(v) for v in box.xyxy[0])
                        detections.append(Detection(cls="pothole", confidence=conf, box=xyxy, raw_cls="pothole"))
            except Exception as exc:
                logger.debug("Pothole inference error: %s", exc)

        # Save annotated image with custom colored bounding boxes
        try:
            from PIL import ImageDraw
            annotated_filename = "annotated_" + os.path.basename(image_path)
            annotated_path = os.path.join(os.path.dirname(image_path), annotated_filename)
            with Image.open(image_path) as im:
                draw_im = im.convert("RGB")
                draw = ImageDraw.Draw(draw_im)
                for d in detections:
                    color = "#ef4444" if d.cls in ("pothole", "hazardous") else "#10b981"
                    draw.rectangle(d.box, outline=color, width=4)
                    draw.text(
                        (d.box[0] + 4, max(0, d.box[1] - 16)),
                        f"{d.cls} {int(d.confidence * 100)}%",
                        fill=color,
                    )
                draw_im.save(annotated_path)
        except Exception as exc:
            logger.debug("Failed saving real annotated image: %s", exc)

        return detections

    def _detect_mock(self, image_size: Tuple[int, int], image_path: Optional[str] = None) -> List[Detection]:
        """Generate synthetic detections sized against real image dimensions."""
        _MOCK_CLASSES = [
            "plastic", "plastic", "plastic", "plastic",
            "mixed_litter", "mixed_litter",
            "paper", "paper",
            "metal",
            "cardboard",
            "organic",
            "glass",
            "hazardous",
            "construction_debris",
        ]
        w, h = image_size
        num_items = random.randint(1, 6)
        detections: List[Detection] = []
        for _ in range(num_items):
            box_w = random.uniform(0.05, 0.35) * w
            box_h = random.uniform(0.05, 0.35) * h
            x1 = random.uniform(0, max(w - box_w, 1))
            y1 = random.uniform(0, max(h - box_h, 1))
            chosen_cls = random.choice(_MOCK_CLASSES)
            detections.append(Detection(
                cls=chosen_cls,
                confidence=round(random.uniform(0.60, 0.95), 2),
                box=(x1, y1, x1 + box_w, y1 + box_h),
                raw_cls=chosen_cls,
            ))

        if image_path and os.path.exists(image_path):
            try:
                from PIL import ImageDraw
                with Image.open(image_path) as im:
                    draw_im = im.convert("RGB")
                    draw = ImageDraw.Draw(draw_im)
                    for d in detections:
                        draw.rectangle(d.box, outline="#f59e0b", width=3)
                        draw.text(
                            (d.box[0] + 4, max(0, d.box[1] - 16)),
                            f"[DEMO] {d.cls} {int(d.confidence * 100)}%",
                            fill="#f59e0b",
                        )
                    annotated_filename = "annotated_" + os.path.basename(image_path)
                    annotated_path = os.path.join(os.path.dirname(image_path), annotated_filename)
                    draw_im.save(annotated_path)
            except Exception as exc:
                logger.debug("Failed saving mock annotated image: %s", exc)

        return detections
