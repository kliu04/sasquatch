"""
Sasquatch hold-detection & route-building library.

Usage:
    from api.main import SasquatchEngine

    engine = SasquatchEngine()
    scan = engine.create_scan("scan.ply", "photo.png")
    holds = scan.get_holds()
    routes = scan.get_routes(difficulty="easy", style="dynamic")
    scan.save_debug_holds("debug_holds.png")
    scan.save_debug_routes("debug_routes.png", difficulty="easy", style="dynamic")
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from api.route_service import build_routes
from api.scan_service import ScanState, draw_debug_overlay, draw_routes_overlay, prepare_scan, process_scan
from api.schemas import Hold
from hold_detector.app import HoldDetectionApp
from hold_detector.config import (
    AppConfig,
    DedupeConfig,
    DetectronConfig,
    GeminiConfig,
    OutputConfig,
    TapeFilterConfig,
)

_BASE_DIR = Path(__file__).parent.parent  # hold-detector/


def _default_config() -> AppConfig:
    return AppConfig(
        images=[],
        detectron=DetectronConfig(
            config_path=_BASE_DIR / "archive/model/experiment_config.yml",
            weights_path=_BASE_DIR / "archive/model/model_final.pth",
            device="cpu",
            score_threshold=0.5,
            max_detections=300,
        ),
        tape_filter=TapeFilterConfig(
            enabled=False,
            uniformity_std=18.0,
            min_fill=0.58,
            min_aspect=1.0,
            max_vertices=4,
            min_minrect_fill=0.85,
        ),
        dedupe=DedupeConfig(
            enabled=True,
            mask_overlap_threshold=0.8,
            box_overlap_threshold=0.9,
        ),
        gemini=GeminiConfig(
            enabled=True,
            model="gemini-3.1-flash-lite-preview",
            api_key=None,
            api_key_env="HOLD_CLASSIFICATION_KEY_GEMINI",
            concurrency=100,
            max_retries=2,
            timeout_seconds=60,
            save_crops=False,
        ),
        output=OutputConfig(
            output_dir=_BASE_DIR / "detectron-output",
            save_raw_detectron=False,
        ),
    )


# ---------------------------------------------------------------------------
# Scan handle — returned by SasquatchEngine.create_scan()
# ---------------------------------------------------------------------------


class Scan:
    """A processed scan. All heavy work is done at creation time."""

    def __init__(self, state: ScanState) -> None:
        self._state = state

    @property
    def scan_id(self) -> str:
        return self._state.scan_id

    @property
    def photo(self) -> np.ndarray:
        """The photo used for detection (BGR numpy array)."""
        return self._state.photo

    @property
    def rendered_image(self) -> np.ndarray:
        """The 2D render of the point cloud (BGR numpy array)."""
        return self._state.rendered_image

    def get_holds(self) -> list[Hold]:
        """Return detected holds with 3D positions and depth."""
        return self._state.holds

    def get_routes(
        self,
        difficulty: str = "medium",
        style: str = "static",
        wingspan: float = 1.8,
        top_k: int = 3,
    ) -> list[list[int]]:
        """Generate climbing routes. Returns list of hold-ID sequences."""
        return build_routes(
            self._state.holds,
            difficulty=difficulty,
            style=style,
            wingspan=wingspan,
            final_k=top_k,
        )

    def debug_holds_image(self) -> np.ndarray:
        """Return photo annotated with hold bboxes, IDs, and depths."""
        return draw_debug_overlay(self._state)

    def debug_routes_image(
        self,
        difficulty: str = "medium",
        style: str = "static",
        wingspan: float = 1.8,
        top_k: int = 3,
    ) -> np.ndarray:
        """Return photo with top-k routes drawn as colored polylines."""
        routes = self.get_routes(difficulty=difficulty, style=style, wingspan=wingspan, top_k=top_k)
        return draw_routes_overlay(self._state, routes)



# ---------------------------------------------------------------------------
# Engine — create once, use for multiple scans
# ---------------------------------------------------------------------------


class SasquatchEngine:
    """Main entry point. Loads the ML model once, then processes scans."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self._config = config or _default_config()
        self._hold_app = HoldDetectionApp(self._config)

    def create_scan(
        self,
        ply_path: str | Path,
        png_path: str | Path | None = None,
    ) -> Scan:
        """Load a PLY + optional PNG, detect holds, compute 3D positions.

        This is synchronous and blocking — all processing happens here.
        Returns a Scan object with holds, routes, and debug images.
        """
        ply_path = Path(ply_path)
        png_path = Path(png_path) if png_path is not None else None

        state = ScanState(
            scan_id=ply_path.stem,
            scan_dir=ply_path.parent,
            ply_path=ply_path,
            png_path=png_path,
        )

        prepare_scan(state)
        process_scan(state, self._hold_app)

        return Scan(state)
