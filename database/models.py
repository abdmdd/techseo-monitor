from sqlalchemy import Column, Integer, String, Text

from database.base import Base


# ==================================================
# INACTIVE SQLALCHEMY MODELS
# ==================================================
#
# These models are intentionally not used by the active runtime yet.
# The current MVP database layer is database/db.py with sqlite3.
# Keep column names aligned with the SQLite schema to reduce migration risk.


class Site(Base):
    __tablename__ = "sites"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    url = Column(String)
    yandex_host = Column(String)
    google_property = Column(String)
    yandex_reviews_url = Column(Text)
    google_reviews_url = Column(Text)
    twogis_reviews_url = Column(Text)
    created_at = Column(String)


class AuditHistory(Base):
    __tablename__ = "audit_history"

    id = Column(Integer, primary_key=True, index=True)
    site_url = Column(String)
    audit_type = Column(String)
    seo_score = Column(Integer)
    errors_count = Column(Integer)
    title = Column(Text)
    description = Column(Text)
    canonical = Column(Text)
    h1 = Column(Text)
    robots_txt = Column(Text)
    sitemap = Column(Text)
    created_at = Column(String)
