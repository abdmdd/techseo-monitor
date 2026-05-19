"""
Inactive SQLAlchemy base.

The active MVP runtime uses sqlite3 through database/db.py. This base is kept
only for a future SQLAlchemy/PostgreSQL migration.
"""

from sqlalchemy.orm import declarative_base


Base = declarative_base()
