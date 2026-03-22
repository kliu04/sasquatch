from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import cv2

from hold_detector.config import GeminiConfig
from hold_detector.constants import SUPPORTED_IMAGE_EXTS


def load_dotenv(dotenv_path: Path = Path(".env")) -> None:
    if not dotenv_path.is_file():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def resolve_api_key(config: GeminiConfig) -> str | None:
    if config.api_key:
        return config.api_key
    load_dotenv()
    if config.api_key_env:
        value = os.getenv(config.api_key_env)
        if value:
            return value
    return os.getenv("GOOGLE_API_KEY")


def collect_images(raw_images: list[str]) -> list[Path]:
    if raw_images:
        image_paths = [Path(item).resolve() for item in raw_images]
    else:
        demo_dir = Path("demo-data").resolve()
        image_paths = [
            path.resolve()
            for path in sorted(demo_dir.iterdir())
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTS
        ]
    if not image_paths:
        raise FileNotFoundError("No input images found.")
    for image_path in image_paths:
        if not image_path.is_file():
            raise FileNotFoundError(f"Image not found: {image_path}")
    return image_paths


def read_image(image_path: Path):
    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError(f"OpenCV failed to read {image_path}")
    return image


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
