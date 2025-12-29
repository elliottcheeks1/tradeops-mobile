# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="TradeOps API",
    version="0.1.0",
    description="Backend for TradeOps mobile & web apps",
)

# --- CORS (allow your future frontends to call this API) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later (e.g. your domain)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Simple healthcheck ---
@app.get("/health")
def health():
    return {"status": "ok"}


# --- Mock quotes endpoint (for now, no DB needed) ---
MOCK_QUOTES = [
    {
        "id": "QDEMO1",
        "customer_name": "Mrs. Jones",
        "total": 1850.00,
        "status": "Open",
    },
    {
        "id": "QDEMO2",
        "customer_name": "ACME Rentals",
        "total": 3250.00,
        "status": "Won",
    },
]


@app.get("/quotes")
def list_quotes():
    """Temporary mock quotes-list until Neon is wired in."""
    return MOCK_QUOTES
