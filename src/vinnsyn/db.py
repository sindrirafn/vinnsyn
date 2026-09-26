"""Database access for Vinnsyn's independent public-market archive."""
from __future__ import annotations

import os
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from urllib.parse import urlparse

from dotenv import load_dotenv


_transaction_connection = ContextVar("vinnsyn_transaction", default=None)


def get_database_url() -> str:
    """Read the Vinnsyn database URL without falling back to another product."""
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and configure the Vinnsyn database.")
    if "your_username" in database_url or "your_password" in database_url:
        raise RuntimeError("DATABASE_URL still contains placeholder values.")
    if urlparse(database_url).path.rstrip("/") != "/vinnsyn":
        raise RuntimeError("DATABASE_URL must point to the standalone vinsyn database.")
    return database_url


def connect():
    """Open a database connection, reusing the current transaction when present."""
    import psycopg

    connection = _transaction_connection.get()
    if connection is not None:
        return nullcontext(connection)
    return psycopg.connect(get_database_url())


@contextmanager
def transaction():
    """Run a unit of work in Vinnsyn's own database."""
    with connect() as connection:
        with connection.transaction():
            if _transaction_connection.get() is None:
                connection.execute("select pg_advisory_xact_lock(355551878)")
            token = _transaction_connection.set(connection)
            try:
                yield connection
            finally:
                _transaction_connection.reset(token)
