from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from detectron2.structures import Instances

from hold_detector.config import DedupeConfig, TapeFilterConfig
from hold_detector.constants import CLASS_NAMES
from hold_detector.geometry import (
    clamp_box,
    contour_metrics,
    intersection_over_smaller_box,
    intersection_over_smaller_mask,
    mask_centroid,
)
from hold_detector.models import DetectionRecord, DuplicateRemoval, ProcessedDetections, TapeAnalysis


class PostProcessor:
    def __init__(self, tape_filter: TapeFilterConfig, dedupe: DedupeConfig) -> None:
        self.tape_filter = tape_filter
        self.dedupe = dedupe

    def process(self, instances: Instances, image_bgr: np.ndarray) -> ProcessedDetections:
        tape_details = self._analyze_tape_like(instances, image_bgr)
        removed_duplicates: list[DuplicateRemoval] = []
        if self.dedupe.enabled:
            instances, tape_details, removed_duplicates = self._dedupe(instances, tape_details)
        deduped_count = len(instances)
        removed_tape: list[TapeAnalysis] = []
        if self.tape_filter.enabled:
            instances, tape_details, removed_tape = self._filter_tape(instances, tape_details)
        records, masks = self._build_records(instances, tape_details)
        return ProcessedDetections(
            instances=instances,
            records=records,
            masks=masks,
            deduped_count=deduped_count,
            removed_duplicates=removed_duplicates,
            removed_tape=removed_tape,
        )

    def _analyze_tape_like(self, instances: Instances, image_bgr: np.ndarray) -> list[TapeAnalysis]:
        if len(instances) == 0 or not instances.has("pred_masks"):
            return []
        boxes = instances.pred_boxes.tensor.tolist()
        masks = instances.pred_masks.numpy().astype(bool)
        scores = instances.scores.tolist()
        return [
            self._analyze_one(image_bgr, idx, float(scores[idx]), box, mask)
            for idx, (box, mask) in enumerate(zip(boxes, masks))
        ]

    def _analyze_one(
        self,
        image_bgr: np.ndarray,
        instance_id: int,
        score: float,
        box: list[float],
        mask: np.ndarray,
    ) -> TapeAnalysis:
        height, width = image_bgr.shape[:2]
        x1, y1, x2, y2 = clamp_box(box, width, height)
        bbox_w = max(1, x2 - x1)
        bbox_h = max(1, y2 - y1)
        bbox_area = bbox_w * bbox_h
        aspect_ratio = max(bbox_w / bbox_h, bbox_h / bbox_w)
        local_mask = mask[y1:y2, x1:x2]
        area = int(local_mask.sum())
        fill_ratio = area / bbox_area if bbox_area else 0.0
        pixels = image_bgr[y1:y2, x1:x2][local_mask]
        color_std = float(pixels.astype(np.float32).std(axis=0).mean()) if len(pixels) else 999.0
        approx_vertices, minrect_fill_ratio = contour_metrics(local_mask)
        is_tape = (
            color_std <= self.tape_filter.uniformity_std
            and fill_ratio >= self.tape_filter.min_fill
            and aspect_ratio >= self.tape_filter.min_aspect
            and approx_vertices <= self.tape_filter.max_vertices
            and minrect_fill_ratio >= self.tape_filter.min_minrect_fill
        )
        return TapeAnalysis(
            instance_id=instance_id,
            score=score,
            aspect_ratio=aspect_ratio,
            fill_ratio=fill_ratio,
            color_std=color_std,
            approx_vertices=approx_vertices,
            minrect_fill_ratio=minrect_fill_ratio,
            mask_area_px=area,
            is_tape=is_tape,
        )

    def _dedupe(
        self,
        instances: Instances,
        tape_details: list[TapeAnalysis],
    ) -> tuple[Instances, list[TapeAnalysis], list[DuplicateRemoval]]:
        if len(instances) <= 1:
            return instances, tape_details, []
        boxes = instances.pred_boxes.tensor.tolist()
        masks = instances.pred_masks.numpy().astype(bool)
        scores = instances.scores.tolist()
        classes = instances.pred_classes.tolist()
        image_shape = masks[0].shape
        order = sorted(range(len(instances)), key=lambda idx: float(scores[idx]), reverse=True)
        keep_indices: list[int] = []
        suppressed: set[int] = set()
        removed: list[DuplicateRemoval] = []

        for position, idx in enumerate(order):
            if idx in suppressed:
                continue
            keep_indices.append(idx)
            for other_idx in order[position + 1:]:
                if other_idx in suppressed:
                    continue
                if int(classes[idx]) != int(classes[other_idx]):
                    continue
                if tape_details[idx].is_tape != tape_details[other_idx].is_tape:
                    continue
                box_overlap = intersection_over_smaller_box(boxes[idx], boxes[other_idx])
                if box_overlap <= 0:
                    continue
                mask_overlap = intersection_over_smaller_mask(
                    masks[idx],
                    masks[other_idx],
                    boxes[idx],
                    boxes[other_idx],
                    image_shape,
                )
                if (
                    mask_overlap >= self.dedupe.mask_overlap_threshold
                    or box_overlap >= self.dedupe.box_overlap_threshold
                ):
                    suppressed.add(other_idx)
                    removed.append(
                        DuplicateRemoval(
                            kept_instance_id=idx,
                            removed_instance_id=other_idx,
                            kept_score=float(scores[idx]),
                            removed_score=float(scores[other_idx]),
                            kept_is_tape=tape_details[idx].is_tape,
                            box_overlap_smaller=box_overlap,
                            mask_overlap_smaller=mask_overlap,
                        )
                    )

        keep_indices.sort()
        return instances[keep_indices], [tape_details[index] for index in keep_indices], removed

    def _filter_tape(
        self,
        instances: Instances,
        tape_details: list[TapeAnalysis],
    ) -> tuple[Instances, list[TapeAnalysis], list[TapeAnalysis]]:
        if len(instances) == 0:
            return instances, tape_details, []
        keep_indices = [idx for idx, detail in enumerate(tape_details) if not detail.is_tape]
        removed = [detail for detail in tape_details if detail.is_tape]
        return instances[keep_indices], [tape_details[idx] for idx in keep_indices], removed

    def _build_records(
        self,
        instances: Instances,
        tape_details: list[TapeAnalysis],
    ) -> tuple[list[DetectionRecord], list[np.ndarray]]:
        boxes = instances.pred_boxes.tensor.tolist() if instances.has("pred_boxes") else []
        scores = instances.scores.tolist() if instances.has("scores") else []
        classes = instances.pred_classes.tolist() if instances.has("pred_classes") else []
        masks = instances.pred_masks.numpy().astype(bool) if instances.has("pred_masks") else None
        if masks is None:
            raise RuntimeError("Detectron outputs do not include masks, but this pipeline requires masks.")

        records: list[DetectionRecord] = []
        mask_arrays: list[np.ndarray] = []
        for idx, box in enumerate(boxes):
            class_id = int(classes[idx])
            label = CLASS_NAMES[class_id] if class_id < len(CLASS_NAMES) else str(class_id)
            mask = masks[idx]
            cx, cy = mask_centroid(mask, box)
            records.append(
                DetectionRecord(
                    instance_id=idx,
                    class_id=class_id,
                    class_name=label,
                    score=round(float(scores[idx]), 4),
                    bbox_xyxy=[round(float(value), 1) for value in box],
                    mask_area_px=int(mask.sum()),
                    mask_centroid=[cx, cy],
                    tape_like=tape_details[idx].is_tape if tape_details else False,
                )
            )
            mask_arrays.append(mask)
        return records, mask_arrays

    def build_summary(self, processed: ProcessedDetections) -> dict[str, Any]:
        return {
            "kept": len(processed.records),
            "removed_duplicates": len(processed.removed_duplicates),
            "removed_tape": len(processed.removed_tape),
            "dedupe_heuristic": {
                "enabled": self.dedupe.enabled,
                "mask_overlap_smaller_min": self.dedupe.mask_overlap_threshold,
                "box_overlap_smaller_min": self.dedupe.box_overlap_threshold,
                "tape_and_hold_are_grouped_separately": True,
            },
            "tape_heuristic": {
                "uniformity_std_max": self.tape_filter.uniformity_std,
                "fill_ratio_min": self.tape_filter.min_fill,
                "aspect_ratio_min": self.tape_filter.min_aspect,
                "approx_vertices_max": self.tape_filter.max_vertices,
                "minrect_fill_ratio_min": self.tape_filter.min_minrect_fill,
            },
            "dedupe_examples": [item.to_dict() for item in processed.removed_duplicates[:25]],
            "removed_examples": [item.to_dict() for item in processed.removed_tape[:25]],
        }
