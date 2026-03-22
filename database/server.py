from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.auth import get_current_user
from database.db import get_db
from database.schema import Climb, Classification, Difficulty, User, Wall

app = FastAPI(title="Sasquatch API")


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class WallCreate(BaseModel):
    name: str
    wall_img_url: str | None = None
    wall_ply_url: str | None = None


class WallResponse(BaseModel):
    id: int
    name: str
    wall_img_url: str | None
    wall_ply_url: str | None


class ClimbCreate(BaseModel):
    difficulty: str
    classification: str


class ClimbResponse(BaseModel):
    id: int
    wall_id: int
    difficulty: str | None
    classification: str | None
    is_favourite: bool | None
    date_sent: datetime | None
    climb_img_url: str | None


# ---------------------------------------------------------------------------
# Wall endpoints
# ---------------------------------------------------------------------------

@app.post("/wall", response_model=WallResponse)
def create_wall(
    body: WallCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wall = Wall(
        user_id=user.id,
        name=body.name,
        wall_img_url=body.wall_img_url,
        wall_ply_url=body.wall_ply_url,
    )
    db.add(wall)
    db.commit()
    db.refresh(wall)
    return _wall_response(wall)


@app.get("/wall", response_model=list[WallResponse])
def list_walls(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    walls = db.query(Wall).filter(Wall.user_id == user.id).all()
    return [_wall_response(w) for w in walls]


@app.get("/wall/{wall_id}", response_model=WallResponse)
def get_wall(
    wall_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wall = _get_user_wall(db, user.id, wall_id)
    return _wall_response(wall)


# ---------------------------------------------------------------------------
# Climb endpoints
# ---------------------------------------------------------------------------

@app.post("/wall/{wall_id}/climb", response_model=ClimbResponse)
def create_climb(
    wall_id: int,
    body: ClimbCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_user_wall(db, user.id, wall_id)

    climb = Climb(
        wall_id=wall_id,
        difficulty=Difficulty[body.difficulty],
        classification=Classification[body.classification],
        is_favourite=False,
    )
    db.add(climb)
    db.commit()
    db.refresh(climb)
    return _climb_response(climb)


@app.get("/wall/{wall_id}/climb", response_model=list[ClimbResponse])
def list_climbs(
    wall_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_user_wall(db, user.id, wall_id)
    climbs = db.query(Climb).filter(Climb.wall_id == wall_id).all()
    return [_climb_response(c) for c in climbs]


@app.get("/wall/{wall_id}/climb/{climb_id}", response_model=ClimbResponse)
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


@app.patch("/wall/{wall_id}/climb/{climb_id}/fav", response_model=ClimbResponse)
def toggle_favourite(
    wall_id: int,
    climb_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_user_wall(db, user.id, wall_id)
    climb = db.query(Climb).filter(Climb.id == climb_id, Climb.wall_id == wall_id).first()
    if climb is None:
        raise HTTPException(404, "Climb not found")
    climb.is_favourite = not climb.is_favourite
    db.commit()
    db.refresh(climb)
    return _climb_response(climb)


@app.patch("/wall/{wall_id}/climb/{climb_id}/sent", response_model=ClimbResponse)
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
    climb.date_sent = datetime.utcnow()
    db.commit()
    db.refresh(climb)
    return _climb_response(climb)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_user_wall(db: Session, user_id: int, wall_id: int) -> Wall:
    wall = db.query(Wall).filter(Wall.id == wall_id, Wall.user_id == user_id).first()
    if wall is None:
        raise HTTPException(404, "Wall not found")
    return wall


def _wall_response(wall: Wall) -> WallResponse:
    return WallResponse(
        id=wall.id,
        name=wall.name,
        wall_img_url=wall.wall_img_url,
        wall_ply_url=wall.wall_ply_url,
    )


def _climb_response(climb: Climb) -> ClimbResponse:
    return ClimbResponse(
        id=climb.id,
        wall_id=climb.wall_id,
        difficulty=climb.difficulty.name if climb.difficulty else None,
        classification=climb.classification.name if climb.classification else None,
        is_favourite=climb.is_favourite,
        date_sent=climb.date_sent,
        climb_img_url=climb.climb_img_url,
    )
