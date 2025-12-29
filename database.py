# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# DATABASE_URL format examples:
# - Local SQLite: sqlite:///./tradeops.db   (default for dev)
# - Neon Postgres: postgresql+psycopg2://USER:PASSWORD@HOST/DBNAME?sslmode=require
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./tradeops.db")

connect_args = {}
if DB_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DB_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
