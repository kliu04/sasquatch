from __future__ import annotations

import io
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from api.ply_service import load_point_cloud, pixel_to_3d, render_point_cloud
from api.schemas import BBox, Hold, HoldsResponse, Position3D, ScanResponse
from hold_detector.app import HoldDetectionApp
from hold_detector.config import (
    AppConfig,
    DedupeConfig,
    DetectronConfig,
    GeminiConfig,
    OutputConfig,
    TapeFilterConfig,
)

# ---------------------------------------------------------------------------
# Scan registry
# ---------------------------------------------------------------------------

_BASE_DIR = Path(__file__).parent.parent  # hold-detector/


@dataclass
class ScanState:
    scan_id: str
    scan_dir: Path
    ply_path: Path
    pcd: Any | None = None
    rendered_image: np.ndarray | None = None
    cam_params: Any | None = None


scan_registry: dict[str, ScanState] = {}

# ---------------------------------------------------------------------------
# App lifecycle — load Detectron model once at startup
# ---------------------------------------------------------------------------

_hold_app: HoldDetectionApp | None = None


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _hold_app
    _hold_app = HoldDetectionApp(_default_config())
    yield


app = FastAPI(lifespan=lifespan)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_scan(scan_id: str) -> ScanState:
    if scan_id not in scan_registry:
        raise HTTPException(status_code=404, detail=f"Scan '{scan_id}' not found.")
    return scan_registry[scan_id]


def _ensure_projection(state: ScanState) -> None:
    """Load + render the point cloud if not already cached."""
    if state.rendered_image is not None:
        return
    pcd = load_point_cloud(state.ply_path)
    image_bgr, cam_params = render_point_cloud(pcd)
    state.pcd = pcd
    state.rendered_image = image_bgr
    state.cam_params = cam_params


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/scans", response_model=ScanResponse, status_code=201)
async def register_scan(file: UploadFile):
    """Upload a single .ply file to create a new scan resource."""
    if not (file.filename or "").lower().endswith(".ply"):
        raise HTTPException(status_code=400, detail=f"Only a .ply file is accepted, got: {file.filename}")

    scan_id = str(uuid.uuid4())
    scan_dir = _BASE_DIR / "3d-data" / "uploads" / scan_id
    scan_dir.mkdir(parents=True, exist_ok=True)

    ply_path = scan_dir / Path(file.filename).name
    ply_path.write_bytes(await file.read())

    scan_registry[scan_id] = ScanState(
        scan_id=scan_id,
        scan_dir=scan_dir,
        ply_path=ply_path,
    )

    return ScanResponse(scan_id=scan_id, frame_count=1)


@app.get("/scans/{scan_id}/projection")
async def get_projection(scan_id: str):
    """Return a rendered 2D PNG image of the merged point cloud."""
    import cv2

    state = _get_scan(scan_id)
    _ensure_projection(state)

    ok, buf = cv2.imencode(".png", state.rendered_image)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to encode projection image.")

    return StreamingResponse(io.BytesIO(buf.tobytes()), media_type="image/png")


@app.get("/scans/{scan_id}/debug/holds")
async def get_holds_debug(scan_id: str):
    """Return projection image with detected holds annotated (bbox + ID label)."""
    import cv2

    state = _get_scan(scan_id)
    _ensure_projection(state)

    records = _hold_app.detect(scan_id, state.rendered_image)

    canvas = state.rendered_image.copy()
    for record in records:
        x1, y1, x2, y2 = (int(v) for v in record.bbox_xyxy)
        cx, cy = record.mask_centroid
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = str(record.instance_id)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(canvas, (cx - 2, cy - th - 4), (cx + tw + 2, cy + 2), (0, 255, 0), -1)
        cv2.putText(canvas, label, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

    ok, buf = cv2.imencode(".png", canvas)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to encode debug image.")

    return StreamingResponse(io.BytesIO(buf.tobytes()), media_type="image/png")


@app.get("/scans/{scan_id}/holds", response_model=HoldsResponse)
async def get_holds(scan_id: str):
    """Detect holds in the rendered point cloud projection and return 3D positions."""
    state = _get_scan(scan_id)
    _ensure_projection(state)

    records = _hold_app.detect(scan_id, state.rendered_image)

    holds: list[Hold] = []
    for record in records:
        cx, cy = record.mask_centroid
        pos_3d = pixel_to_3d(cx, cy, state.pcd, state.cam_params)

        if pos_3d is None:
            position = Position3D(x=0.0, y=0.0, z=0.0)
        else:
            position = Position3D(x=float(pos_3d[0]), y=float(pos_3d[1]), z=float(pos_3d[2]))

        x1, y1, x2, y2 = record.bbox_xyxy
        holds.append(
            Hold(
                id=record.instance_id,
                position=position,
                bbox=BBox(x1=x1, y1=y1, x2=x2, y2=y2),
                confidence=record.score,
                hold_type=None,
            )
        )

    return HoldsResponse(scan_id=scan_id, holds=holds)
