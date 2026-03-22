"""User profile endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.auth import get_current_user
from database.db import get_db
from database.schema import User

router = APIRouter(prefix="/users", tags=["users"])


class UserResponse(BaseModel):
    id: int
    username: str | None
    wingspan: float | None


class UserUpdate(BaseModel):
    username: str | None = None
    wingspan: float | None = None


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return UserResponse(id=user.id, username=user.username, wingspan=user.wingspan)


@router.patch("/me", response_model=UserResponse)
def update_me(
    body: UserUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Re-query user in this session (auth may use a different session)
    db_user = db.query(User).filter(User.id == user.id).first()
    if body.username is not None:
        db_user.username = body.username
    if body.wingspan is not None:
        db_user.wingspan = body.wingspan
    db.commit()
    db.refresh(db_user)
    return UserResponse(id=db_user.id, username=db_user.username, wingspan=db_user.wingspan)
