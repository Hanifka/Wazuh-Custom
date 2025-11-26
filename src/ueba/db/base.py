from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

load_dotenv()

Base = declarative_base()


def _create_engine(database_url: str):
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(
        database_url,
        connect_args=connect_args,
        future=True,
        pool_pre_ping=True,
    )


@lru_cache()
def get_engine(database_url: Optional[str] = None):
    url = database_url or os.getenv("DATABASE_URL", "sqlite:///./ueba.db")
    return _create_engine(url)


def get_session_factory(database_url: Optional[str] = None):
    engine = get_engine(database_url)
    return scoped_session(
        sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    )


SessionLocal = get_session_factory()
