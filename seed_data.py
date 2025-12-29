# seed_data.py
from app.database import engine, SessionLocal, Base
from app import models, crud, schemas

# Ensure tables exist
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# If there's already an account, assume it's seeded.
if db.query(models.Account).first():
    print("DB already seeded; skipping.")
    db.close()
    raise SystemExit()

acct = models.Account(id="acct-demo-001", name="Demo HVAC Co", plan_tier="growth")
loc = models.Location(account_id=acct.id, name="Dallas Branch", city="Dallas", state="TX")

db.add(acct)
db.add(loc)
db.commit()
db.refresh(loc)

# Customers
cust1 = crud.create_customer(
    db, acct.id,
    schemas.CustomerCreate(
        location_id=loc.id,
        name="Brenda Caulfield",
        phone="555-0100",
        email="brenda@example.com",
    )
)

cust2 = crud.create_customer(
    db, acct.id,
    schemas.CustomerCreate(
        location_id=loc.id,
        name="Kevin Parker",
        phone="555-0101",
        email="kevin@example.com",
    )
)

# Lead with attribution
lead1 = crud.create_lead(
    db, acct.id,
    schemas.LeadCreate(
        location_id=loc.id,
        customer_id=cust1.id,
        title="AC not cooling",
        description="3-ton unit, upstairs, 15 years old",
        source="google_ads",
        attribution=schemas.LeadAttributionIn(
            utm_source="google",
            utm_medium="cpc",
            utm_campaign="ac_repair_dallas",
            utm_term="ac repair dallas"
        )
    )
)

# Quote for Brenda
quote = crud.create_quote(
    db, acct.id,
    schemas.QuoteCreate(
        location_id=loc.id,
        customer_id=cust1.id,
        title="System replacement - 3 ton",
        line_items=[
            schemas.QuoteLineItemIn(
                type="material",
                code="AC-16SEER-3T",
                description="16 SEER 3-ton condenser + coil",
                qty=1,
                unit_cost=1800,
                unit_price=3200,
            ),
            schemas.QuoteLineItemIn(
                type="labor",
                code="LAB-AC-INSTALL",
                description="Install labor (2 techs, 1 day)",
                qty=1,
                unit_cost=600,
                unit_price=1400,
            )
        ]
    )
)

db.close()
print("Seed complete.")
