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

# Local imports (Must be in the same directory)
from database import SessionLocal, engine
import models
import crud
import schemas
from frontend_app import dash_app

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------
# Since we don't have login yet, we use the ID from seed_data.py
DEMO_ACCOUNT_ID = "acct-demo-001" 


# ---------- Notes API ----------

@app.post("/quotes/{quote_id}/notes", response_model=schemas.NoteOut)
def create_note(quote_id: str, note: schemas.NoteCreate, db: Session = Depends(get_db)):
    """Add a note to a quote."""
    # Using DEMO_ACCOUNT_ID from config
    return crud.create_quote_note(db, quote_id, DEMO_ACCOUNT_ID, note)

@app.get("/quotes/{quote_id}/notes", response_model=List[schemas.NoteOut])
def get_notes(quote_id: str, db: Session = Depends(get_db)):
    """Get all notes for a quote."""
    return crud.get_quote_notes(db, quote_id)
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

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    Simple JSON landing page.
    """
    return JSONResponse(
        {
            "service": "TradeOps API",
            "status": "ok",
            "docs": "/docs",
            "dashboard": "/app",
            "endpoints": ["/health", "/quotes", "/app"],
        }
    )


# -------------------------------------------------------------------
# Quotes API
# -------------------------------------------------------------------
@app.get("/quotes", response_model=List[schemas.QuoteOut])
def list_quotes(db: Session = Depends(get_db)):
    """
    Fetch all quotes for the demo account.
    """
    return crud.list_quotes(db, account_id=DEMO_ACCOUNT_ID)


@app.get("/quotes/{quote_id}", response_model=schemas.QuoteOut)
def get_quote(quote_id: str, db: Session = Depends(get_db)):
    """
    Get a single quote by UUID.
    """
    db_quote = crud.get_quote(db, quote_id)
    if not db_quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return db_quote


@app.post("/quotes", response_model=schemas.QuoteOut)
def create_quote(quote: schemas.QuoteCreate, db: Session = Depends(get_db)):
    """
    Create a new quote.
    """
    return crud.create_quote(db, account_id=DEMO_ACCOUNT_ID, data=quote)


@app.put("/quotes/{quote_id}", response_model=schemas.QuoteOut)
def update_quote(
    quote_id: str, quote: schemas.QuoteUpdate, db: Session = Depends(get_db)
):
    """
    Update an existing quote by UUID.
    """
    db_quote = crud.update_quote(db, quote_id, quote)
    if not db_quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return db_quote


@app.delete("/quotes/{quote_id}")
def delete_quote(quote_id: str, db: Session = Depends(get_db)):
    """
    Delete a quote by UUID.
    """
    deleted = crud.delete_quote(db, quote_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Quote not found")
    return {"ok": True}


# -------------------------------------------------------------------
# Mount Dash UI at /app
# -------------------------------------------------------------------
app.mount("/app", WSGIMiddleware(dash_app.server))

