# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# For now, SQLite file in the project root.
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./tradeops.db")

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency that yields a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
