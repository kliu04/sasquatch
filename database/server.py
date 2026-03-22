"""Sasquatch unified API server.

Wires together auth, database, GCS storage, scan worker, and all routers.
Run with: uvicorn database.server:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database.routers import climbs, users, walls
from database.scan_worker import ScanWorker
from database.storage import GCSStorage


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize shared services
    storage = GCSStorage()
    worker = ScanWorker(storage)

    # Inject dependencies into routers
    walls.configure(storage, worker)
    climbs.configure(storage, worker)

    # Store on app state for access if needed
    app.state.storage = storage
    app.state.worker = worker

    yield

    # Shutdown: nothing to clean up


app = FastAPI(title="Sasquatch API", lifespan=lifespan)

# CORS — allow all for mobile app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(walls.router)
app.include_router(climbs.router)
app.include_router(users.router)


@app.get("/health")
def health():
    return {"status": "ok"}
