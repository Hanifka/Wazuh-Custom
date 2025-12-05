from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ueba.api.routers import entities, events, feedback, health

app = FastAPI(
    title="UEBA Dashboard API",
    description="Backend API for UEBA User and Entity Behavior Analytics Dashboard",
    version="0.1.0",
)

# Add CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(entities.router)
app.include_router(events.router)
app.include_router(feedback.router)


@app.get("/")
def root():
    """Root endpoint with basic info."""
    return {
        "message": "UEBA Dashboard API",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }
