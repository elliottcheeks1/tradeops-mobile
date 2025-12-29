from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime
import models, schemas

# ---------- Helper ----------

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

# ---------- Quotes ----------

def list_quotes(db: Session, account_id: str, customer_id: str | None = None):
    q = db.query(models.Quote).filter(models.Quote.account_id == account_id)
    if customer_id:
        q = q.filter(models.Quote.customer_id == customer_id)
    
    quotes = q.order_by(models.Quote.created_at.desc()).all()
    
    # Enrich with customer name for the UI
    for quote in quotes:
        if quote.customer:
            quote.customer_name = quote.customer.name
        else:
            quote.customer_name = "Unknown Client"
            
    return quotes

def get_quote(db: Session, quote_id: str):
    quote = db.query(models.Quote).filter(models.Quote.id == quote_id).first()
    if quote and quote.customer:
        quote.customer_name = quote.customer.name
    return quote

def create_quote(db: Session, account_id: str, data: schemas.QuoteCreate) -> models.Quote:
    quote = models.Quote(
        account_id=account_id,
        location_id=data.location_id,
        customer_id=data.customer_id,
        title=data.title,
        selling_tech_id=data.selling_tech_id,
        status=data.status or "draft",
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
    db.commit()
    db.refresh(quote)
    return quote

def update_quote(db: Session, quote_id: str, data: schemas.QuoteUpdate):
    quote = db.query(models.Quote).filter(models.Quote.id == quote_id).first()
    if not quote:
        return None

    if data.title is not None:
        quote.title = data.title
    if data.status is not None:
        quote.status = data.status

    if data.line_items is not None:
        # Clear old items
        db.query(models.QuoteLineItem).filter(models.QuoteLineItem.quote_id == quote_id).delete()
        # Add new items
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
    
    db.commit()
    db.refresh(quote)
    return quote

def delete_quote(db: Session, quote_id: str):
    quote = db.query(models.Quote).filter(models.Quote.id == quote_id).first()
    if quote:
        db.delete(quote)
        db.commit()
        return True
    return False

# ---------- Customers ----------

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

# ---------- Leads ----------

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
    db.flush()

    if data.attribution:
        attrib = models.LeadAttribution(
            lead_id=lead.id,
            **data.attribution.model_dump(exclude_unset=True)
        )
        db.add(attrib)

    db.commit()
    db.refresh(lead)
    return lead

# ---------- Notes / Activity ----------

def create_quote_note(db: Session, quote_id: str, account_id: str, note: schemas.NoteCreate):
    event = models.ActivityEvent(
        account_id=account_id,
        quote_id=quote_id,
        actor_type="user",
        actor_id=note.author,
        event_type="note",
        payload={"content": note.content}
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

def get_quote_notes(db: Session, quote_id: str):
    events = (
        db.query(models.ActivityEvent)
        .filter(
            models.ActivityEvent.quote_id == quote_id,
            models.ActivityEvent.event_type == "note"
        )
        .order_by(models.ActivityEvent.created_at.desc())
        .all()
    )
    notes = []
    for e in events:
        content = e.payload.get("content", "") if e.payload else ""
        notes.append(schemas.NoteOut(
            id=e.id,
            content=content,
            author=e.actor_id,
            created_at=e.created_at
        ))
    return notes
