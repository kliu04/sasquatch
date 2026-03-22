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
    """Highlight detected holds with white masks on a dimmed photo."""
    canvas = (state.photo.copy() * 0.35).astype(np.uint8)
    overlay = canvas.copy()
    color = (255, 255, 255)

    if state.masks is not None:
        for mask in state.masks:
            overlay[mask] = color
            contours, _ = cv2.findContours(
                mask.astype(np.uint8) * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            cv2.drawContours(canvas, contours, -1, color, 2)

    cv2.addWeighted(overlay, 0.5, canvas, 0.5, 0, canvas)
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


def _classify_route_holds(
    route: list[int],
    hold_map: dict[int, Hold],
) -> tuple[int | None, set[int], set[int], set[int]]:
    """Classify route holds by vertical position.

    Returns (end_hold_id, foot_hold_ids, start_hand_ids, regular_hold_ids).
    - End hold: highest on wall (smallest y) — finish target.
    - Foot holds: bottom 2 — starting feet.
    - Start hands: next 2 from bottom — starting hand positions.
    - Regular: everything else.
    """
    if not route:
        return None, set(), set(), set()

    scored = []
    for hid in route:
        hold = hold_map.get(hid)
        if hold is None:
            continue
        cy = (hold.bbox.y1 + hold.bbox.y2) / 2
        scored.append((hid, cy))

    scored.sort(key=lambda x: x[1])  # ascending y = top to bottom

    end_id = scored[0][0]
    foot_ids = set()
    start_hand_ids = set()

    if len(scored) >= 5:
        foot_ids = {s[0] for s in scored[-2:]}
        start_hand_ids = {s[0] for s in scored[-4:-2]}
    elif len(scored) >= 3:
        foot_ids = {s[0] for s in scored[-2:]}

    regular_ids = {s[0] for s in scored} - {end_id} - foot_ids - start_hand_ids
    return end_id, foot_ids, start_hand_ids, regular_ids


def _draw_hold_mask(
    canvas: np.ndarray,
    overlay: np.ndarray,
    hid: int,
    hold_map: dict[int, Hold],
    mask_by_id: dict[int, np.ndarray],
    fill_color: tuple[int, int, int],
    outline_color: tuple[int, int, int],
) -> None:
    """Draw a single hold with mask fill and outline."""
    if hid in mask_by_id:
        mask = mask_by_id[hid]
        overlay[mask] = fill_color
        contours, _ = cv2.findContours(
            mask.astype(np.uint8) * 255,
            cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
        )
        cv2.drawContours(canvas, contours, -1, outline_color, 2)
    else:
        hold = hold_map.get(hid)
        if hold:
            cx = int((hold.bbox.x1 + hold.bbox.x2) / 2)
            cy = int((hold.bbox.y1 + hold.bbox.y2) / 2)
            r = max(int((hold.bbox.x2 - hold.bbox.x1) / 2), 8)
            cv2.circle(overlay, (cx, cy), r, fill_color, -1)
            cv2.circle(canvas, (cx, cy), r, outline_color, 2)


_COLOR_GREEN = (0, 255, 0)      # end hold (finish)
_COLOR_BLUE = (255, 180, 0)     # foot holds (start) — BGR light blue
_COLOR_WHITE = (255, 255, 255)
_COLOR_ROUTE = (0, 100, 255)    # regular route holds — orange


def draw_routes_overlay(
    state: ScanState,
    routes: list[list[int]],
) -> np.ndarray:
    """Draw routes on a dimmed photo with color-coded hold types.

    - Green: end/finish hold (highest on wall)
    - Blue: starting foot holds (bottom 2)
    - White outline: starting hand holds (next 2 up)
    - Orange: regular route holds
    """
    canvas = (state.photo.copy() * 0.35).astype(np.uint8)

    mask_by_id: dict[int, np.ndarray] = {}
    if state.masks is not None and state.records is not None:
        for record, mask in zip(state.records, state.masks):
            mask_by_id[record.instance_id] = mask

    hold_map = {h.id: h for h in state.holds}

    overlay = canvas.copy()
    for route in routes:
        end_id, foot_ids, start_hand_ids, regular_ids = _classify_route_holds(route, hold_map)

        # End hold — green
        if end_id is not None:
            _draw_hold_mask(canvas, overlay, end_id, hold_map, mask_by_id, _COLOR_GREEN, _COLOR_GREEN)

        # Foot holds — blue
        for hid in foot_ids:
            _draw_hold_mask(canvas, overlay, hid, hold_map, mask_by_id, _COLOR_BLUE, _COLOR_BLUE)

        # Starting hand holds — white outline
        for hid in start_hand_ids:
            _draw_hold_mask(canvas, overlay, hid, hold_map, mask_by_id, _COLOR_WHITE, _COLOR_WHITE)

        # Regular holds — orange with white outline
        for hid in regular_ids:
            _draw_hold_mask(canvas, overlay, hid, hold_map, mask_by_id, _COLOR_ROUTE, _COLOR_WHITE)

    # Blend (60% overlay preserves mask colors while showing photo through)
    canvas = cv2.addWeighted(overlay, 0.6, canvas, 0.4, 0)

    # Legend
    lx, ly = 10, 20
    for ri, route in enumerate(routes):
        label = f"Route {ri + 1} ({len(route)} holds)"
        cv2.rectangle(canvas, (lx, ly - 10), (lx + 14, ly + 4), _COLOR_ROUTE, -1)
        cv2.putText(canvas, label, (lx + 20, ly + 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, _COLOR_WHITE, 1, cv2.LINE_AA)
        ly += 22

    return canvas
