from __future__ import annotations

import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials


security = HTTPBasic()


def get_api_credentials() -> tuple[str, str]:
    """Get API credentials from environment variables."""
    username = os.getenv("UEBA_DASH_USERNAME")
    password = os.getenv("UEBA_DASH_PASSWORD")

    if not username or not password:
        raise ValueError(
            "UEBA_DASH_USERNAME and UEBA_DASH_PASSWORD environment variables must be set"
        )

    return username, password


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    """Verify HTTP Basic Auth credentials against environment variables."""
    expected_username, expected_password = get_api_credentials()

    is_username_correct = credentials.username == expected_username
    is_password_correct = credentials.password == expected_password

    if not (is_username_correct and is_password_correct):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username
