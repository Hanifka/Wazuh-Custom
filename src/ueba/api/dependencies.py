from __future__ import annotations

from typing import Generator

from fastapi import Depends
from sqlalchemy.orm import Session, scoped_session

from ueba.db.base import get_session_factory


def get_session_factory_instance() -> scoped_session:
    """Return the global session factory."""
    return get_session_factory()


def get_session(
    factory: scoped_session = Depends(get_session_factory_instance),
) -> Generator[Session, None, None]:
    """Provide a database session for each request."""
    session = factory()
    try:
        yield session
    finally:
        session.close()
