import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests

from config.settings import YANDEX_CLIENT_ID, YANDEX_CLIENT_SECRET, YANDEX_REDIRECT_URI
from database.db import get_connection


YANDEX_AUTH_URL = "https://oauth.yandex.ru/authorize"
YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token"
YANDEX_SERVICE_WEBMASTER = "webmaster"
OAUTH_TIMEOUT = 20
STATE_MAX_AGE_SECONDS = 900


def _state_secret():
    secret = (YANDEX_CLIENT_SECRET or YANDEX_CLIENT_ID or "").strip()
    if not secret:
        raise ValueError("Yandex OAuth credentials are not configured.")
    return secret.encode("utf-8")


def _b64_encode(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64_decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _sign_state(payload):
    raw_payload = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded_payload = _b64_encode(raw_payload)
    signature = hmac.new(_state_secret(), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded_payload}.{_b64_encode(signature)}"


def _verify_state(state):
    try:
        encoded_payload, encoded_signature = str(state or "").split(".", 1)
        expected_signature = hmac.new(
            _state_secret(),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        actual_signature = _b64_decode(encoded_signature)
        if not hmac.compare_digest(expected_signature, actual_signature):
            return None

        payload = json.loads(_b64_decode(encoded_payload).decode("utf-8"))
        issued_at = int(payload.get("iat", 0))
        if issued_at < int(time.time()) - STATE_MAX_AGE_SECONDS:
            return None

        return {
            "user_id": int(payload["user_id"]),
            "site_id": int(payload["site_id"]),
        }
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def parse_yandex_oauth_state(state):
    return _verify_state(state)


def _ensure_site_owner(user_id, site_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM sites WHERE id = ? AND user_id = ?", (site_id, user_id))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def _expires_at(tokens):
    expires_in = tokens.get("expires_in")
    if not expires_in:
        return None

    try:
        seconds = int(expires_in)
    except (TypeError, ValueError):
        return None

    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def get_yandex_redirect_uri():
    return YANDEX_REDIRECT_URI


def generate_yandex_auth_url(user_id, site_id):
    redirect_uri = get_yandex_redirect_uri()

    if not YANDEX_CLIENT_ID or not redirect_uri:
        raise ValueError("Yandex OAuth credentials are not configured.")

    if not _ensure_site_owner(user_id, site_id):
        raise ValueError("Site was not found or does not belong to the current user.")

    state = _sign_state({
        "user_id": int(user_id),
        "site_id": int(site_id),
        "iat": int(time.time()),
    })
    query = urlencode({
        "response_type": "code",
        "client_id": YANDEX_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "state": state,
    })
    return f"{YANDEX_AUTH_URL}?{query}"


def exchange_code_for_token(code):
    if not code:
        raise ValueError("OAuth code is required.")
    if not YANDEX_CLIENT_ID or not YANDEX_CLIENT_SECRET:
        raise ValueError("Yandex OAuth credentials are not configured.")

    response = requests.post(
        YANDEX_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": YANDEX_CLIENT_ID,
            "client_secret": YANDEX_CLIENT_SECRET,
        },
        timeout=OAUTH_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def refresh_access_token(refresh_token):
    if not refresh_token:
        raise ValueError("Refresh token is required.")
    if not YANDEX_CLIENT_ID or not YANDEX_CLIENT_SECRET:
        raise ValueError("Yandex OAuth credentials are not configured.")

    response = requests.post(
        YANDEX_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": YANDEX_CLIENT_ID,
            "client_secret": YANDEX_CLIENT_SECRET,
        },
        timeout=OAUTH_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def save_yandex_integration(user_id, site_id, tokens):
    if not _ensure_site_owner(user_id, site_id):
        return False

    access_token = tokens.get("access_token")
    if not access_token:
        return False

    refresh_token = tokens.get("refresh_token")
    expires_at = _expires_at(tokens)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO yandex_integrations
        (
            user_id,
            site_id,
            service_type,
            access_token,
            refresh_token,
            expires_at,
            connected_at,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 'connected')
        ON CONFLICT(user_id, site_id, service_type)
        DO UPDATE SET
            access_token = excluded.access_token,
            refresh_token = COALESCE(excluded.refresh_token, yandex_integrations.refresh_token),
            expires_at = excluded.expires_at,
            connected_at = CURRENT_TIMESTAMP,
            status = 'connected'
    """, (
        user_id,
        site_id,
        YANDEX_SERVICE_WEBMASTER,
        access_token,
        refresh_token,
        expires_at,
    ))
    conn.commit()
    conn.close()
    return True


def get_yandex_integration_status(user_id, site_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            status,
            connected_at,
            expires_at,
            access_token,
            refresh_token
        FROM yandex_integrations
        WHERE user_id = ? AND site_id = ? AND service_type = ?
        LIMIT 1
    """, (user_id, site_id, YANDEX_SERVICE_WEBMASTER))
    row = cursor.fetchone()
    conn.close()

    if not row or row[0] != "connected":
        return {
            "connected": False,
            "status": row[0] if row else "disconnected",
            "connected_at": None,
            "expires_at": None,
            "token_status": "missing",
        }

    return {
        "connected": True,
        "status": row[0],
        "connected_at": row[1],
        "expires_at": row[2],
        "token_status": "stored" if row[3] else "missing",
        "has_refresh_token": bool(row[4]),
    }


def disconnect_yandex_integration(user_id, site_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE yandex_integrations
        SET
            access_token = NULL,
            refresh_token = NULL,
            expires_at = NULL,
            status = 'disconnected'
        WHERE user_id = ? AND site_id = ? AND service_type = ?
    """, (user_id, site_id, YANDEX_SERVICE_WEBMASTER))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0
