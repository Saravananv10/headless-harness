"""FastAPI application entry point for EpochLedger."""

from fastapi import FastAPI
from .router import router as experiment_router

app = FastAPI(title="EpochLedger API", version="0.1.0")

# Register API routers
app.include_router(experiment_router)

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
