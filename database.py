# database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Get DATABASE_URL from env (Render + Neon)
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_CY9j6DWvxrQA@ep-wispy-shadow-aeman4s8-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"  # fallback for local dev
)

# SQLAlchemy 2.0-style engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()
