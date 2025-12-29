# app/main.py
from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from . import schemas, crud, models

# Create tables on startup for POC
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TradeOps Backend",
    version="0.1.0",
    description="Core API for customers, leads, quotes, and activity."
)

# For now we hard-code a demo account id.
FAKE_ACCOUNT_ID = "acct-demo-001"


@app.get("/health")
def health():
    return {"status": "ok"}


# ----- Customers -----

@app.post("/customers", response_model=schemas.CustomerOut)
def create_customer(customer: schemas.CustomerCreate, db: Session = Depends(get_db)):
    # TODO: verify location belongs to account
    return crud.create_customer(db, FAKE_ACCOUNT_ID, customer)


@app.get("/customers", response_model=list[schemas.CustomerOut])
def list_customers(
    search: str | None = Query(default=None, description="Search by name"),
    db: Session = Depends(get_db)
):
    return crud.list_customers(db, FAKE_ACCOUNT_ID, search=search)


@app.get("/customers/{customer_id}/activity", response_model=list[schemas.ActivityEventOut])
def customer_activity(customer_id: str, db: Session = Depends(get_db)):
    events = crud.get_activity_for_customer(db, FAKE_ACCOUNT_ID, customer_id, limit=50)
    return events


# ----- Leads -----

@app.post("/leads", response_model=schemas.LeadOut)
def create_lead(lead: schemas.LeadCreate, db: Session = Depends(get_db)):
    # Simple: auto-create customer if not provided
    if not lead.customer_id:
        cust_data = schemas.CustomerCreate(
            location_id=lead.location_id,
            name=lead.title,
        )
        customer = crud.create_customer(db, FAKE_ACCOUNT_ID, cust_data)
        lead.customer_id = customer.id

    obj = crud.create_lead(db, FAKE_ACCOUNT_ID, lead)
    return obj


@app.get("/leads", response_model=list[schemas.LeadOut])
def list_leads(
    status: str | None = None,
    db: Session = Depends(get_db)
):
    q = db.query(models.Lead).filter(models.Lead.account_id == FAKE_ACCOUNT_ID)
    if status:
        q = q.filter(models.Lead.status == status)
    leads = q.order_by(models.Lead.created_at.desc()).all()
    return leads


# ----- Quotes -----

@app.post("/quotes", response_model=schemas.QuoteOut)
def create_quote(quote: schemas.QuoteCreate, db: Session = Depends(get_db)):
    return crud.create_quote(db, FAKE_ACCOUNT_ID, quote)


@app.get("/quotes", response_model=list[schemas.QuoteOut])
def list_quotes(
    customer_id: str | None = None,
    db: Session = Depends(get_db)
):
    quotes = crud.list_quotes(db, FAKE_ACCOUNT_ID, customer_id=customer_id)
    return quotes
