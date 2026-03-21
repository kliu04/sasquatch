from __future__ import annotations

from pydantic import BaseModel


class ScanResponse(BaseModel):
    scan_id: str
    frame_count: int


class Position3D(BaseModel):
    x: float
    y: float
    z: float


class BBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class Hold(BaseModel):
    id: int
    position: Position3D
    bbox: BBox
    confidence: float
    hold_type: str | None = None


class HoldsResponse(BaseModel):
    scan_id: str
    holds: list[Hold]
