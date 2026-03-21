from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(slots=True)
class TapeAnalysis:
    instance_id: int
    score: float
    aspect_ratio: float
    fill_ratio: float
    color_std: float
    approx_vertices: int
    minrect_fill_ratio: float
    mask_area_px: int
    is_tape: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "score": round(self.score, 4),
            "aspect_ratio": round(self.aspect_ratio, 3),
            "fill_ratio": round(self.fill_ratio, 3),
            "color_std": round(self.color_std, 3),
            "approx_vertices": self.approx_vertices,
            "minrect_fill_ratio": round(self.minrect_fill_ratio, 3),
            "mask_area_px": self.mask_area_px,
            "is_tape": self.is_tape,
        }


@dataclass(slots=True)
class DuplicateRemoval:
    kept_instance_id: int
    removed_instance_id: int
    kept_score: float
    removed_score: float
    kept_is_tape: bool
    box_overlap_smaller: float
    mask_overlap_smaller: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "kept_instance_id": self.kept_instance_id,
            "removed_instance_id": self.removed_instance_id,
            "kept_score": round(self.kept_score, 4),
            "removed_score": round(self.removed_score, 4),
            "kept_is_tape": self.kept_is_tape,
            "box_overlap_smaller": round(self.box_overlap_smaller, 3),
            "mask_overlap_smaller": round(self.mask_overlap_smaller, 3),
        }


@dataclass(slots=True)
class DetectionRecord:
    instance_id: int
    class_id: int
    class_name: str
    score: float
    bbox_xyxy: list[float]
    mask_area_px: int
    mask_centroid: list[int]
    tape_like: bool
    type: str | None = None
    color: str | None = None
    confidence: float | None = None
    classification_status: str | None = None
    classification_attempts: int | None = None
    classification_error: str | None = None
    crop_paths: dict[str, str] | None = None

    def copy(self) -> "DetectionRecord":
        return replace(self)

    def apply_classification(
        self,
        *,
        hold_type: str,
        color: str | None = None,
        confidence: float | None = None,
        attempts: int,
    ) -> "DetectionRecord":
        updated = self.copy()
        updated.type = hold_type
        updated.color = color
        updated.confidence = round(confidence, 4) if confidence is not None else None
        updated.classification_status = "ok"
        updated.classification_attempts = attempts
        return updated

    def mark_failed(self, error: str, attempts: int) -> "DetectionRecord":
        updated = self.copy()
        updated.classification_status = "failed"
        updated.classification_attempts = attempts
        updated.classification_error = error
        return updated

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "instance_id": self.instance_id,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "score": round(self.score, 4),
            "bbox_xyxy": self.bbox_xyxy,
            "mask_area_px": self.mask_area_px,
            "mask_centroid": self.mask_centroid,
            "tape_like": self.tape_like,
        }
        if self.type is not None:
            payload["type"] = self.type
        if self.color is not None:
            payload["color"] = self.color
        if self.confidence is not None:
            payload["confidence"] = round(self.confidence, 4)
        if self.classification_status is not None:
            payload["classification_status"] = self.classification_status
        if self.classification_attempts is not None:
            payload["classification_attempts"] = self.classification_attempts
        if self.classification_error is not None:
            payload["classification_error"] = self.classification_error
        if self.crop_paths is not None:
            payload["crop_paths"] = self.crop_paths
        return payload


@dataclass(slots=True)
class ProcessedDetections:
    instances: Any
    records: list[DetectionRecord]
    masks: list[Any]
    deduped_count: int
    removed_duplicates: list[DuplicateRemoval] = field(default_factory=list)
    removed_tape: list[TapeAnalysis] = field(default_factory=list)
