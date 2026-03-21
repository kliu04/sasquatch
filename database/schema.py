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


class Climb(Base):
    __tablename__ = "climbs"
    id = Column(Integer, primary_key=True)
    wall_id = Column(Integer, ForeignKey("walls.id"))
    difficulty = Column(Enum(Difficulty))
    classification = Column(Enum(Classification))
    is_favourite = Column(Boolean)
    date_sent = Column(DateTime)

engine = create_engine('postgresql://user:password@localhost:5432/mydb')
Base.metadata.create_all(engine)