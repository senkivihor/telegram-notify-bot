import importlib
import os
from unittest.mock import patch

import infrastructure.database as database

from sqlalchemy.pool import StaticPool


def _reload_database_module():
    """Reloads the database module so engine creation runs with current env + patches."""
    importlib.reload(database)
    return database


def _restore_database_module(original_url: str | None):
    if original_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = original_url
    _reload_database_module()


def test_postgres_engine_uses_pre_ping_and_keepalives():
    original_url = os.environ.get("DATABASE_URL")

    try:
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql+psycopg2://user:pass@localhost/db?sslmode=require"},
        ):
            with patch("sqlalchemy.create_engine") as mock_engine:
                _reload_database_module()

                assert mock_engine.call_count == 1
                _, kwargs = mock_engine.call_args

                assert kwargs["pool_pre_ping"] is True
                assert kwargs["pool_recycle"] == 1800
                assert kwargs["connect_args"] == {
                    "keepalives": 1,
                    "keepalives_idle": 30,
                    "keepalives_interval": 10,
                    "keepalives_count": 5,
                }
    finally:
        _restore_database_module(original_url)


def test_sqlite_memory_uses_static_pool_without_pre_ping():
    original_url = os.environ.get("DATABASE_URL")

    try:
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:"}):
            with patch("sqlalchemy.create_engine") as mock_engine:
                _reload_database_module()

                assert mock_engine.call_count == 1
                _, kwargs = mock_engine.call_args

                assert kwargs["connect_args"] == {"check_same_thread": False}
                assert kwargs["poolclass"] is StaticPool
                assert "pool_pre_ping" not in kwargs
                assert "pool_recycle" not in kwargs
    finally:
        _restore_database_module(original_url)
