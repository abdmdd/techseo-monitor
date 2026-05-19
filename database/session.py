"""
Inactive SQLAlchemy foundation.

The production-ready MVP currently uses database/db.py as the single active
SQLite layer. This module is kept as a placeholder for a future PostgreSQL /
SQLAlchemy migration, but it must not create engines or sessions at import time.
"""

SessionLocal = None
engine = None


def get_session():
    raise RuntimeError(
        "SQLAlchemy runtime is disabled. Use database.db for the active SQLite layer."
    )
