# app/models.py
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey, Text, Numeric, JSON
)
from sqlalchemy.orm import relationship
from .database import Base


def _uuid():
    return str(uuid.uuid4())


class Account(Base):
    __tablename__ = "accounts"
    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    plan_tier = Column(String, default="core")
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    locations = relationship("Location", back_populates="account")
    users = relationship("User", back_populates="account")


class Location(Base):
    __tablename__ = "locations"
    id = Column(String, primary_key=True, default=_uuid)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    name = Column(String, nullable=False)
    timezone = Column(String, default="America/Chicago")
    city = Column(String)
    state = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    account = relationship("Account", back_populates="locations")
    customers = relationship("Customer", back_populates="location")


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_uuid)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    email = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, default="tech")
    password_hash = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("Account", back_populates="users")


class Customer(Base):
    __tablename__ = "customers"
    id = Column(String, primary_key=True, default=_uuid)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    location_id = Column(String, ForeignKey("locations.id"), nullable=False)

    name = Column(String, nullable=False)
    phone = Column(String)
    email = Column(String)

    billing_address = Column(JSON, nullable=True)
    service_address = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    location = relationship("Location", back_populates="customers")
    leads = relationship("Lead", back_populates="customer")
    quotes = relationship("Quote", back_populates="customer")


class Lead(Base):
    __tablename__ = "leads"
    id = Column(String, primary_key=True, default=_uuid)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    location_id = Column(String, ForeignKey("locations.id"), nullable=False)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=True)

    status = Column(String, default="new")  # new/working/scheduled/closed
    source = Column(String, nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text)

    assigned_to_user_id = Column(String, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="leads")
    attribution = relationship("LeadAttribution", uselist=False, back_populates="lead")


class LeadAttribution(Base):
    __tablename__ = "lead_attribution"
    id = Column(String, primary_key=True, default=_uuid)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)

    gclid = Column(String)
    utm_source = Column(String)
    utm_medium = Column(String)
    utm_campaign = Column(String)
    utm_term = Column(String)
    landing_url = Column(Text)
    referrer = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead", back_populates="attribution")


class Quote(Base):
    __tablename__ = "quotes"
    id = Column(String, primary_key=True, default=_uuid)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    location_id = Column(String, ForeignKey("locations.id"), nullable=False)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)

    version = Column(Integer, default=1)
    status = Column(String, default="draft")  # draft/sent/approved/rejected
    title = Column(String, nullable=False)

    total_price = Column(Numeric(12, 2), default=0)
    total_cost = Column(Numeric(12, 2), default=0)
    margin_percent = Column(Numeric(5, 2), default=0)

    selling_tech_id = Column(String, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="quotes")
    line_items = relationship("QuoteLineItem", back_populates="quote", cascade="all, delete-orphan")


class QuoteLineItem(Base):
    __tablename__ = "quote_line_items"
    id = Column(String, primary_key=True, default=_uuid)
    quote_id = Column(String, ForeignKey("quotes.id"), nullable=False)

    type = Column(String, default="material")  # labor/material/fee/discount
    code = Column(String)
    description = Column(String, nullable=False)
    qty = Column(Numeric(10, 2), default=1)
    unit_cost = Column(Numeric(12, 2), default=0)
    unit_price = Column(Numeric(12, 2), default=0)
    position = Column(Integer, default=0)

    quote = relationship("Quote", back_populates="line_items")


class ActivityEvent(Base):
    __tablename__ = "activity_events"
    id = Column(String, primary_key=True, default=_uuid)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)

    customer_id = Column(String, ForeignKey("customers.id"), nullable=True)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=True)
    quote_id = Column(String, ForeignKey("quotes.id"), nullable=True)

    actor_type = Column(String)  # user/system/customer
    actor_id = Column(String, nullable=True)
    event_type = Column(String, nullable=False)
    payload = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow)
