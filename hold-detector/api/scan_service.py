from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from api.ply_service import compute_depth, load_point_cloud, pixel_to_3d, render_point_cloud
from api.schemas import BBox, Hold, Position3D
from hold_detector.app import HoldDetectionApp
from hold_detector.models import DetectionRecord


# ---------------------------------------------------------------------------
# Scan state
# ---------------------------------------------------------------------------

@dataclass
class ScanState:
    scan_id: str
    scan_dir: Path
    ply_path: Path
    png_path: Path | None = None
    # Populated by process_scan()
    pcd: Any | None = None
    cam_params: Any | None = None
    rendered_image: np.ndarray | None = None
    photo: np.ndarray | None = None
    records: list[DetectionRecord] | None = None
    holds: list[Hold] | None = None


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

def process_scan(state: ScanState, hold_app: HoldDetectionApp) -> None:
    """Load PLY, render, load PNG, detect holds, compute 3D positions and depth.

    Results are cached on state so subsequent GET requests are instant.
    """
    pcd = load_point_cloud(state.ply_path)
    rendered, cam_params = render_point_cloud(pcd)
    state.pcd = pcd
    state.cam_params = cam_params
    state.rendered_image = rendered

    if state.png_path is not None:
        photo = cv2.imread(str(state.png_path))
        if photo is not None and photo.shape[:2] != rendered.shape[:2]:
            h, w = rendered.shape[:2]
            photo = cv2.resize(photo, (w, h))
        state.photo = photo if photo is not None else rendered
    else:
        state.photo = rendered

    records = hold_app.detect(state.scan_id, state.photo)
    state.records = records

    holds: list[Hold] = []
    for record in records:
        cx, cy = record.mask_centroid
        pos_3d = pixel_to_3d(cx, cy, pcd, cam_params)

        position = (
            Position3D(x=float(pos_3d[0]), y=float(pos_3d[1]), z=float(pos_3d[2]))
            if pos_3d is not None
            else Position3D(x=0.0, y=0.0, z=0.0)
        )
        depth = compute_depth(tuple(record.bbox_xyxy), pcd, cam_params)

        x1, y1, x2, y2 = record.bbox_xyxy
        holds.append(Hold(
            id=record.instance_id,
            position=position,
            bbox=BBox(x1=x1, y1=y1, x2=x2, y2=y2),
            confidence=record.score,
            depth=depth,
        ))

    state.holds = holds


def ensure_processed(state: ScanState, hold_app: HoldDetectionApp) -> None:
    """Run process_scan lazily if not already done."""
    if state.holds is None:
        process_scan(state, hold_app)


# ---------------------------------------------------------------------------
# Debug overlay
# ---------------------------------------------------------------------------

def draw_debug_overlay(state: ScanState) -> np.ndarray:
    """Draw bounding boxes, hold IDs, and depths on the photo."""
    canvas = state.photo.copy()
    for hold, record in zip(state.holds, state.records):
        x1 = int(hold.bbox.x1)
        y1 = int(hold.bbox.y1)
        x2 = int(hold.bbox.x2)
        y2 = int(hold.bbox.y2)
        cx, cy = record.mask_centroid

        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 255, 0), 2)

        label = f"{hold.id} ({hold.depth:.3f}m)"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(canvas, (cx - 2, cy - th - 4), (cx + tw + 2, cy + 2), (0, 255, 0), -1)
        cv2.putText(canvas, label, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

    return canvas
