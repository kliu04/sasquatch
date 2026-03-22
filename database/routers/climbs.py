"""Climb endpoints: generate routes, list saved, get, update, delete."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.auth import get_current_user
from database.db import get_db
from database.schema import Classification, Climb, Difficulty, User, Wall, WallStatus
from database.scan_worker import ScanWorker
from database.storage import GCSStorage

router = APIRouter(prefix="/walls/{wall_id}/climbs", tags=["climbs"])

_storage: GCSStorage | None = None
_worker: ScanWorker | None = None


def configure(storage: GCSStorage, worker: ScanWorker) -> None:
    global _storage, _worker
    _storage = storage
    _worker = worker


# ── Schemas ──

class ClimbCreate(BaseModel):
    difficulty: str  # easy | medium | hard
    style: str  # static | dynamic
    wingspan: float | None = None
    top_k: int = 3


class ClimbUpdate(BaseModel):
    is_saved: bool | None = None
    is_favourite: bool | None = None


class ClimbResponse(BaseModel):
    id: int
    wall_id: int
    difficulty: str | None
    classification: str | None
    route_hold_ids: list[int] | None
    is_saved: bool
    is_favourite: bool
    date_sent: str | None
    climb_img_url: str | None
    created_at: str | None = None


# ── Helpers ──

def _get_user_wall(db: Session, user_id: int, wall_id: int) -> Wall:
    wall = db.query(Wall).filter(Wall.id == wall_id, Wall.user_id == user_id).first()
    if wall is None:
        raise HTTPException(404, "Wall not found")
    return wall


def _climb_response(climb: Climb) -> ClimbResponse:
    route_ids = None
    if climb.route_hold_ids:
        try:
            route_ids = json.loads(climb.route_hold_ids)
        except (json.JSONDecodeError, TypeError):
            route_ids = None

    return ClimbResponse(
        id=climb.id,
        wall_id=climb.wall_id,
        difficulty=climb.difficulty.name if climb.difficulty else None,
        classification=climb.classification.name if climb.classification else None,
        route_hold_ids=route_ids,
        is_saved=climb.is_saved or False,
        is_favourite=climb.is_favourite or False,
        date_sent=climb.date_sent.isoformat() if climb.date_sent else None,
        climb_img_url=_storage.signed_url_or_none(climb.climb_img_url),
        created_at=climb.created_at.isoformat() if climb.created_at else None,
    )


# ── Endpoints ──

@router.post("", response_model=list[ClimbResponse], status_code=201)
def create_climbs(
    wall_id: int,
    body: ClimbCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wall = _get_user_wall(db, user.id, wall_id)

    if wall.status != WallStatus.ready:
        raise HTTPException(409, f"Wall is not ready (status: {wall.status.name})")
    if not wall.holds_json:
        raise HTTPException(409, "No holds detected for this wall")

    # Validate enums
    if body.difficulty not in ("easy", "medium", "hard"):
        raise HTTPException(400, "difficulty must be easy, medium, or hard")
    if body.style not in ("static", "dynamic"):
        raise HTTPException(400, "style must be static or dynamic")

    wingspan = body.wingspan or user.wingspan or 1.8

    # Generate routes + images (functional: holds data → routes)
    routes, images = _worker.generate_routes(
        wall_id=wall_id,
        holds_json=wall.holds_json,
        difficulty=body.difficulty,
        style=body.style,
        wingspan=wingspan,
        top_k=body.top_k,
    )

    climbs = []
    for i, route in enumerate(routes):
        climb = Climb(
            wall_id=wall_id,
            difficulty=Difficulty[body.difficulty],
            classification=Classification[body.style],
            route_hold_ids=json.dumps(route),
            is_saved=False,
            is_favourite=False,
        )
        db.add(climb)
        db.flush()  # get the ID

        # Upload route image if available
        if i < len(images):
            img_url = _storage.upload_bytes(
                images[i],
                f"walls/{wall_id}/climbs/{climb.id}.png",
            )
            climb.climb_img_url = img_url

        climbs.append(climb)

    db.commit()
    for c in climbs:
        db.refresh(c)

    return [_climb_response(c) for c in climbs]


@router.get("", response_model=list[ClimbResponse])
def list_climbs(
    wall_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List saved climbs for this wall."""
    _get_user_wall(db, user.id, wall_id)
    climbs = (
        db.query(Climb)
        .filter(Climb.wall_id == wall_id, Climb.is_saved == True)
        .all()
    )
    return [_climb_response(c) for c in climbs]


@router.get("/{climb_id}", response_model=ClimbResponse)
def get_climb(
    wall_id: int,
    climb_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_user_wall(db, user.id, wall_id)
    climb = db.query(Climb).filter(Climb.id == climb_id, Climb.wall_id == wall_id).first()
    if climb is None:
        raise HTTPException(404, "Climb not found")
    return _climb_response(climb)


@router.patch("/{climb_id}", response_model=ClimbResponse)
def update_climb(
    wall_id: int,
    climb_id: int,
    body: ClimbUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_user_wall(db, user.id, wall_id)
    climb = db.query(Climb).filter(Climb.id == climb_id, Climb.wall_id == wall_id).first()
    if climb is None:
        raise HTTPException(404, "Climb not found")

    if body.is_favourite is not None:
        climb.is_favourite = body.is_favourite
        if body.is_favourite:
            climb.is_saved = True  # favourite implies saved

    if body.is_saved is not None:
        climb.is_saved = body.is_saved
        if not body.is_saved:
            climb.is_favourite = False  # unsaving clears favourite

    db.commit()
    db.refresh(climb)
    return _climb_response(climb)


@router.patch("/{climb_id}/sent", response_model=ClimbResponse)
def mark_sent(
    wall_id: int,
    climb_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_user_wall(db, user.id, wall_id)
    climb = db.query(Climb).filter(Climb.id == climb_id, Climb.wall_id == wall_id).first()
    if climb is None:
        raise HTTPException(404, "Climb not found")
    climb.date_sent = datetime.now(timezone.utc)
    climb.is_saved = True  # sent implies saved, otherwise invisible in list endpoints
    db.commit()
    db.refresh(climb)
    return _climb_response(climb)


@router.delete("/{climb_id}", status_code=204)
def delete_climb(
    wall_id: int,
    climb_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_user_wall(db, user.id, wall_id)
    climb = db.query(Climb).filter(Climb.id == climb_id, Climb.wall_id == wall_id).first()
    if climb is None:
        raise HTTPException(404, "Climb not found")

    # Delete GCS image
    if climb.climb_img_url:
        try:
            _storage.delete_prefix(f"walls/{wall_id}/climbs/{climb_id}.")
        except Exception:
            pass

    db.delete(climb)
    db.commit()
