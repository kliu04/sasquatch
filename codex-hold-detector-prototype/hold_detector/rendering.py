from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from detectron2.data import MetadataCatalog
from detectron2.structures import Instances
from detectron2.utils.visualizer import ColorMode, Visualizer

from hold_detector.constants import CLASS_NAMES, TYPE_COLORS_BGR
from hold_detector.models import DetectionRecord
from hold_detector.postprocess import clamp_box


class OverlayRenderer:
    def save_raw_detectron(self, image_bgr: np.ndarray, instances: Instances, output_path: Path) -> None:
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        metadata = MetadataCatalog.get("archived_hold_model")
        metadata.thing_classes = CLASS_NAMES
        visualizer = Visualizer(rgb, metadata=metadata, scale=1.0, instance_mode=ColorMode.IMAGE)
        rendered = visualizer.draw_instance_predictions(instances.to("cpu")).get_image()
        cv2.imwrite(str(output_path), cv2.cvtColor(rendered, cv2.COLOR_RGB2BGR))

    def save_instance_ids(
        self,
        image_bgr: np.ndarray,
        records: list[DetectionRecord],
        masks: list[np.ndarray],
        output_path: Path,
    ) -> None:
        base = image_bgr.copy()
        overlay = image_bgr.copy()
        color = (0, 215, 255)
        for record, mask in zip(records, masks):
            overlay[mask] = (
                0.7 * overlay[mask].astype(np.float32) + 0.3 * np.array(color, dtype=np.float32)
            ).astype(np.uint8)
            contours, _ = cv2.findContours((mask.astype(np.uint8) * 255), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(base, contours, -1, color, 2)
            cx, cy = record.mask_centroid
            self._draw_label(base, f"id {record.instance_id}", (int(cx), int(cy)), color)
        cv2.imwrite(str(output_path), cv2.addWeighted(overlay, 0.45, base, 0.55, 0))

    def save_classified(
        self,
        image_bgr: np.ndarray,
        records: list[DetectionRecord],
        masks: list[np.ndarray],
        output_path: Path,
        include_not_hold: bool,
    ) -> None:
        base = image_bgr.copy()
        overlay = image_bgr.copy()
        for record, mask in zip(records, masks):
            if record.type == "not-hold" and not include_not_hold:
                continue
            if record.type is None and not include_not_hold:
                continue
            color = TYPE_COLORS_BGR.get(str(record.type), TYPE_COLORS_BGR["unclassified"])
            overlay[mask] = (
                0.65 * overlay[mask].astype(np.float32) + 0.35 * np.array(color, dtype=np.float32)
            ).astype(np.uint8)
            contours, _ = cv2.findContours((mask.astype(np.uint8) * 255), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(base, contours, -1, color, 2)
            x1, y1, _, _ = clamp_box(record.bbox_xyxy, image_bgr.shape[1], image_bgr.shape[0])
            label = record.type or "unclassified"
            if record.confidence is not None:
                label = f"{label} {record.confidence:.2f}"
            self._draw_label(base, label, (x1, max(18, y1)), color)
        cv2.imwrite(str(output_path), cv2.addWeighted(overlay, 0.45, base, 0.55, 0))

    def _draw_label(self, image: np.ndarray, text: str, origin: tuple[int, int], color: tuple[int, int, int]) -> None:
        font = cv2.FONT_HERSHEY_SIMPLEX
        max_dim = max(image.shape[0], image.shape[1])
        scale = min(1.5, max(0.7, max_dim / 2400))
        thickness = 2 if scale >= 0.9 else 1
        text_size, baseline = cv2.getTextSize(text, font, scale, thickness)
        x = max(0, origin[0])
        padding_x = max(6, int(round(scale * 6)))
        padding_y = max(5, int(round(scale * 5)))
        y = max(text_size[1] + padding_y, origin[1])
        cv2.rectangle(
            image,
            (x, y - text_size[1] - baseline - (padding_y * 2)),
            (x + text_size[0] + (padding_x * 2), y + padding_y),
            color,
            -1,
        )
        cv2.putText(
            image,
            text,
            (x + padding_x, y - padding_y),
            font,
            scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )
