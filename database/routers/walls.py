"""Wall endpoints: create, upload, process, list, get, delete."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.auth import get_current_user
from database.db import get_db
from database.schema import User, Wall, WallStatus
from database.scan_worker import ScanWorker
from database.storage import GCSStorage

router = APIRouter(prefix="/walls", tags=["walls"])

# Injected at app startup
_storage: GCSStorage | None = None
_worker: ScanWorker | None = None


def configure(storage: GCSStorage, worker: ScanWorker) -> None:
    global _storage, _worker
    _storage = storage
    _worker = worker


# ── Schemas ──

class WallCreate(BaseModel):
    name: str
    has_ply: bool = True  # False for 2D-only (photo without LiDAR scan)


class WallCreateResponse(BaseModel):
    id: int
    name: str
    status: str
    ply_upload_url: str | None  # null when has_ply=false
    png_upload_url: str
    created_at: str | None = None


class WallSummary(BaseModel):
    id: int
    name: str
    status: str
    hold_count: int | None
    wall_img_url: str | None
    created_at: str | None = None


class WallDetail(BaseModel):
    id: int
    name: str
    status: str
    wall_img_url: str | None
    wall_ply_url: str | None
    holds_image_url: str | None
    hold_count: int | None
    error_message: str | None
    created_at: str | None = None


class ProcessResponse(BaseModel):
    wall_id: int
    status: str


class HoldPosition(BaseModel):
    x: float
    y: float
    z: float


class HoldBBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class HoldItem(BaseModel):
    id: int
    position: HoldPosition
    bbox: HoldBBox
    confidence: float
    depth: float


class HoldsResponse(BaseModel):
    wall_id: int
    holds: list[HoldItem]


# ── Helpers ──

def _get_user_wall(db: Session, user_id: int, wall_id: int) -> Wall:
    wall = db.query(Wall).filter(Wall.id == wall_id, Wall.user_id == user_id).first()
    if wall is None:
        raise HTTPException(404, "Wall not found")
    return wall


def _wall_summary(wall: Wall) -> WallSummary:
    return WallSummary(
        id=wall.id,
        name=wall.name,
        status=wall.status.name if wall.status else "pending_upload",
        hold_count=wall.hold_count,
        wall_img_url=_storage.signed_url_or_none(wall.wall_img_url),
        created_at=wall.created_at.isoformat() if wall.created_at else None,
    )


def _wall_detail(wall: Wall) -> WallDetail:
    return WallDetail(
        id=wall.id,
        name=wall.name,
        status=wall.status.name if wall.status else "pending_upload",
        wall_img_url=_storage.signed_url_or_none(wall.wall_img_url),
        wall_ply_url=_storage.signed_url_or_none(wall.wall_ply_url),
        holds_image_url=_storage.signed_url_or_none(wall.holds_image_url),
        hold_count=wall.hold_count,
        error_message=wall.error_message,
        created_at=wall.created_at.isoformat() if wall.created_at else None,
    )


# ── Endpoints ──

@router.post("", response_model=WallCreateResponse, status_code=201)
def create_wall(
    body: WallCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wall = Wall(
        user_id=user.id,
        name=body.name,
        status=WallStatus.pending_upload,
    )
    db.add(wall)
    db.commit()
    db.refresh(wall)

    png_gcs_path = f"walls/{wall.id}/photo.png"
    png_url = _storage.generate_upload_url(png_gcs_path, content_type="image/png")

    ply_url = None
    if body.has_ply:
        ply_gcs_path = f"walls/{wall.id}/scan.ply"
        ply_url = _storage.generate_upload_url(ply_gcs_path, content_type="application/octet-stream")
        wall.wall_ply_url = _storage.public_url(ply_gcs_path)
        db.commit()

    return WallCreateResponse(
        id=wall.id,
        name=wall.name,
        status=wall.status.name,
        ply_upload_url=ply_url,
        png_upload_url=png_url,
        created_at=wall.created_at.isoformat() if wall.created_at else None,
    )


@router.post("/{wall_id}/process", response_model=ProcessResponse, status_code=202)
async def process_wall(
    wall_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wall = _get_user_wall(db, user.id, wall_id)

    if wall.status not in (WallStatus.pending_upload, WallStatus.error):
        raise HTTPException(409, f"Wall is already {wall.status.name}")

    wall.status = WallStatus.processing
    wall.error_message = None
    db.commit()

    loop = asyncio.get_running_loop()
    _worker.start_processing(wall_id, loop)

    return ProcessResponse(wall_id=wall.id, status="processing")


@router.get("", response_model=list[WallSummary])
def list_walls(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    walls = db.query(Wall).filter(Wall.user_id == user.id).all()
    return [_wall_summary(w) for w in walls]


@router.get("/{wall_id}", response_model=WallDetail)
async def get_wall(
    wall_id: int,
    poll: bool = False,
    timeout: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wall = _get_user_wall(db, user.id, wall_id)

    if poll and wall.status == WallStatus.processing:
        # Long polling: wait for processing to complete
        timeout = min(timeout, 60)  # cap at 60s
        status = await _worker.wait_for_ready(wall_id, timeout=float(timeout))
        # Refresh wall from DB
        db.refresh(wall)

    return _wall_detail(wall)


class WallUpdate(BaseModel):
    name: str | None = None


@router.patch("/{wall_id}", response_model=WallDetail)
def update_wall(
    wall_id: int,
    body: WallUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wall = _get_user_wall(db, user.id, wall_id)
    if body.name is not None:
        wall.name = body.name
    db.commit()
    db.refresh(wall)
    return _wall_detail(wall)


@router.delete("/{wall_id}", status_code=204)
def delete_wall(
    wall_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wall = _get_user_wall(db, user.id, wall_id)

    # Delete GCS files
    try:
        _storage.delete_prefix(f"walls/{wall_id}/")
    except Exception:
        pass  # Best effort

    db.delete(wall)
    db.commit()


@router.get("/{wall_id}/holds", response_model=HoldsResponse)
def get_holds(
    wall_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wall = _get_user_wall(db, user.id, wall_id)

    if wall.status != WallStatus.ready:
        raise HTTPException(409, f"Wall is not ready (status: {wall.status.name})")

    import json
    try:
        holds_data = json.loads(wall.holds_json) if wall.holds_json else []
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(500, "Corrupted holds data")
    holds = [
        HoldItem(
            id=h["id"],
            position=HoldPosition(**h["position"]),
            bbox=HoldBBox(**h["bbox"]),
            confidence=h["confidence"],
            depth=h.get("depth", 0.0),
        )
        for h in holds_data
    ]

    return HoldsResponse(wall_id=wall.id, holds=holds)
