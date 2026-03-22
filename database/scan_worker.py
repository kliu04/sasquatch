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

from api.main import SasquatchEngine
from api.route_service import build_routes
from api.scan_service import (
    ScanState,
    draw_debug_overlay,
    draw_routes_overlay,
    prepare_scan,
    process_scan,
)
from api.schemas import Hold

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
        """Run full scan pipeline in background thread."""
        db = SessionLocal()
        ply_tmp = None
        png_tmp = None
        try:
            wall = db.query(Wall).filter(Wall.id == wall_id).first()
            if wall is None:
                return

            # Update status
            wall.status = WallStatus.processing
            db.commit()

            # Download files from GCS
            ply_gcs = f"walls/{wall_id}/scan.ply"
            png_gcs = f"walls/{wall_id}/photo.png"
            ply_tmp = self._storage.download_to_tempfile(ply_gcs, suffix=".ply")
            png_tmp = self._storage.download_to_tempfile(png_gcs, suffix=".png")

            # Run the engine
            engine = self._ensure_engine()
            scan = engine.create_scan(ply_tmp, png_tmp)

            # Store scan state for route generation later
            self._scans[wall_id] = scan._state

            # Serialize holds to JSON
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

            # Generate holds overlay image
            holds_img = scan.debug_holds_image()
            _, holds_png = cv2.imencode(".png", holds_img)
            holds_img_url = self._storage.upload_bytes(
                holds_png.tobytes(),
                f"walls/{wall_id}/holds_overlay.png",
            )

            # Also upload the wall photo (the rendered/resized version used for detection)
            _, photo_png = cv2.imencode(".png", scan.photo)
            wall_img_url = self._storage.upload_bytes(
                photo_png.tobytes(),
                f"walls/{wall_id}/wall_photo.png",
            )

            # Update DB
            wall.status = WallStatus.ready
            wall.hold_count = len(holds)
            wall.holds_json = json.dumps(holds_data)
            wall.holds_image_url = holds_img_url
            wall.wall_img_url = wall_img_url
            db.commit()

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
            # Clean up temp files
            if ply_tmp and ply_tmp.exists():
                ply_tmp.unlink()
            if png_tmp and png_tmp.exists():
                png_tmp.unlink()
            # Signal long-pollers
            if self._loop and wall_id in self._ready_events:
                self._loop.call_soon_threadsafe(self._ready_events[wall_id].set)

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

        # Generate visualization images if scan state is cached
        images: list[bytes] = []
        scan_state = self._scans.get(wall_id)
        if scan_state is not None:
            for route in routes:
                route_img = draw_routes_overlay(scan_state, [route])
                _, png_data = cv2.imencode(".png", route_img)
                images.append(png_data.tobytes())

        return routes, images
