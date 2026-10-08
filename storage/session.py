"""Koneksi database. Default SQLite; ganti lewat env MONITORING_DB_URL (mis. PostgreSQL)."""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from storage.models import Base

DEFAULT_URL = "sqlite:///data/monitoring.db"


def make_engine(url: str | None = None) -> Engine:
    url = url or os.environ.get("MONITORING_DB_URL", DEFAULT_URL)
    kwargs: dict = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        path = url.replace("sqlite:///", "", 1)
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, **kwargs)


def make_session_factory(engine: Engine) -> sessionmaker:
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)