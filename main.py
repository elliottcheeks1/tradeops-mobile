# main.py
"""
FastAPI entrypoint for TradeOps:
- JSON API (health, quotes)
- Mounts the Dash UI at /app
"""

from typing import List

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.wsgi import WSGIMiddleware
from sqlalchemy.orm import Session

# Local imports
from database import SessionLocal, engine
import models
import crud
import schemas
from frontend_app import dash_app  # <- Dash instance

# -------------------------------------------------------------------
# Database init
# -------------------------------------------------------------------
models.Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------------------------------------------
# FastAPI app
# -------------------------------------------------------------------
app = FastAPI(
    title="TradeOps API",
    description="Backend API + Dash UI for home service contractors",
    version="0.1.0",
)

# CORS (for future separate frontends / localhost testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # you can tighten this later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------------------
# Health + root
# -------------------------------------------------------------------
@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/")
def root():
    """
    Simple JSON landing page so you know the service is up.
    """
    return JSONResponse(
        {
            "service": "TradeOps API",
            "status": "ok",
            "docs": "/docs",
            "endpoints": ["/health", "/quotes", "/app"],
        }
    )


# -------------------------------------------------------------------
# Quotes API (simple CRUD)
# -------------------------------------------------------------------
@app.get("/quotes", response_model=List[schemas.QuoteOut])
def list_quotes(db: Session = Depends(get_db)):
    return crud.get_quotes(db)


@app.get("/quotes/{quote_id}", response_model=schemas.QuoteOut)
def get_quote(quote_id: int, db: Session = Depends(get_db)):
    db_quote = crud.get_quote(db, quote_id)
    if not db_quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return db_quote


@app.post("/quotes", response_model=schemas.QuoteOut)
def create_quote(quote: schemas.QuoteCreate, db: Session = Depends(get_db)):
    return crud.create_quote(db, quote)


@app.put("/quotes/{quote_id}", response_model=schemas.QuoteOut)
def update_quote(
    quote_id: int, quote: schemas.QuoteUpdate, db: Session = Depends(get_db)
):
    db_quote = crud.update_quote(db, quote_id, quote)
    if not db_quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return db_quote


@app.delete("/quotes/{quote_id}")
def delete_quote(quote_id: int, db: Session = Depends(get_db)):
    deleted = crud.delete_quote(db, quote_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Quote not found")
    return {"ok": True}


# -------------------------------------------------------------------
# Mount Dash UI at /app
# -------------------------------------------------------------------
# Dash will live at: https://tradeops.onrender.com/app
app.mount("/app", WSGIMiddleware(dash_app.server))
