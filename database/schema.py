from sqlalchemy import (
    Column,
    create_engine,
    Integer,
    String,
    ForeignKey,
    Float,
    Enum,
    Boolean,
    DateTime,
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


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String)
    wingspan = Column(Float)
    walls = relationship("Wall")


class Wall(Base):
    __tablename__ = "walls"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)
    climbs = relationship("Climb")
    wall_img_url = Column(String)
    wall_ply_url = Column(String)


class Climb(Base):
    __tablename__ = "climbs"
    id = Column(Integer, primary_key=True)
    wall_id = Column(Integer, ForeignKey("walls.id"))
    difficulty = Column(Enum(Difficulty))
    classification = Column(Enum(Classification))
    is_favourite = Column(Boolean)
    date_sent = Column(DateTime)
    climb_img_url = Column(String)

engine = create_engine('postgresql://postgres:dev@34.11.229.123:5432/sasquatch')
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)