import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "waste_management.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    # Set this env var once a custom-trained YOLOv8 model exists.
    WASTE_MODEL_WEIGHTS = os.environ.get("WASTE_MODEL_WEIGHTS")
