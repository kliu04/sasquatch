"""Background scan processing worker.

Orchestrates SasquatchEngine for hold detection. The API layer delegates
all ML work here — routers never import from hold_detector directly.
"""
from __future__ import annotations

import asyncio
import json
import sys
import threading
from pathlib import Path

import cv2

# Add hold-detector to path so we can import its modules
_HOLD_DETECTOR_DIR = Path(__file__).parent.parent / "hold-detector"
if str(_HOLD_DETECTOR_DIR) not in sys.path:
    sys.path.insert(0, str(_HOLD_DETECTOR_DIR))

import numpy as np

from api.main import SasquatchEngine
from api.route_service import build_routes
from api.scan_service import (
    ScanState,
    draw_debug_overlay,
    draw_routes_overlay,
    prepare_scan,
    process_scan,
)
from api.schemas import BBox, Hold, Position3D
from hold_detector.app import HoldDetectionApp

from database.db import SessionLocal
from database.schema import Wall, WallStatus
from database.storage import GCSStorage


class ScanWorker:
    """Background worker that processes wall scans via SasquatchEngine."""

    def __init__(self, storage: GCSStorage):
        self._storage = storage
        self._engine: SasquatchEngine | None = None
        self._scans: dict[int, ScanState] = {}
        self._ready_events: dict[int, asyncio.Event] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def _ensure_engine(self) -> SasquatchEngine:
        if self._engine is None:
            self._engine = SasquatchEngine()
        return self._engine

    def get_scan_state(self, wall_id: int) -> ScanState | None:
        return self._scans.get(wall_id)

    def get_or_create_event(self, wall_id: int) -> asyncio.Event:
        if wall_id not in self._ready_events:
            self._ready_events[wall_id] = asyncio.Event()
        return self._ready_events[wall_id]

    async def wait_for_ready(self, wall_id: int, timeout: float = 30.0) -> str:
        """Long-poll: wait until wall processing completes or timeout."""
        event = self.get_or_create_event(wall_id)
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
        # Return current status from DB
        db = SessionLocal()
        try:
            wall = db.query(Wall).filter(Wall.id == wall_id).first()
            return wall.status.name if wall else "error"
        finally:
            db.close()

    def start_processing(self, wall_id: int, loop: asyncio.AbstractEventLoop) -> None:
        """Start background processing for a wall. Non-blocking."""
        self._loop = loop
        thread = threading.Thread(
            target=self._process_wall,
            args=(wall_id,),
            daemon=True,
        )
        thread.start()

    def _process_wall(self, wall_id: int) -> None:
        """Run scan pipeline in background thread. Picks 3D or 2D mode based on PLY presence."""
        db = SessionLocal()
        ply_tmp = None
        png_tmp = None
        try:
            wall = db.query(Wall).filter(Wall.id == wall_id).first()
            if wall is None:
                return

            wall.status = WallStatus.processing
            db.commit()

            # Download PNG (always required)
            png_gcs = f"walls/{wall_id}/photo.png"
            png_tmp = self._storage.download_to_tempfile(png_gcs, suffix=".png")

            # Check if PLY exists (wall_ply_url is set during wall creation when has_ply=true)
            has_ply = wall.wall_ply_url is not None
            if has_ply:
                ply_gcs = f"walls/{wall_id}/scan.ply"
                ply_tmp = self._storage.download_to_tempfile(ply_gcs, suffix=".ply")

            if has_ply:
                self._process_3d(wall_id, wall, ply_tmp, png_tmp, db)
            else:
                self._process_2d(wall_id, wall, png_tmp, db)

        except Exception as exc:
            db.rollback()
            wall = db.query(Wall).filter(Wall.id == wall_id).first()
            if wall:
                wall.status = WallStatus.error
                wall.error_message = str(exc)
                db.commit()
            print(f"[scan_worker] error processing wall {wall_id}: {exc}", flush=True)
            import traceback
            traceback.print_exc()
        finally:
            db.close()
            if ply_tmp and ply_tmp.exists():
                ply_tmp.unlink()
            if png_tmp and png_tmp.exists():
                png_tmp.unlink()
            if self._loop and wall_id in self._ready_events:
                self._loop.call_soon_threadsafe(self._ready_events[wall_id].set)

    def _process_3d(self, wall_id: int, wall: Wall, ply_tmp: Path, png_tmp: Path, db) -> None:
        """Full 3D pipeline: PLY + PNG -> holds with 3D positions and depth."""
        engine = self._ensure_engine()
        scan = engine.create_scan(ply_tmp, png_tmp)

        self._scans[wall_id] = scan._state

        holds = scan.get_holds()
        holds_data = [
            {
                "id": h.id,
                "position": {"x": h.position.x, "y": h.position.y, "z": h.position.z},
                "bbox": {"x1": h.bbox.x1, "y1": h.bbox.y1, "x2": h.bbox.x2, "y2": h.bbox.y2},
                "confidence": h.confidence,
                "depth": h.depth,
                "hold_type": h.hold_type,
            }
            for h in holds
        ]

        # Generate and upload images
        holds_img = scan.debug_holds_image()
        _, holds_png = cv2.imencode(".png", holds_img)
        holds_img_url = self._storage.upload_bytes(
            holds_png.tobytes(), f"walls/{wall_id}/holds_overlay.png",
        )

        _, photo_png = cv2.imencode(".png", scan.photo)
        wall_img_url = self._storage.upload_bytes(
            photo_png.tobytes(), f"walls/{wall_id}/wall_photo.png",
        )

        wall.status = WallStatus.ready
        wall.hold_count = len(holds)
        wall.holds_json = json.dumps(holds_data)
        wall.holds_image_url = holds_img_url
        wall.wall_img_url = wall_img_url
        db.commit()

    def _process_2d(self, wall_id: int, wall: Wall, png_tmp: Path, db) -> None:
        """2D-only pipeline: PNG -> holds with synthetic metric positions for route generation."""
        engine = self._ensure_engine()
        hold_app = engine._hold_app

        # Read the image
        photo = cv2.imread(str(png_tmp))
        if photo is None:
            raise ValueError(f"Could not read image: {png_tmp}")

        # Run detection directly (no Open3D needed)
        records, masks = hold_app.detect(f"wall_{wall_id}", photo)

        # Map pixel positions to synthetic 3D metre coordinates.
        # Assume the image spans ~4m wide x ~5m tall (typical climbing wall).
        # This lets build_routes() work with its metre-based distance thresholds.
        img_h, img_w = photo.shape[:2]
        wall_width_m = 4.0
        wall_height_m = 5.0
        px_to_m_x = wall_width_m / img_w
        px_to_m_y = wall_height_m / img_h

        holds: list[Hold] = []
        for record in records:
            x1, y1, x2, y2 = record.bbox_xyxy
            cx, cy = record.mask_centroid
            # Synthetic depth from bbox area (larger hold = deeper/more grabbable)
            area_px = (x2 - x1) * (y2 - y1)
            depth = (area_px / (img_w * img_h)) * 0.1  # normalize to ~0-0.1m range
            holds.append(Hold(
                id=record.instance_id,
                position=Position3D(
                    x=float(cx) * px_to_m_x,
                    y=float(cy) * px_to_m_y,
                    z=0.0,
                ),
                bbox=BBox(x1=x1, y1=y1, x2=x2, y2=y2),
                confidence=record.score,
                depth=max(depth, 0.005),
            ))

        holds_data = [
            {
                "id": h.id,
                "position": {"x": h.position.x, "y": h.position.y, "z": h.position.z},
                "bbox": {"x1": h.bbox.x1, "y1": h.bbox.y1, "x2": h.bbox.x2, "y2": h.bbox.y2},
                "confidence": h.confidence,
                "depth": h.depth,
                "hold_type": h.hold_type,
            }
            for h in holds
        ]

        # Build a minimal ScanState for visualization
        state = ScanState(
            scan_id=f"wall_{wall_id}",
            scan_dir=png_tmp.parent,
            ply_path=png_tmp,  # placeholder
            png_path=png_tmp,
            photo=photo,
            records=records,
            masks=masks,
            holds=holds,
            status="ready",
        )
        self._scans[wall_id] = state

        # Generate holds overlay
        holds_img = draw_debug_overlay(state)
        _, holds_png_bytes = cv2.imencode(".png", holds_img)
        holds_img_url = self._storage.upload_bytes(
            holds_png_bytes.tobytes(), f"walls/{wall_id}/holds_overlay.png",
        )

        # Upload wall photo
        _, photo_png = cv2.imencode(".png", photo)
        wall_img_url = self._storage.upload_bytes(
            photo_png.tobytes(), f"walls/{wall_id}/wall_photo.png",
        )

        wall.status = WallStatus.ready
        wall.hold_count = len(holds)
        wall.holds_json = json.dumps(holds_data)
        wall.holds_image_url = holds_img_url
        wall.wall_img_url = wall_img_url
        db.commit()

    def generate_routes(
        self,
        wall_id: int,
        holds_json: str,
        difficulty: str,
        style: str,
        wingspan: float,
        top_k: int,
    ) -> tuple[list[list[int]], list[bytes]]:
        """Generate routes and their visualization images.

        Returns (routes, images) where images is a list of PNG bytes per route.
        """
        # Reconstruct Hold objects from JSON
        holds_data = json.loads(holds_json)
        holds = [
            Hold(
                id=h["id"],
                position={"x": h["position"]["x"], "y": h["position"]["y"], "z": h["position"]["z"]},
                bbox={"x1": h["bbox"]["x1"], "y1": h["bbox"]["y1"], "x2": h["bbox"]["x2"], "y2": h["bbox"]["y2"]},
                confidence=h["confidence"],
                depth=h.get("depth", 0.0),
                hold_type=h.get("hold_type"),
            )
            for h in holds_data
        ]

        # Generate routes (functional: holds in, routes out)
        routes = build_routes(
            holds,
            difficulty=difficulty,
            style=style,
            wingspan=wingspan,
            final_k=top_k,
        )

        # Generate visualization images
        images: list[bytes] = []
        scan_state = self._scans.get(wall_id)

        # If scan state isn't cached, build a minimal one from the wall image
        if scan_state is None:
            from database.db import SessionLocal
            db = SessionLocal()
            try:
                wall = db.query(Wall).filter(Wall.id == wall_id).first()
                if wall and wall.wall_img_url:
                    try:
                        tmp_path = self._storage.download_to_tempfile(
                            self._storage._gcs_path(wall.wall_img_url), suffix=".png"
                        )
                        photo = cv2.imread(str(tmp_path))
                        tmp_path.unlink(missing_ok=True)
                        if photo is not None:
                            scan_state = ScanState(
                                scan_id=str(wall_id),
                                scan_dir=Path("/tmp"),
                                ply_path=Path("/tmp/dummy.ply"),
                            )
                            scan_state.photo = photo
                            scan_state.holds = holds
                            scan_state.masks = None
                            scan_state.records = None
                    except Exception as e:
                        print(f"Failed to download wall image for route overlay: {e}")
            finally:
                db.close()

        if scan_state is not None:
            for route in routes:
                route_img = draw_routes_overlay(scan_state, [route])
                _, png_data = cv2.imencode(".png", route_img)
                images.append(png_data.tobytes())

        return routes, images
