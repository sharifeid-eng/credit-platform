"""Database connection and SQLAlchemy setup.

DB-optional: when DATABASE_URL is not set, engine is None and the platform
runs in tape-only mode. All DB-touching code must check for None.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None
SessionLocal = sessionmaker(bind=engine) if engine else None


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency yielding a DB session (or None if no DB configured)."""
    if SessionLocal is None:
        yield None
        return
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
