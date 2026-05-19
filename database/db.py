import sqlite3
from pathlib import Path

from config.settings import SQLITE_DB_PATH


DB_PATH = Path(SQLITE_DB_PATH)


def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            yandex_host TEXT,
            google_property TEXT,
            yandex_reviews_url TEXT,
            google_reviews_url TEXT,
            twogis_reviews_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_url TEXT NOT NULL,
            audit_type TEXT NOT NULL,
            seo_score INTEGER NOT NULL,
            errors_count INTEGER NOT NULL,
            title TEXT,
            description TEXT,
            canonical TEXT,
            h1 TEXT,
            robots_txt TEXT,
            sitemap TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    columns_to_add = [
        ("yandex_reviews_url", "TEXT"),
        ("google_reviews_url", "TEXT"),
        ("twogis_reviews_url", "TEXT")
    ]

    cursor.execute("PRAGMA table_info(sites)")
    existing_columns = [column[1] for column in cursor.fetchall()]

    for column_name, column_type in columns_to_add:
        if column_name not in existing_columns:
            cursor.execute(f"ALTER TABLE sites ADD COLUMN {column_name} {column_type}")

    conn.commit()
    conn.close()


def add_site(
    name,
    url,
    yandex_host,
    google_property,
    yandex_reviews_url="",
    google_reviews_url="",
    twogis_reviews_url=""
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO sites
        (
            name,
            url,
            yandex_host,
            google_property,
            yandex_reviews_url,
            google_reviews_url,
            twogis_reviews_url
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        url,
        yandex_host,
        google_property,
        yandex_reviews_url,
        google_reviews_url,
        twogis_reviews_url
    ))

    conn.commit()
    conn.close()


def get_sites():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            url,
            yandex_host,
            google_property,
            yandex_reviews_url,
            google_reviews_url,
            twogis_reviews_url,
            created_at
        FROM sites
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    return rows


def save_audit_result(
    site_url,
    audit_type,
    seo_score,
    errors_count,
    title,
    description,
    canonical,
    h1,
    robots_txt,
    sitemap
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO audit_history
        (
            site_url,
            audit_type,
            seo_score,
            errors_count,
            title,
            description,
            canonical,
            h1,
            robots_txt,
            sitemap
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        site_url,
        audit_type,
        seo_score,
        errors_count,
        title,
        description,
        canonical,
        h1,
        robots_txt,
        sitemap
    ))

    conn.commit()
    conn.close()


def get_audit_history():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            site_url,
            audit_type,
            seo_score,
            errors_count,
            title,
            description,
            canonical,
            h1,
            robots_txt,
            sitemap,
            created_at
        FROM audit_history
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    return rows
