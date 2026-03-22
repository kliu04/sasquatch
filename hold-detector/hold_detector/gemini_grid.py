from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from hold_detector.geometry import clamp_box
from hold_detector.models import DetectionRecord


class GeminiGridBuilder:
    def __init__(self, grid_size: int) -> None:
        self.grid_size = grid_size

    def build_crop(
        self,
        image_bgr: np.ndarray,
        record: DetectionRecord,
        crop_dir: Path | None,
    ) -> np.ndarray:
        context_crop = self._build_context_crop(image_bgr, record.bbox_xyxy)
        if crop_dir is not None:
            crop_dir.mkdir(parents=True, exist_ok=True)
            context_path = crop_dir / f"{record.instance_id:03d}_context.jpg"
            cv2.imwrite(str(context_path), context_crop)
            record.crop_paths = {"context": str(context_path)}
        return context_crop

    def build_grid(self, records: list[DetectionRecord], context_crops: list[np.ndarray], tile_size: int = 224) -> np.ndarray:
        grid = np.full(
            (self.grid_size * tile_size, self.grid_size * tile_size, 3),
            248,
            dtype=np.uint8,
        )
        total_cells = self.grid_size ** 2
        for cell_index in range(total_cells):
            row = cell_index // self.grid_size
            col = cell_index % self.grid_size
            y1 = row * tile_size
            x1 = col * tile_size
            if cell_index < len(records):
                tile = self._prepare_tile(context_crops[cell_index], records[cell_index].instance_id, tile_size)
            else:
                tile = np.full((tile_size, tile_size, 3), 245, dtype=np.uint8)
                cv2.putText(tile, "empty", (70, 112), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (150, 150, 150), 1, cv2.LINE_AA)
            grid[y1:y1 + tile_size, x1:x1 + tile_size] = tile
        return grid

    def build_contents(self, records: list[DetectionRecord], grid_bytes: bytes, types: Any) -> list[Any]:
        grid_positions = []
        for index, record in enumerate(records):
            row = (index // self.grid_size) + 1
            col = (index % self.grid_size) + 1
            grid_positions.append(
                f"- row {row}, col {col}, instance_id {record.instance_id}, "
                f"detector_score {record.score}, bbox {record.bbox_xyxy}"
            )
        prompt_lines = [
            "You are classifying multiple climbing wall detector candidates in one batch.",
            f"The image is a {self.grid_size}x{self.grid_size} grid of hold crops with surrounding wall context.",
            "Each occupied tile has a black header showing its instance_id.",
            "Return exactly one JSON object per candidate, with the same instance_id.",
            "Do not omit candidates and do not invent instance_ids.",
            "Candidates in this grid:",
            *grid_positions,
        ]
        return [
            "\n".join(prompt_lines),
            types.Part.from_bytes(data=grid_bytes, mime_type="image/png"),
        ]

    def build_single_contents(self, crop_bytes: bytes, mime_type: str, types: Any) -> list[Any]:
        return [types.Part.from_bytes(data=crop_bytes, mime_type=mime_type)]

    def encode_image(self, image_bgr: np.ndarray, extension: str) -> bytes:
        ok, buffer = cv2.imencode(extension, image_bgr)
        if not ok:
            raise RuntimeError(f"OpenCV failed to encode image as {extension}")
        return buffer.tobytes()

    def _build_context_crop(
        self,
        image_bgr: np.ndarray,
        box: list[float],
    ) -> np.ndarray:
        height, width = image_bgr.shape[:2]
        x1, y1, x2, y2 = clamp_box(box, width, height)
        bbox_w = x2 - x1
        bbox_h = y2 - y1
        pad = max(20, int(max(bbox_w, bbox_h) * 0.25))
        cx1 = max(0, x1 - pad)
        cy1 = max(0, y1 - pad)
        cx2 = min(width, x2 + pad)
        cy2 = min(height, y2 + pad)
        return image_bgr[cy1:cy2, cx1:cx2].copy()

    def _prepare_tile(
        self,
        crop_bgr: np.ndarray,
        instance_id: int,
        tile_size: int,
        label_height: int = 28,
        padding: int = 10,
    ) -> np.ndarray:
        tile = np.full((tile_size, tile_size, 3), 242, dtype=np.uint8)
        cv2.rectangle(tile, (0, 0), (tile_size - 1, tile_size - 1), (210, 210, 210), 1)
        cv2.rectangle(tile, (0, 0), (tile_size - 1, label_height), (20, 20, 20), -1)
        cv2.putText(tile, f"id {instance_id}", (8, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

        usable = tile_size - label_height - (padding * 2)
        crop_h, crop_w = crop_bgr.shape[:2]
        scale = min(usable / max(crop_w, 1), usable / max(crop_h, 1), 1.0)
        resized_w = max(1, int(round(crop_w * scale)))
        resized_h = max(1, int(round(crop_h * scale)))
        resized = cv2.resize(crop_bgr, (resized_w, resized_h), interpolation=cv2.INTER_AREA)

        x = (tile_size - resized_w) // 2
        y = label_height + padding + ((usable - resized_h) // 2)
        tile[y:y + resized_h, x:x + resized_w] = resized
        return tile
