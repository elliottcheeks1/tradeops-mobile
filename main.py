from __future__ import annotations

import json
from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text, create_engine, select, func
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# =========================================================
# TradeOps Full Tool (POC)
# - FastAPI + SQLite + SQLAlchemy
# - Keeps your existing SPA routes and /api endpoints,
#   but upgrades the backend to support:
#   * Accounts/Customers
#   * Quotes + Quote Management (status, edit, detail)
#   * Service Calls / Appointments (schedule, assign tech, complete)
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tradeops.db"
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def utcnow() -> datetime:
    return datetime.utcnow()


def iso_date(d: Optional[datetime]) -> str:
    if not d:
        return ""
    return d.strftime("%Y-%m-%d")


def iso_time(d: Optional[datetime]) -> str:
    if not d:
        return ""
    return d.strftime("%H:%M")


# =========================================================
# DB MODELS
# =========================================================

class User(Base):
    __tablename__ = "users"

    username = Column(String, primary_key=True)
    password = Column(String, nullable=False)  # POC only
    role = Column(String, nullable=False)      # admin / tech
    full_name = Column(String, nullable=False)


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, default="")
    phone = Column(String, default="")
    address = Column(String, default="")
    city = Column(String, default="")
    created_at = Column(DateTime, default=utcnow, nullable=False)

    quotes = relationship("Quote", back_populates="customer", cascade="all, delete-orphan")
    service_calls = relationship("ServiceCall", back_populates="customer", cascade="all, delete-orphan")


class CatalogItem(Base):
    __tablename__ = "catalog"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String, default="")
    base_cost = Column(Float, default=0.0)
    price = Column(Float, default=0.0)


class Quote(Base):
    __tablename__ = "quotes"

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    status = Column(String, default="Draft")  # Draft, Sent, Approved, Declined
    total = Column(Float, default=0.0)
    notes = Column(Text, default="")
    items_json = Column(Text, default="[]")

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    customer = relationship("Customer", back_populates="quotes")
    service_call = relationship("ServiceCall", back_populates="quote", uselist=False)


class ServiceCall(Base):
    """
    Represents an appointment / service call / job.
    Reuses your existing UI concepts:
    - Dispatch board assigns tech + schedule
    - Tech "My Schedule" shows assigned jobs
    - Job Details allows work order items + completion notes + completion
    """
    __tablename__ = "service_calls"

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    quote_id = Column(String, ForeignKey("quotes.id"), nullable=True)

    status = Column(String, default="New")  # New, Approved, Scheduled, In Progress, Complete
    title = Column(String, default="Service Call")
    address = Column(String, default="")

    tech_username = Column(String, ForeignKey("users.username"), nullable=True)
    scheduled_start = Column(DateTime, nullable=True)
    scheduled_end = Column(DateTime, nullable=True)

    total = Column(Float, default=0.0)
    items_json = Column(Text, default="[]")
    notes = Column(Text, default="")

    created_at = Column(DateTime, default=utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    customer = relationship("Customer", back_populates="service_calls")
    quote = relationship("Quote", back_populates="service_call")


# =========================================================
# Pydantic Schemas
# =========================================================

class LoginIn(BaseModel):
    username: str
    password: str


class CustomerIn(BaseModel):
    id: Optional[str] = None
    name: str
    email: str = ""
    phone: str = ""
    address: str = ""
    city: str = ""


class QuoteItemIn(BaseModel):
    id: Optional[str] = None
    name: str
    category: Optional[str] = ""
    price: float
    qty: int = 1


class QuoteIn(BaseModel):
    customer_id: str
    items: List[QuoteItemIn]
    total: float
    notes: str = ""
    status: Optional[str] = None  # if omitted -> Draft


class QuoteUpdateIn(BaseModel):
    items: List[QuoteItemIn]
    total: float
    notes: str = ""
    status: Optional[str] = None


class QuoteStatusIn(BaseModel):
    status: str


class ServiceCallIn(BaseModel):
    customer_id: str
    title: str = "Service Call"
    address: str = ""
    quote_id: Optional[str] = None
    notes: str = ""
    status: str = "New"


class AssignIn(BaseModel):
    # NOTE: the existing SPA posts "quote_id" for the job id (kept for compatibility)
    quote_id: str = Field(..., description="ServiceCall.id (kept field name for UI compatibility)")
    tech_username: str
    scheduled_date: str  # YYYY-MM-DD
    start_time: Optional[str] = "09:00"  # HH:MM
    duration_minutes: Optional[int] = 120


class CompleteJobIn(BaseModel):
    job_id: str
    final_items: List[QuoteItemIn]
    total: float
    notes: str = ""


# =========================================================
# App Setup
# =========================================================

app = FastAPI(title="TradeOps Full Tool")

# Serve SPA
static_path = BASE_DIR / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")


@app.get("/")
def root():
    index = static_path / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="index.html not found in ./static")
    return FileResponse(index)


# =========================================================
# DB Init / Seeding
# =========================================================

def init_db():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        # Seed users
        if db.execute(select(func.count(User.username))).scalar_one() == 0:
            db.add_all([
                User(username="admin", password="admin", role="admin", full_name="Admin User"),
                User(username="tech", password="tech", role="tech", full_name="Technician User"),
                User(username="tech2", password="tech2", role="tech", full_name="Technician Two"),
            ])

        # Seed customers
        if db.execute(select(func.count(Customer.id))).scalar_one() == 0:
            db.add_all([
                Customer(id="C-1", name="Burger King #402", address="123 Whopper Ln", city="Austin", email="bk402@franchise.com", phone="(512) 555-0101"),
                Customer(id="C-2", name="Marriott Downtown", address="400 Congress Ave", city="Austin", email="manager@marriott.com", phone="(512) 555-0102"),
                Customer(id="C-3", name="Residential - John Doe", address="88 Maple St", city="Austin", email="john@example.com", phone="(512) 555-0103"),
            ])

        # Seed catalog
        if db.execute(select(func.count(CatalogItem.id))).scalar_one() == 0:
            seed = [
                ("I-1", "HVAC Tune-up", "Service", 20, 89),
                ("I-2", "16 SEER AC Unit", "Install", 1800, 2800),
                ("I-3", "Water Heater Install", "Install", 600, 1200),
                ("I-4", "Panel Upgrade 200A", "Install", 800, 1600),
                ("I-5", "Drain Cleaning", "Service", 10, 149),
                ("I-6", "Smart Thermostat", "Service", 80, 249),
                ("I-7", "EV Charger Install", "Install", 300, 950),
            ]
            db.add_all([CatalogItem(id=i, name=n, category=c, base_cost=float(bc), price=float(p)) for i, n, c, bc, p in seed])

        db.commit()


@app.on_event("startup")
def on_startup():
    init_db()


# =========================================================
# Helpers
# =========================================================

def customer_to_dict(c: Customer) -> Dict[str, Any]:
    return {
        "id": c.id,
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "address": c.address,
        "city": c.city,
    }


def catalog_to_dict(i: CatalogItem) -> Dict[str, Any]:
    return {"id": i.id, "name": i.name, "category": i.category, "base_cost": i.base_cost, "price": i.price}


def quote_to_list_row(q: Quote) -> Dict[str, Any]:
    return {
        "id": q.id,
        "customer_id": q.customer_id,
        "customer_name": q.customer.name if q.customer else "",
        "total": float(q.total or 0.0),
        "status": q.status,
        "created_at": q.created_at.isoformat() if q.created_at else None,
    }


def sc_to_row(sc: ServiceCall) -> Dict[str, Any]:
    return {
        "id": sc.id,
        "customer_id": sc.customer_id,
        "quote_id": sc.quote_id,
        "customer_name": sc.customer.name if sc.customer else "",
        "address": sc.address or (sc.customer.address if sc.customer else ""),
        "status": sc.status,
        "tech": sc.tech_username or "",
        "scheduled_date": iso_date(sc.scheduled_start),
        "scheduled_time": iso_time(sc.scheduled_start),
        "items_json": sc.items_json or "[]",
        "notes": sc.notes or "",
        "total": float(sc.total or 0.0),
        "title": sc.title or "Service Call",
    }


def ensure_service_call_for_approved_quote(db, q: Quote) -> None:
    if q.status != "Approved":
        return
    existing = db.execute(select(ServiceCall).where(ServiceCall.quote_id == q.id)).scalar_one_or_none()
    if existing:
        # Keep in sync (POC)
        existing.total = float(q.total or 0.0)
        existing.items_json = q.items_json or "[]"
        if existing.status == "New":
            existing.status = "Approved"
        existing.address = existing.address or (q.customer.address if q.customer else "")
        return

    sc = ServiceCall(
        id=f"J-{q.id[-8:]}",
        customer_id=q.customer_id,
        quote_id=q.id,
        status="Approved",
        title=f"Service Call (from Quote)",
        address=q.customer.address if q.customer else "",
        total=float(q.total or 0.0),
        items_json=q.items_json or "[]",
        notes=q.notes or "",
    )
    db.add(sc)


# =========================================================
# API Endpoints (aligned to your SPA)
# =========================================================

@app.post("/api/login")
def api_login(payload: LoginIn):
    with SessionLocal() as db:
        u = db.get(User, payload.username)
        if not u or u.password != payload.password:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return {"user": {"username": u.username, "role": u.role, "full_name": u.full_name}}


@app.get("/api/init-data")
def api_init_data():
    with SessionLocal() as db:
        customers = db.execute(select(Customer).order_by(Customer.created_at.desc())).scalars().all()
        catalog = db.execute(select(CatalogItem).order_by(CatalogItem.name.asc())).scalars().all()
        return {"customers": [customer_to_dict(c) for c in customers], "catalog": [catalog_to_dict(i) for i in catalog]}


# -------------------- Customers / Accounts --------------------

@app.get("/api/customers")
def api_customers():
    with SessionLocal() as db:
        customers = db.execute(select(Customer).order_by(Customer.name.asc())).scalars().all()
        return [customer_to_dict(c) for c in customers]


@app.post("/api/customers")
def api_create_customer(payload: CustomerIn):
    with SessionLocal() as db:
        cid = payload.id or f"C-{int(datetime.utcnow().timestamp())}"
        if db.get(Customer, cid):
            raise HTTPException(status_code=400, detail="Customer ID already exists")
        c = Customer(
            id=cid,
            name=payload.name.strip(),
            email=payload.email.strip(),
            phone=payload.phone.strip(),
            address=payload.address.strip(),
            city=payload.city.strip(),
        )
        db.add(c)
        db.commit()
        return {"ok": True, "id": cid}


@app.put("/api/customers/{customer_id}")
def api_update_customer(customer_id: str, payload: CustomerIn):
    with SessionLocal() as db:
        c = db.get(Customer, customer_id)
        if not c:
            raise HTTPException(status_code=404, detail="Customer not found")
        c.name = payload.name.strip()
        c.email = payload.email.strip()
        c.phone = payload.phone.strip()
        c.address = payload.address.strip()
        c.city = payload.city.strip()
        db.commit()
        return {"ok": True}


@app.get("/api/customers/{customer_id}/summary")
def api_customer_summary(customer_id: str):
    with SessionLocal() as db:
        c = db.get(Customer, customer_id)
        if not c:
            raise HTTPException(status_code=404, detail="Customer not found")

        quotes = db.execute(select(Quote).where(Quote.customer_id == customer_id).order_by(Quote.created_at.desc())).scalars().all()
        calls = db.execute(select(ServiceCall).where(ServiceCall.customer_id == customer_id).order_by(ServiceCall.created_at.desc())).scalars().all()

        return {
            "customer": customer_to_dict(c),
            "quotes": [quote_to_list_row(q) for q in quotes],
            "service_calls": [sc_to_row(sc) for sc in calls],
        }


# -------------------- Quotes --------------------

@app.get("/api/quotes")
def api_quotes():
    with SessionLocal() as db:
        quotes = db.execute(select(Quote).order_by(Quote.created_at.desc())).scalars().all()
        return [quote_to_list_row(q) for q in quotes]


@app.get("/api/quotes/{quote_id}")
def api_quote_detail(quote_id: str):
    with SessionLocal() as db:
        q = db.get(Quote, quote_id)
        if not q:
            raise HTTPException(status_code=404, detail="Quote not found")
        try:
            items = json.loads(q.items_json or "[]")
        except Exception:
            items = []
        return {
            "id": q.id,
            "customer_id": q.customer_id,
            "customer_name": q.customer.name if q.customer else "",
            "status": q.status,
            "total": float(q.total or 0.0),
            "notes": q.notes or "",
            "items": items,
            "created_at": q.created_at.isoformat() if q.created_at else None,
            "updated_at": q.updated_at.isoformat() if q.updated_at else None,
        }


@app.post("/api/quotes")
def api_create_quote(payload: QuoteIn):
    with SessionLocal() as db:
        c = db.get(Customer, payload.customer_id)
        if not c:
            raise HTTPException(status_code=400, detail="Invalid customer_id")

        qid = f"Q-{int(datetime.utcnow().timestamp())}"
        status = payload.status or "Draft"
        q = Quote(
            id=qid,
            customer_id=payload.customer_id,
            status=status,
            total=float(payload.total or 0.0),
            notes=payload.notes or "",
            items_json=json.dumps([i.model_dump() for i in payload.items]),
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(q)
        db.commit()

        # If created as Approved, ensure a job exists
        with SessionLocal() as db2:
            q2 = db2.get(Quote, qid)
            if q2:
                ensure_service_call_for_approved_quote(db2, q2)
                db2.commit()

        return {"ok": True, "id": qid}


@app.put("/api/quotes/{quote_id}")
def api_update_quote(quote_id: str, payload: QuoteUpdateIn):
    with SessionLocal() as db:
        q = db.get(Quote, quote_id)
        if not q:
            raise HTTPException(status_code=404, detail="Quote not found")
        q.items_json = json.dumps([i.model_dump() for i in payload.items])
        q.total = float(payload.total or 0.0)
        q.notes = payload.notes or ""
        if payload.status:
            q.status = payload.status
        q.updated_at = utcnow()

        ensure_service_call_for_approved_quote(db, q)
        db.commit()
        return {"ok": True}


@app.post("/api/quotes/{quote_id}/status")
def api_set_quote_status(quote_id: str, payload: QuoteStatusIn):
    with SessionLocal() as db:
        q = db.get(Quote, quote_id)
        if not q:
            raise HTTPException(status_code=404, detail="Quote not found")
        q.status = payload.status
        q.updated_at = utcnow()
        ensure_service_call_for_approved_quote(db, q)
        db.commit()
        return {"ok": True}


# -------------------- Service Calls / Dispatch / Jobs --------------------

@app.post("/api/service-calls")
def api_create_service_call(payload: ServiceCallIn):
    with SessionLocal() as db:
        c = db.get(Customer, payload.customer_id)
        if not c:
            raise HTTPException(status_code=400, detail="Invalid customer_id")
        scid = f"J-{int(datetime.utcnow().timestamp())}"
        sc = ServiceCall(
            id=scid,
            customer_id=payload.customer_id,
            quote_id=payload.quote_id,
            status=payload.status or "New",
            title=payload.title or "Service Call",
            address=(payload.address or "").strip() or (c.address or ""),
            notes=payload.notes or "",
            items_json="[]",
            total=0.0,
        )
        db.add(sc)
        db.commit()
        return {"ok": True, "id": scid}


@app.get("/api/dispatch-data")
def api_dispatch_data():
    with SessionLocal() as db:
        techs = db.execute(select(User).where(User.role == "tech").order_by(User.full_name.asc())).scalars().all()

        unscheduled = db.execute(
            select(ServiceCall).where(ServiceCall.scheduled_start.is_(None)).where(ServiceCall.status.in_(["New", "Approved"])).order_by(ServiceCall.created_at.desc())
        ).scalars().all()

        scheduled = db.execute(
            select(ServiceCall).where(ServiceCall.scheduled_start.is_not(None)).where(ServiceCall.status.in_(["Scheduled", "In Progress", "Complete"])).order_by(ServiceCall.scheduled_start.asc())
        ).scalars().all()

        return {
            "techs": [{"username": t.username, "full_name": t.full_name} for t in techs],
            "unscheduled": [sc_to_row(sc) for sc in unscheduled],
            "scheduled": [sc_to_row(sc) for sc in scheduled],
        }


@app.post("/api/dispatch/assign")
def api_dispatch_assign(payload: AssignIn):
    with SessionLocal() as db:
        # Existing SPA passes the job id as "quote_id" (kept for compatibility)
        sc = db.get(ServiceCall, payload.quote_id)
        if not sc:
            raise HTTPException(status_code=404, detail="Service call not found")

        tech = db.get(User, payload.tech_username)
        if not tech or tech.role != "tech":
            raise HTTPException(status_code=400, detail="Invalid tech")

        try:
            y, m, d = [int(x) for x in payload.scheduled_date.split("-")]
            hh, mm = [int(x) for x in (payload.start_time or "09:00").split(":")]
            start = datetime(y, m, d, hh, mm)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid date/time")

        dur = int(payload.duration_minutes or 120)
        end = start + timedelta(minutes=dur)

        sc.tech_username = tech.username
        sc.scheduled_start = start
        sc.scheduled_end = end
        if sc.status in ("New", "Approved"):
            sc.status = "Scheduled"
        db.commit()
        return {"ok": True}


@app.get("/api/my-jobs")
def api_my_jobs(username: str):
    with SessionLocal() as db:
        jobs = db.execute(
            select(ServiceCall).where(ServiceCall.tech_username == username).where(ServiceCall.status.in_(["Scheduled", "In Progress"])).order_by(ServiceCall.scheduled_start.asc())
        ).scalars().all()
        return [sc_to_row(j) for j in jobs]


@app.post("/api/jobs/complete")
def api_jobs_complete(payload: CompleteJobIn):
    with SessionLocal() as db:
        sc = db.get(ServiceCall, payload.job_id)
        if not sc:
            raise HTTPException(status_code=404, detail="Job not found")
        sc.items_json = json.dumps([i.model_dump() for i in payload.final_items])
        sc.total = float(payload.total or 0.0)
        sc.notes = payload.notes or ""
        sc.status = "Complete"
        sc.completed_at = utcnow()
        db.commit()
        return {"ok": True}


# -------------------- Dashboard --------------------

@app.get("/api/dashboard")
def api_dashboard():
    today = datetime.utcnow().date()

    with SessionLocal() as db:
        # Revenue: completed jobs
        revenue = db.execute(select(func.coalesce(func.sum(ServiceCall.total), 0.0)).where(ServiceCall.status == "Complete")).scalar_one() or 0.0

        # Pending quotes: Draft or Sent
        pending = db.execute(select(func.count(Quote.id)).where(Quote.status.in_(["Draft", "Sent"]))).scalar_one() or 0

        # Active jobs: scheduled/in progress
        active_jobs = db.execute(select(func.count(ServiceCall.id)).where(ServiceCall.status.in_(["Scheduled", "In Progress"]))).scalar_one() or 0

        # Avg ticket: completed jobs avg, fallback to 0
        avg_ticket = db.execute(select(func.coalesce(func.avg(ServiceCall.total), 0.0)).where(ServiceCall.status == "Complete")).scalar_one() or 0.0

        # Recent activity: latest quotes (mix w/ jobs)
        recent_q = db.execute(select(Quote).order_by(Quote.created_at.desc()).limit(8)).scalars().all()
        recent = [
            {
                "id": q.id,
                "customer_name": q.customer.name if q.customer else "",
                "status": f"Quote: {q.status}",
                "total": float(q.total or 0.0),
            }
            for q in recent_q
        ]

        # Today's schedule
        start_dt = datetime(today.year, today.month, today.day, 0, 0)
        end_dt = start_dt + timedelta(days=1)
        todays = db.execute(
            select(ServiceCall).where(ServiceCall.scheduled_start.is_not(None)).where(ServiceCall.scheduled_start >= start_dt).where(ServiceCall.scheduled_start < end_dt).order_by(ServiceCall.scheduled_start.asc())
        ).scalars().all()

        schedule = [
            {
                "id": j.id,
                "customer_name": j.customer.name if j.customer else "",
                "scheduled_date": f"{iso_date(j.scheduled_start)} {iso_time(j.scheduled_start)}",
                "tech": j.tech_username or "",
            }
            for j in todays
        ]

        return {
            "revenue": float(revenue),
            "pending": int(pending),
            "active_jobs": int(active_jobs),
            "avg_ticket": float(avg_ticket),
            "recent": recent,
            "schedule": schedule,
        }
