from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel

from ueba.api.auth import get_api_credentials
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

# Mount static files
static_path = os.path.join(os.path.dirname(__file__), '../../..', 'static')
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

# Setup Jinja2 templates
template_path = os.path.join(os.path.dirname(__file__), '../../..', 'templates')
jinja_env = Environment(
    loader=FileSystemLoader(template_path),
    autoescape=True,
)


class LoginRequest(BaseModel):
    """Request model for login endpoint."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Response model for login endpoint."""
    session_token: str
    message: str


# Session token storage (in production, use Redis or database)
_session_tokens = {}


@app.post("/login", response_model=LoginResponse)
def login(request: LoginRequest) -> LoginResponse:
    """
    Login endpoint to create a session token.
    
    Validates credentials against environment variables and returns a session token
    that can be used in subsequent requests via Bearer token or stored as a cookie.
    """
    expected_username, expected_password = get_api_credentials()

    if request.username != expected_username or request.password != expected_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Generate a secure session token
    session_token = secrets.token_urlsafe(32)
    _session_tokens[session_token] = {
        "username": request.username,
        "created_at": datetime.now(timezone.utc),
    }

    return LoginResponse(
        session_token=session_token,
        message=f"Successfully logged in as {request.username}",
    )


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """
    Serve the UEBA Dashboard HTML.
    
    This is the main dashboard interface that loads from templates/dashboard.html.
    """
    try:
        template = jinja_env.get_template("dashboard.html")
        html_content = template.render()
        return html_content
    except Exception as e:
        return f"<h1>Error loading dashboard: {str(e)}</h1>", 500


# Include routers
app.include_router(health.router)
app.include_router(entities.router)
app.include_router(events.router)
app.include_router(feedback.router)
