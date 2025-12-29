from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="TradeOps API",
    version="0.1.0",
    description="Backend for TradeOps mobile & web apps",
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Root (Render hits this) ---
@app.get("/")
def root():
    return {
        "service": "TradeOps API",
        "status": "ok",
        "docs": "/docs",
        "endpoints": ["/health", "/quotes"],
    }


# --- Health ---
@app.get("/health")
def health():
    return {"status": "ok"}


# --- Mock quotes ---
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
    return MOCK_QUOTES
