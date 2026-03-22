from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import DeclarativeBase, relationship

import enum


@enum.unique
class Difficulty(enum.Enum):
    easy = enum.auto()
    medium = enum.auto()
    hard = enum.auto()


@enum.unique
class Classification(enum.Enum):
    static = enum.auto()
    dynamic = enum.auto()


@enum.unique
class WallStatus(enum.Enum):
    pending_upload = enum.auto()
    processing = enum.auto()
    ready = enum.auto()
    error = enum.auto()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    google_id = Column(String, unique=True, nullable=False)
    username = Column(String)
    wingspan = Column(Float)
    walls = relationship("Wall")


class Wall(Base):
    __tablename__ = "walls"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)
    status = Column(Enum(WallStatus), default=WallStatus.pending_upload)
    error_message = Column(String, nullable=True)
    hold_count = Column(Integer, nullable=True)
    holds_json = Column(String, nullable=True)
    wall_img_url = Column(String, nullable=True)
    wall_ply_url = Column(String, nullable=True)
    holds_image_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    climbs = relationship("Climb", cascade="all, delete-orphan")


class Climb(Base):
    __tablename__ = "climbs"
    id = Column(Integer, primary_key=True)
    wall_id = Column(Integer, ForeignKey("walls.id"))
    difficulty = Column(Enum(Difficulty))
    classification = Column(Enum(Classification))
    route_hold_ids = Column(String, nullable=True)
    is_saved = Column(Boolean, default=False)
    is_favourite = Column(Boolean, default=False)
    date_sent = Column(DateTime, nullable=True)
    climb_img_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
