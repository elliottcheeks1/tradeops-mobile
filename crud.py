# app/crud.py
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime
import models, schemas           # ✅ absolute import



# Customers

def create_customer(db: Session, account_id: str, data: schemas.CustomerCreate) -> models.Customer:
    c = models.Customer(
        account_id=account_id,
        location_id=data.location_id,
        name=data.name,
        phone=data.phone,
        email=data.email,
        billing_address=data.billing_address.model_dump() if data.billing_address else None,
        service_address=data.service_address.model_dump() if data.service_address else None,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def list_customers(db: Session, account_id: str, search: str | None = None, limit: int = 50):
    q = db.query(models.Customer).filter(models.Customer.account_id == account_id)
    if search:
        like = f"%{search}%"
        q = q.filter(models.Customer.name.ilike(like))
    return q.order_by(models.Customer.created_at.desc()).limit(limit).all()


# Leads

def create_lead(db: Session, account_id: str, data: schemas.LeadCreate) -> models.Lead:
    lead = models.Lead(
        account_id=account_id,
        location_id=data.location_id,
        customer_id=data.customer_id,
        title=data.title,
        description=data.description,
        source=data.source,
    )
    db.add(lead)
    db.flush()  # get lead.id

    if data.attribution:
        attrib = models.LeadAttribution(
            lead_id=lead.id,
            **data.attribution.model_dump(exclude_unset=True)
        )
        db.add(attrib)

    # Activity event
    activity = models.ActivityEvent(
        account_id=account_id,
        customer_id=data.customer_id,
        lead_id=lead.id,
        actor_type="user",
        event_type="lead.created",
        payload={"title": data.title, "source": data.source},
    )
    db.add(activity)

    db.commit()
    db.refresh(lead)
    return lead


# Quotes

def _recalc_quote_totals(quote: models.Quote):
    total_cost = Decimal("0")
    total_price = Decimal("0")
    for li in quote.line_items:
        total_cost += (li.unit_cost or 0) * (li.qty or 0)
        total_price += (li.unit_price or 0) * (li.qty or 0)
    quote.total_cost = total_cost
    quote.total_price = total_price
    quote.margin_percent = ((total_price - total_cost) / total_price * 100
                            if total_price > 0 else 0)


def create_quote(db: Session, account_id: str, data: schemas.QuoteCreate) -> models.Quote:
    quote = models.Quote(
        account_id=account_id,
        location_id=data.location_id,
        customer_id=data.customer_id,
        title=data.title,
        selling_tech_id=data.selling_tech_id,
        status="draft",
    )
    db.add(quote)
    db.flush()

    for idx, li in enumerate(data.line_items):
        db.add(models.QuoteLineItem(
            quote_id=quote.id,
            type=li.type,
            code=li.code,
            description=li.description,
            qty=li.qty,
            unit_cost=li.unit_cost,
            unit_price=li.unit_price,
            position=li.position or idx
        ))

    _recalc_quote_totals(quote)

    db.add(models.ActivityEvent(
        account_id=account_id,
        customer_id=data.customer_id,
        quote_id=quote.id,
        actor_type="user",
        event_type="quote.created",
        payload={"title": data.title}
    ))

    db.commit()
    db.refresh(quote)
    return quote


def list_quotes(db: Session, account_id: str, customer_id: str | None = None):
    q = db.query(models.Quote).filter(models.Quote.account_id == account_id)
    if customer_id:
        q = q.filter(models.Quote.customer_id == customer_id)
    return q.order_by(models.Quote.created_at.desc()).all()


def get_activity_for_customer(db: Session, account_id: str, customer_id: str, limit: int = 50):
    return (
        db.query(models.ActivityEvent)
        .filter(
            models.ActivityEvent.account_id == account_id,
            models.ActivityEvent.customer_id == customer_id,
        )
        .order_by(models.ActivityEvent.created_at.desc())
        .limit(limit)
        .all()
    )

