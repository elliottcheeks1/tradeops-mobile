from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

# ---------- Customers ----------

class Address(BaseModel):
    line1: str
    city: str
    state: str
    postal_code: str

class CustomerCreate(BaseModel):
    location_id: str
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    billing_address: Optional[Address] = None
    service_address: Optional[Address] = None

class CustomerOut(BaseModel):
    id: str
    name: str
    phone: Optional[str]
    email: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# ---------- Leads ----------

class LeadAttributionIn(BaseModel):
    gclid: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_term: Optional[str] = None
    landing_url: Optional[str] = None
    referrer: Optional[str] = None

class LeadCreate(BaseModel):
    location_id: str
    customer_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    source: Optional[str] = None
    attribution: Optional[LeadAttributionIn] = None

class LeadOut(BaseModel):
    id: str
    title: str
    status: str
    source: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# ---------- Quotes ----------

class QuoteLineItemIn(BaseModel):
    type: str = "material"
    code: Optional[str] = None
    description: str
    qty: float = 1
    unit_cost: float = 0
    unit_price: float = 0
    position: int = 0

class QuoteCreate(BaseModel):
    location_id: Optional[str] = "loc-demo"  # Default for demo
    customer_id: Optional[str] = "cust-demo" # Default for demo
    title: str
    selling_tech_id: Optional[str] = None
    line_items: List[QuoteLineItemIn] = []
    status: Optional[str] = "draft"

class QuoteUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    line_items: Optional[List[QuoteLineItemIn]] = None
    customer_id: Optional[str] = None
    location_id: Optional[str] = None

class QuoteOut(BaseModel):
    id: str
    version: int
    title: str
    status: str
    total_price: float
    margin_percent: float
    customer_name: Optional[str] = None # Added for easier UI display
    created_at: datetime

    class Config:
        from_attributes = True

# ---------- Notes / Activity ----------

class NoteCreate(BaseModel):
    content: str
    author: Optional[str] = "Unknown"

class NoteOut(BaseModel):
    id: str
    content: str
    author: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class ActivityEventOut(BaseModel):
    id: str
    event_type: str
    actor_type: str
    created_at: datetime
    payload: dict = Field(default_factory=dict)

    class Config:
        from_attributes = True
