import json
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
            name TEXT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            site_id INTEGER,
            site_url TEXT NOT NULL,
            audit_type TEXT NOT NULL DEFAULT 'monthly',
            task_id TEXT,
            status TEXT NOT NULL DEFAULT 'queued',
            progress INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            result_json TEXT,
            seo_score INTEGER,
            errors_count INTEGER,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE SET NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quarterly_audit_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            site_id INTEGER NOT NULL,
            check_key TEXT NOT NULL,
            status TEXT,
            comment TEXT,
            checked_at TEXT,
            checked_by TEXT,
            mobile_score INTEGER,
            desktop_score INTEGER,
            lcp REAL,
            inp REAL,
            cls REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quarterly_audit_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            check_id INTEGER NOT NULL,
            old_status TEXT,
            new_status TEXT,
            old_comment TEXT,
            new_comment TEXT,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            changed_by TEXT,
            FOREIGN KEY (check_id) REFERENCES quarterly_audit_checks(id) ON DELETE CASCADE
        )
    """)

    migrate_sites_unique_url(cursor)

    if not column_exists(cursor, "sites", "user_id"):
        cursor.execute("ALTER TABLE sites ADD COLUMN user_id INTEGER")

    if not column_exists(cursor, "audit_history", "user_id"):
        cursor.execute("ALTER TABLE audit_history ADD COLUMN user_id INTEGER")

    if not column_exists(cursor, "users", "name"):
        cursor.execute("ALTER TABLE users ADD COLUMN name TEXT")

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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_jobs_user_status ON audit_jobs(user_id, status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_jobs_site ON audit_jobs(site_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_jobs_task_id ON audit_jobs(task_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_token ON auth_sessions(token)")
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_quarterly_checks_unique
        ON quarterly_audit_checks(user_id, site_id, check_key)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_quarterly_checks_user_site
        ON quarterly_audit_checks(user_id, site_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_quarterly_history_check
        ON quarterly_audit_history(check_id)
    """)

    conn.commit()
    conn.close()


def _audit_job_row_to_dict(row):
    if not row:
        return None

    return {
        "id": row[0],
        "user_id": row[1],
        "site_id": row[2],
        "site_url": row[3],
        "audit_type": row[4],
        "task_id": row[5],
        "status": row[6],
        "progress": row[7],
        "error_message": row[8],
        "result": json.loads(row[9]) if row[9] else None,
        "seo_score": row[10],
        "errors_count": row[11],
        "started_at": row[12],
        "finished_at": row[13],
        "created_at": row[14],
        "updated_at": row[15],
    }


def create_audit_job(user_id, site_id, site_url, audit_type="monthly"):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO audit_jobs
        (
            user_id,
            site_id,
            site_url,
            audit_type,
            status,
            progress
        )
        VALUES (?, ?, ?, ?, 'queued', 0)
    """, (user_id, site_id, site_url, audit_type))

    conn.commit()
    job_id = cursor.lastrowid
    conn.close()
    return job_id


def set_audit_job_task_id(job_id, task_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE audit_jobs
        SET
            task_id = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (task_id, job_id))

    conn.commit()
    conn.close()


def update_audit_job(
    job_id,
    status=None,
    progress=None,
    error_message=None,
    result=None,
    seo_score=None,
    errors_count=None,
    started=False,
    finished=False
):
    fields = ["updated_at = CURRENT_TIMESTAMP"]
    params = []

    if status is not None:
        fields.append("status = ?")
        params.append(status)

    if progress is not None:
        normalized_progress = max(0, min(100, int(progress)))
        fields.append("progress = ?")
        params.append(normalized_progress)

    if error_message is not None:
        fields.append("error_message = ?")
        params.append(str(error_message))

    if result is not None:
        fields.append("result_json = ?")
        params.append(json.dumps(result, ensure_ascii=False))

    if seo_score is not None:
        fields.append("seo_score = ?")
        params.append(int(seo_score))

    if errors_count is not None:
        fields.append("errors_count = ?")
        params.append(int(errors_count))

    if started:
        fields.append("started_at = COALESCE(started_at, CURRENT_TIMESTAMP)")

    if finished:
        fields.append("finished_at = CURRENT_TIMESTAMP")

    params.append(job_id)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        UPDATE audit_jobs
        SET {", ".join(fields)}
        WHERE id = ?
    """, tuple(params))
    conn.commit()
    conn.close()


def get_audit_job(job_id, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT
            id,
            user_id,
            site_id,
            site_url,
            audit_type,
            task_id,
            status,
            progress,
            error_message,
            result_json,
            seo_score,
            errors_count,
            started_at,
            finished_at,
            created_at,
            updated_at
        FROM audit_jobs
        WHERE id = ?
    """
    params = [job_id]

    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)

    cursor.execute(query, tuple(params))
    row = cursor.fetchone()
    conn.close()
    return _audit_job_row_to_dict(row)


def get_latest_audit_job(user_id, site_url=None, audit_type="monthly"):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT
            id,
            user_id,
            site_id,
            site_url,
            audit_type,
            task_id,
            status,
            progress,
            error_message,
            result_json,
            seo_score,
            errors_count,
            started_at,
            finished_at,
            created_at,
            updated_at
        FROM audit_jobs
        WHERE user_id = ? AND audit_type = ?
    """
    params = [user_id, audit_type]

    if site_url:
        query += " AND site_url = ?"
        params.append(site_url)

    query += " ORDER BY id DESC LIMIT 1"

    cursor.execute(query, tuple(params))
    row = cursor.fetchone()
    conn.close()
    return _audit_job_row_to_dict(row)


def get_active_audit_job(user_id, site_url=None, audit_type="monthly"):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT
            id,
            user_id,
            site_id,
            site_url,
            audit_type,
            task_id,
            status,
            progress,
            error_message,
            result_json,
            seo_score,
            errors_count,
            started_at,
            finished_at,
            created_at,
            updated_at
        FROM audit_jobs
        WHERE
            user_id = ?
            AND audit_type = ?
            AND status IN ('queued', 'running')
    """
    params = [user_id, audit_type]

    if site_url:
        query += " AND site_url = ?"
        params.append(site_url)

    query += " ORDER BY id DESC LIMIT 1"

    cursor.execute(query, tuple(params))
    row = cursor.fetchone()
    conn.close()
    return _audit_job_row_to_dict(row)


def create_user(email, password_hash, name=""):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO users (name, email, password_hash)
            VALUES (?, ?, ?)
        """, (name.strip(), email.strip().lower(), password_hash))
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
        SELECT id, name, email, password_hash, created_at
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
        SELECT id, name, email, created_at
        FROM users
        WHERE id = ?
    """, (user_id,))

    row = cursor.fetchone()
    conn.close()
    return row


def update_user_password_hash(user_id, password_hash):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users
        SET password_hash = ?
        WHERE id = ?
    """, (password_hash, user_id))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def create_auth_session(user_id, token):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO auth_sessions (user_id, token)
        VALUES (?, ?)
    """, (user_id, token))
    conn.commit()
    conn.close()


def get_user_by_session_token(token):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT users.id, users.name, users.email, users.created_at
        FROM auth_sessions
        JOIN users ON users.id = auth_sessions.user_id
        WHERE auth_sessions.token = ?
    """, (token,))
    row = cursor.fetchone()

    if row:
        cursor.execute("""
            UPDATE auth_sessions
            SET last_used_at = CURRENT_TIMESTAMP
            WHERE token = ?
        """, (token,))
        conn.commit()

    conn.close()
    return row


def delete_auth_session(token):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


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


def _quarterly_check_row_to_dict(row):
    if not row:
        return None

    return {
        "id": row[0],
        "user_id": row[1],
        "site_id": row[2],
        "check_key": row[3],
        "status": row[4],
        "comment": row[5],
        "checked_at": row[6],
        "checked_by": row[7],
        "mobile_score": row[8],
        "desktop_score": row[9],
        "lcp": row[10],
        "inp": row[11],
        "cls": row[12],
        "created_at": row[13],
        "updated_at": row[14],
    }


def get_quarterly_audit_checks(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            q.id,
            q.user_id,
            q.site_id,
            q.check_key,
            q.status,
            q.comment,
            q.checked_at,
            q.checked_by,
            q.mobile_score,
            q.desktop_score,
            q.lcp,
            q.inp,
            q.cls,
            q.created_at,
            q.updated_at
        FROM quarterly_audit_checks q
        JOIN sites s ON s.id = q.site_id
        WHERE q.user_id = ? AND s.user_id = ?
        ORDER BY q.site_id, q.check_key
    """, (user_id, user_id))

    rows = cursor.fetchall()
    conn.close()
    return {
        (row[2], row[3]): _quarterly_check_row_to_dict(row)
        for row in rows
    }


def upsert_quarterly_audit_check(
    user_id,
    site_id,
    check_key,
    status,
    comment,
    checked_at,
    checked_by,
    mobile_score=None,
    desktop_score=None,
    lcp=None,
    inp=None,
    cls=None
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM sites WHERE id = ? AND user_id = ?", (site_id, user_id))
    if not cursor.fetchone():
        conn.close()
        return None

    cursor.execute("""
        SELECT
            id,
            status,
            comment
        FROM quarterly_audit_checks
        WHERE user_id = ? AND site_id = ? AND check_key = ?
    """, (user_id, site_id, check_key))
    existing = cursor.fetchone()

    normalized_status = status or "acceptable"
    normalized_comment = comment or ""
    normalized_checked_by = checked_by or ""

    if existing:
        check_id, old_status, old_comment = existing
        cursor.execute("""
            UPDATE quarterly_audit_checks
            SET
                status = ?,
                comment = ?,
                checked_at = ?,
                checked_by = ?,
                mobile_score = ?,
                desktop_score = ?,
                lcp = ?,
                inp = ?,
                cls = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            normalized_status,
            normalized_comment,
            checked_at,
            normalized_checked_by,
            mobile_score,
            desktop_score,
            lcp,
            inp,
            cls,
            check_id
        ))

        if (old_status or "") != normalized_status or (old_comment or "") != normalized_comment:
            cursor.execute("""
                INSERT INTO quarterly_audit_history
                (
                    check_id,
                    old_status,
                    new_status,
                    old_comment,
                    new_comment,
                    changed_by
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                check_id,
                old_status,
                normalized_status,
                old_comment,
                normalized_comment,
                normalized_checked_by
            ))
    else:
        cursor.execute("""
            INSERT INTO quarterly_audit_checks
            (
                user_id,
                site_id,
                check_key,
                status,
                comment,
                checked_at,
                checked_by,
                mobile_score,
                desktop_score,
                lcp,
                inp,
                cls
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            site_id,
            check_key,
            normalized_status,
            normalized_comment,
            checked_at,
            normalized_checked_by,
            mobile_score,
            desktop_score,
            lcp,
            inp,
            cls
        ))
        check_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO quarterly_audit_history
            (
                check_id,
                old_status,
                new_status,
                old_comment,
                new_comment,
                changed_by
            )
            VALUES (?, NULL, ?, NULL, ?, ?)
        """, (
            check_id,
            normalized_status,
            normalized_comment,
            normalized_checked_by
        ))

    conn.commit()
    conn.close()
    return check_id


def get_quarterly_audit_history(user_id, site_id=None, limit=80):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT
            h.id,
            h.check_id,
            q.site_id,
            q.check_key,
            h.old_status,
            h.new_status,
            h.old_comment,
            h.new_comment,
            h.changed_at,
            h.changed_by
        FROM quarterly_audit_history h
        JOIN quarterly_audit_checks q ON q.id = h.check_id
        JOIN sites s ON s.id = q.site_id
        WHERE q.user_id = ? AND s.user_id = ?
    """
    params = [user_id, user_id]

    if site_id is not None:
        query += " AND q.site_id = ?"
        params.append(site_id)

    query += " ORDER BY h.id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    return rows
