"""
Standalone visualization helper for iterating on route generation.

Usage:
    python visualize.py 3d-data/scan_1774130092.ply 3d-data/scan_1774130092.png
    python visualize.py  # uses default files
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2

from api.main import SasquatchEngine

DEFAULT_PLY = "3d-data/scan_1774130092.ply"
DEFAULT_PNG = "3d-data/scan_1774130092.png"

COMBOS = [
    ("easy", "dynamic"),
    ("easy", "static"),
    ("medium", "dynamic"),
    ("medium", "static"),
    ("hard", "dynamic"),
    ("hard", "static"),
]

TOP_K = 15


def main() -> None:
    ply = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLY
    png = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PNG

    print(f"Loading engine...")
    engine = SasquatchEngine()

    print(f"Processing {ply} + {png}...")
    scan = engine.create_scan(ply, png)

    holds = scan.get_holds()
    print(f"Detected {len(holds)} holds")

    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)

    for difficulty, style in COMBOS:
        routes = scan.get_routes(difficulty=difficulty, style=style, top_k=TOP_K)
        tag = f"{difficulty}_{style}"

        if not routes:
            print(f"  {tag}: no routes found")
            continue

        print(f"  {tag}: {len(routes)} routes")
        for i, route in enumerate(routes):
            hold_map = {h.id: h for h in holds}
            start = hold_map.get(route[0])
            end = hold_map.get(route[-1])
            sy = int((start.bbox.y1 + start.bbox.y2) / 2) if start else -1
            ey = int((end.bbox.y1 + end.bbox.y2) / 2) if end else -1
            sx = int((start.bbox.x1 + start.bbox.x2) / 2) if start else -1
            print(f"    Route {i+1}: {len(route)} holds, start=({sx},{sy}) end_y={ey}px")

        # Save each route as a separate image
        from api.scan_service import draw_routes_overlay
        for i, route in enumerate(routes):
            img = draw_routes_overlay(scan._state, [route])
            path = out_dir / f"route_{tag}_{i+1}.png"
            cv2.imwrite(str(path), img)
            print(f"    Saved {path}")

    # Also save holds debug
    holds_img = scan.debug_holds_image()
    holds_path = out_dir / "debug_holds.png"
    cv2.imwrite(str(holds_path), holds_img)
    print(f"Saved {holds_path}")


if __name__ == "__main__":
    main()
