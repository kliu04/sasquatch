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
    # "processing" | "ready" | "error"
    status: str = "processing"
    error: str | None = None
    # Populated by process_scan()
    pcd: Any | None = None
    cam_params: Any | None = None
    rendered_image: np.ndarray | None = None
    photo: np.ndarray | None = None
    records: list[DetectionRecord] | None = None
    masks: list[np.ndarray] | None = None
    holds: list[Hold] | None = None


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

def prepare_scan(state: ScanState) -> None:
    """Phase 1 (main thread): Load PLY and render via Open3D.

    Open3D's Visualizer requires the main thread for OpenGL on macOS,
    so this must NOT run inside asyncio.to_thread().
    """
    import time

    t0 = time.perf_counter()
    print(f"[scan {state.scan_id}] loading PLY...", flush=True)
    pcd = load_point_cloud(state.ply_path)
    t1 = time.perf_counter()
    print(f"[scan {state.scan_id}] PLY loaded in {t1 - t0:.1f}s", flush=True)

    print(f"[scan {state.scan_id}] rendering point cloud...", flush=True)
    rendered, cam_params = render_point_cloud(pcd)
    t2 = time.perf_counter()
    print(f"[scan {state.scan_id}] rendered in {t2 - t1:.1f}s", flush=True)

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


def process_scan(state: ScanState, hold_app: HoldDetectionApp) -> None:
    """Phase 2 (background thread): Detect holds, compute 3D positions and depth.

    Sets state.status to "ready" on success or "error" on failure.
    Called from main.py via asyncio.to_thread() after prepare_scan() completes.
    """
    import time

    try:
        t0 = time.perf_counter()
        print(f"[scan {state.scan_id}] starting hold detection...", flush=True)
        records, masks = hold_app.detect(state.scan_id, state.photo)
        t1 = time.perf_counter()
        print(f"[scan {state.scan_id}] detection done in {t1 - t0:.1f}s — {len(records)} holds", flush=True)
        state.records = records
        state.masks = masks

        print(f"[scan {state.scan_id}] computing 3D positions for {len(records)} holds...", flush=True)
        holds: list[Hold] = []
        for record in records:
            cx, cy = record.mask_centroid
            pos_3d = pixel_to_3d(cx, cy, state.pcd, state.cam_params)

            position = (
                Position3D(x=float(pos_3d[0]), y=float(pos_3d[1]), z=float(pos_3d[2]))
                if pos_3d is not None
                else Position3D(x=0.0, y=0.0, z=0.0)
            )
            depth = compute_depth(tuple(record.bbox_xyxy), state.pcd, state.cam_params)

            x1, y1, x2, y2 = record.bbox_xyxy
            holds.append(Hold(
                id=record.instance_id,
                position=position,
                bbox=BBox(x1=x1, y1=y1, x2=x2, y2=y2),
                confidence=record.score,
                depth=depth,
            ))

        t2 = time.perf_counter()
        print(f"[scan {state.scan_id}] 3D positions done in {t2 - t1:.1f}s", flush=True)
        print(f"[scan {state.scan_id}] total processing: {t2 - t0:.1f}s", flush=True)
        state.holds = holds
        state.status = "ready"
    except Exception as exc:
        state.status = "error"
        state.error = str(exc)
        raise


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


_ROUTE_COLORS = [
    (0, 100, 255),   # orange-red
    (0, 220, 0),     # green
    (255, 80, 0),    # blue
    (0, 255, 255),   # yellow
    (255, 0, 255),   # magenta
    (255, 255, 0),   # cyan
    (0, 165, 255),   # orange
    (128, 0, 128),   # purple
    (0, 128, 255),   # dark orange
    (180, 105, 255), # hot pink
    (0, 200, 200),   # dark yellow
    (255, 0, 128),   # blue-violet
    (50, 205, 50),   # lime green
    (0, 69, 255),    # red-orange
    (203, 192, 255), # pink
]


def draw_routes_overlay(
    state: ScanState,
    routes: list[list[int]],
) -> np.ndarray:
    """Draw routes by coloring hold masks (filled shapes) on the photo."""
    canvas = state.photo.copy()

    # Build mapping from hold ID to mask index
    # records and masks are parallel arrays; hold.id == record.instance_id
    mask_by_id: dict[int, np.ndarray] = {}
    if state.masks is not None and state.records is not None:
        for record, mask in zip(state.records, state.masks):
            mask_by_id[record.instance_id] = mask

    hold_map = {h.id: h for h in state.holds}

    # Draw non-route holds as faint white outlines
    route_hold_ids: set[int] = set()
    for route in routes:
        route_hold_ids.update(route)

    for hold in state.holds:
        if hold.id in route_hold_ids:
            continue
        if hold.id in mask_by_id:
            contours, _ = cv2.findContours(
                mask_by_id[hold.id].astype(np.uint8) * 255,
                cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
            )
            cv2.drawContours(canvas, contours, -1, (255, 255, 255), 1)
        else:
            cx = int((hold.bbox.x1 + hold.bbox.x2) / 2)
            cy = int((hold.bbox.y1 + hold.bbox.y2) / 2)
            cv2.circle(canvas, (cx, cy), 6, (255, 255, 255), 1)

    # Color route holds with their route color (semi-transparent fill + outline)
    overlay = canvas.copy()
    for ri, route in enumerate(routes):
        color = _ROUTE_COLORS[ri % len(_ROUTE_COLORS)]
        for hid in route:
            if hid not in mask_by_id:
                # Fallback: draw colored circle from bbox
                hold = hold_map.get(hid)
                if hold:
                    cx = int((hold.bbox.x1 + hold.bbox.x2) / 2)
                    cy = int((hold.bbox.y1 + hold.bbox.y2) / 2)
                    r = max(int((hold.bbox.x2 - hold.bbox.x1) / 2), 8)
                    cv2.circle(overlay, (cx, cy), r, color, -1)
                continue
            mask = mask_by_id[hid]
            # Fill mask area with route color
            overlay[mask] = color
            # Draw contour outline
            contours, _ = cv2.findContours(
                mask.astype(np.uint8) * 255,
                cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
            )
            cv2.drawContours(overlay, contours, -1, (0, 0, 0), 2)

    # Blend overlay with original (60% opacity for colored holds)
    alpha = 0.6
    canvas = cv2.addWeighted(overlay, alpha, canvas, 1 - alpha, 0)

    # Add route number labels on each hold
    for ri, route in enumerate(routes):
        color = _ROUTE_COLORS[ri % len(_ROUTE_COLORS)]
        for hid in route:
            hold = hold_map.get(hid)
            if hold is None:
                continue
            cx = int((hold.bbox.x1 + hold.bbox.x2) / 2)
            cy = int((hold.bbox.y1 + hold.bbox.y2) / 2)
            label = str(ri + 1)
            cv2.putText(canvas, label, (cx - 5, cy + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(canvas, label, (cx - 5, cy + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)

    # Legend
    lx, ly = 10, 20
    for ri, route in enumerate(routes):
        color = _ROUTE_COLORS[ri % len(_ROUTE_COLORS)]
        label = f"Route {ri + 1} ({len(route)} holds)"
        cv2.rectangle(canvas, (lx, ly - 10), (lx + 14, ly + 4), color, -1)
        cv2.putText(canvas, label, (lx + 20, ly + 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        ly += 22

    return canvas
