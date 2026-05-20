import sqlite3
from pathlib import Path

from config.settings import SQLITE_DB_PATH


DB_PATH = Path(SQLITE_DB_PATH)


def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return column_name in [column[1] for column in cursor.fetchall()]


def migrate_sites_unique_url(cursor):
    cursor.execute("PRAGMA index_list(sites)")
    indexes = cursor.fetchall()

    has_global_unique_url = False

    for index in indexes:
        index_name = index[1]
        is_unique = index[2]

        if not is_unique:
            continue

        cursor.execute(f"PRAGMA index_info({index_name})")
        index_columns = [column[2] for column in cursor.fetchall()]

        if index_columns == ["url"]:
            has_global_unique_url = True
            break

    if not has_global_unique_url:
        return

    cursor.execute("ALTER TABLE sites RENAME TO sites_legacy")
    cursor.execute("""
        CREATE TABLE sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            yandex_host TEXT,
            google_property TEXT,
            yandex_reviews_url TEXT,
            google_reviews_url TEXT,
            twogis_reviews_url TEXT,
            yandex_webmaster_connected INTEGER DEFAULT 0,
            yandex_webmaster_token TEXT,
            yandex_webmaster_connected_at TIMESTAMP,
            yandex_metrika_connected INTEGER DEFAULT 0,
            yandex_metrika_token TEXT,
            yandex_metrika_connected_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("PRAGMA table_info(sites_legacy)")
    legacy_columns = [column[1] for column in cursor.fetchall()]
    target_columns = [
        "id",
        "user_id",
        "name",
        "url",
        "yandex_host",
        "google_property",
        "yandex_reviews_url",
        "google_reviews_url",
        "twogis_reviews_url",
        "yandex_webmaster_connected",
        "yandex_webmaster_token",
        "yandex_webmaster_connected_at",
        "yandex_metrika_connected",
        "yandex_metrika_token",
        "yandex_metrika_connected_at",
        "created_at"
    ]
    copy_columns = [column for column in target_columns if column in legacy_columns]

    cursor.execute(f"""
        INSERT INTO sites ({", ".join(copy_columns)})
        SELECT {", ".join(copy_columns)}
        FROM sites_legacy
    """)
    cursor.execute("DROP TABLE sites_legacy")


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            yandex_host TEXT,
            google_property TEXT,
            yandex_reviews_url TEXT,
            google_reviews_url TEXT,
            twogis_reviews_url TEXT,
            yandex_webmaster_connected INTEGER DEFAULT 0,
            yandex_webmaster_token TEXT,
            yandex_webmaster_connected_at TIMESTAMP,
            yandex_metrika_connected INTEGER DEFAULT 0,
            yandex_metrika_token TEXT,
            yandex_metrika_connected_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    migrate_sites_unique_url(cursor)

    if not column_exists(cursor, "sites", "user_id"):
        cursor.execute("ALTER TABLE sites ADD COLUMN user_id INTEGER")

    if not column_exists(cursor, "audit_history", "user_id"):
        cursor.execute("ALTER TABLE audit_history ADD COLUMN user_id INTEGER")

    columns_to_add = [
        ("yandex_reviews_url", "TEXT"),
        ("google_reviews_url", "TEXT"),
        ("twogis_reviews_url", "TEXT"),
        ("yandex_webmaster_connected", "INTEGER DEFAULT 0"),
        ("yandex_webmaster_token", "TEXT"),
        ("yandex_webmaster_connected_at", "TIMESTAMP"),
        ("yandex_metrika_connected", "INTEGER DEFAULT 0"),
        ("yandex_metrika_token", "TEXT"),
        ("yandex_metrika_connected_at", "TIMESTAMP")
    ]

    cursor.execute("PRAGMA table_info(sites)")
    existing_columns = [column[1] for column in cursor.fetchall()]

    for column_name, column_type in columns_to_add:
        if column_name not in existing_columns:
            cursor.execute(f"ALTER TABLE sites ADD COLUMN {column_name} {column_type}")

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_sites_user_url
        ON sites(user_id, url)
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_history_user ON audit_history(user_id)")

    conn.commit()
    conn.close()


def create_user(email, password_hash):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO users (email, password_hash)
            VALUES (?, ?)
        """, (email.strip().lower(), password_hash))
        conn.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        user_id = None

    conn.close()
    return user_id


def get_user_by_email(email):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, email, password_hash, created_at
        FROM users
        WHERE email = ?
    """, (email.strip().lower(),))

    row = cursor.fetchone()
    conn.close()
    return row


def get_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, email, created_at
        FROM users
        WHERE id = ?
    """, (user_id,))

    row = cursor.fetchone()
    conn.close()
    return row


def add_site(
    name,
    url,
    yandex_host,
    google_property,
    yandex_reviews_url="",
    google_reviews_url="",
    twogis_reviews_url="",
    user_id=None
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO sites
        (
            user_id,
            name,
            url,
            yandex_host,
            google_property,
            yandex_reviews_url,
            google_reviews_url,
            twogis_reviews_url
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
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


def get_sites(user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
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
    """
    params = ()

    if user_id is not None:
        query += " WHERE user_id = ?"
        params = (user_id,)

    query += """
        ORDER BY id DESC
    """

    cursor.execute(query, params)

    rows = cursor.fetchall()
    conn.close()

    return rows


def get_site_by_id(site_id, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT
            id,
            user_id,
            name,
            url,
            yandex_host,
            google_property,
            yandex_reviews_url,
            google_reviews_url,
            twogis_reviews_url,
            yandex_webmaster_connected,
            yandex_webmaster_token,
            yandex_webmaster_connected_at,
            yandex_metrika_connected,
            yandex_metrika_token,
            yandex_metrika_connected_at,
            created_at
        FROM sites
        WHERE id = ?
    """
    params = [site_id]

    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)

    cursor.execute(query, tuple(params))
    row = cursor.fetchone()
    conn.close()
    return row


def connect_yandex_webmaster(site_id, token, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        UPDATE sites
        SET
            yandex_webmaster_connected = 1,
            yandex_webmaster_token = ?,
            yandex_webmaster_connected_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """
    params = [token, site_id]

    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)

    cursor.execute(query, tuple(params))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def disconnect_yandex_webmaster(site_id, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        UPDATE sites
        SET
            yandex_webmaster_connected = 0,
            yandex_webmaster_token = NULL,
            yandex_webmaster_connected_at = NULL
        WHERE id = ?
    """
    params = [site_id]

    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)

    cursor.execute(query, tuple(params))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def connect_yandex_metrika(site_id, token, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        UPDATE sites
        SET
            yandex_metrika_connected = 1,
            yandex_metrika_token = ?,
            yandex_metrika_connected_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """
    params = [token, site_id]

    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)

    cursor.execute(query, tuple(params))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def disconnect_yandex_metrika(site_id, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        UPDATE sites
        SET
            yandex_metrika_connected = 0,
            yandex_metrika_token = NULL,
            yandex_metrika_connected_at = NULL
        WHERE id = ?
    """
    params = [site_id]

    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)

    cursor.execute(query, tuple(params))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


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
    sitemap,
    user_id=None
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO audit_history
        (
            user_id,
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
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


def get_audit_history(user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
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
    """
    params = ()

    if user_id is not None:
        query += " WHERE user_id = ?"
        params = (user_id,)

    query += """
        ORDER BY id DESC
    """

    cursor.execute(query, params)

    rows = cursor.fetchall()
    conn.close()

    return rows
