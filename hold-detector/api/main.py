from __future__ import annotations

import io
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import cv2
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from api.route_service import build_routes
from api.scan_repository import InMemoryScanRepository, ScanRepository
from api.scan_service import ScanState, draw_debug_overlay, ensure_processed
from api.schemas import HoldsResponse, Route, RoutesResponse, ScanResponse
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

# ---------------------------------------------------------------------------
# App state (created once at startup, injected into endpoints)
# ---------------------------------------------------------------------------

_hold_app: HoldDetectionApp | None = None
_repo: ScanRepository | None = None


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
    global _hold_app, _repo
    _hold_app = HoldDetectionApp(_default_config())
    _repo = InMemoryScanRepository()
    yield


app = FastAPI(lifespan=lifespan)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_scan(scan_id: str) -> ScanState:
    state = _repo.get(scan_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Scan '{scan_id}' not found.")
    return state


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/scans", response_model=ScanResponse, status_code=201)
async def register_scan(ply_file: UploadFile, png_file: UploadFile | None = None):
    """Upload a .ply file and an optional .png photo to create a new scan resource."""
    if not (ply_file.filename or "").lower().endswith(".ply"):
        raise HTTPException(status_code=400, detail=f"ply_file must be a .ply file, got: {ply_file.filename}")

    scan_id = str(uuid.uuid4())
    scan_dir = _BASE_DIR / "3d-data" / "uploads" / scan_id
    scan_dir.mkdir(parents=True, exist_ok=True)

    ply_path = scan_dir / Path(ply_file.filename).name
    ply_path.write_bytes(await ply_file.read())

    png_path: Path | None = None
    if png_file is not None:
        png_path = scan_dir / Path(png_file.filename).name
        png_path.write_bytes(await png_file.read())

    state = ScanState(scan_id=scan_id, scan_dir=scan_dir, ply_path=ply_path, png_path=png_path)
    _repo.create(state)
    return ScanResponse(scan_id=scan_id, frame_count=1)


@app.get("/scans/{scan_id}/projection")
async def get_projection(scan_id: str):
    """Return a rendered 2D PNG image of the point cloud."""
    state = _get_scan(scan_id)
    ensure_processed(state, _hold_app)

    ok, buf = cv2.imencode(".png", state.rendered_image)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to encode image.")
    return StreamingResponse(io.BytesIO(buf.tobytes()), media_type="image/png")


@app.get("/scans/{scan_id}/holds", response_model=HoldsResponse)
async def get_holds(scan_id: str):
    """Detect holds and return 3D positions with depth."""
    state = _get_scan(scan_id)
    ensure_processed(state, _hold_app)
    return HoldsResponse(scan_id=scan_id, holds=state.holds)


@app.get("/scans/{scan_id}/debug/holds")
async def get_holds_debug(scan_id: str):
    """Return the photo annotated with hold bounding boxes, IDs, and depths."""
    state = _get_scan(scan_id)
    ensure_processed(state, _hold_app)

    canvas = draw_debug_overlay(state)
    ok, buf = cv2.imencode(".png", canvas)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to encode image.")
    return StreamingResponse(io.BytesIO(buf.tobytes()), media_type="image/png")


@app.get("/scans/{scan_id}/routes", response_model=RoutesResponse)
async def get_routes(
    scan_id: str,
    difficulty: str = "medium",
    style: str = "static",
    wingspan: float = 1.8,
):
    """Generate climbing routes from detected holds using real 3D distances.

    Args:
        difficulty: easy | medium | hard — controls total route budget (metres)
        style:      static | dynamic — controls move distance range and style preference
        wingspan:   climber's max reach in metres (default 1.8m)
    """
    if difficulty not in ("easy", "medium", "hard"):
        raise HTTPException(status_code=400, detail="difficulty must be easy, medium, or hard")
    if style not in ("static", "dynamic"):
        raise HTTPException(status_code=400, detail="style must be static or dynamic")

    state = _get_scan(scan_id)
    ensure_processed(state, _hold_app)

    route_ids = build_routes(
        state.holds,
        difficulty=difficulty,
        style=style,
        wingspan=wingspan,
    )

    return RoutesResponse(
        scan_id=scan_id,
        difficulty=difficulty,
        style=style,
        routes=[Route(holds=r) for r in route_ids],
    )
