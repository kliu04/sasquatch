from __future__ import annotations

from pydantic import BaseModel


class ScanResponse(BaseModel):
    scan_id: str
    status: str
    frame_count: int


class ScanStatusResponse(BaseModel):
    scan_id: str
    status: str
    error: str | None = None


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
    depth: float = 0.0
    hold_type: str | None = None


class HoldsResponse(BaseModel):
    scan_id: str
    holds: list[Hold]


class Route(BaseModel):
    holds: list[int]


class RoutesResponse(BaseModel):
    scan_id: str
    difficulty: str
    style: str
    routes: list[Route]
