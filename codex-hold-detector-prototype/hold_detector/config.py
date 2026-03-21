from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class DetectronConfig:
    config_path: Path
    weights_path: Path
    device: str
    score_threshold: float
    max_detections: int


@dataclass(slots=True)
class TapeFilterConfig:
    enabled: bool
    uniformity_std: float
    min_fill: float
    min_aspect: float
    max_vertices: int
    min_minrect_fill: float


@dataclass(slots=True)
class DedupeConfig:
    enabled: bool
    mask_overlap_threshold: float
    box_overlap_threshold: float


@dataclass(slots=True)
class GeminiConfig:
    enabled: bool
    model: str
    api_key: str | None
    api_key_env: str
    concurrency: int
    max_retries: int
    timeout_seconds: int
    save_crops: bool


@dataclass(slots=True)
class OutputConfig:
    output_dir: Path
    save_raw_detectron: bool


@dataclass(slots=True)
class AppConfig:
    images: list[str]
    detectron: DetectronConfig
    tape_filter: TapeFilterConfig
    dedupe: DedupeConfig
    gemini: GeminiConfig
    output: OutputConfig
