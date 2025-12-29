import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Get the URL
raw_db_url = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_CY9j6DWvxrQA@ep-wispy-shadow-aeman4s8-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)

# 2. Fix for Render/Heroku 'postgres://' legacy format
# SQLAlchemy 1.4+ requires 'postgresql://'
if raw_db_url.startswith("postgres://"):
    DATABASE_URL = raw_db_url.replace("postgres://", "postgresql://", 1)
else:
    DATABASE_URL = raw_db_url

# 3. Create Engine
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
