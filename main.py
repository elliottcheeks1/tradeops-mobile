from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.wsgi import WSGIMiddleware
from frontend_app import dash_app  # <-- import the Dash app

app = FastAPI(
    title="TradeOps API",
    description="Backend API + Dash UI",
    version="0.1.0"
)

# Allow frontend UI & local dev to call API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoint
@app.get("/health")
def health_check():
    return {"status": "healthy"}

# Root response - API metadata
@app.get("/")
def root():
    return JSONResponse({
        "service": "TradeOps API",
        "status": "ok",
        "docs": "/docs",
        "endpoints": ["/health", "/quotes", "/app"]
    })

# ---- Mount the Dash UI here ---- #
# Dash is exposed at: https://tradeops.onrender.com/app
app.mount("/app", WSGIMiddleware(dash_app.server))
# -------------------------------- #

# (If you added quotes endpoints, they remain unchanged)
