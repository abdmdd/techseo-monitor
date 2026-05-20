from database.db import (
    connect_yandex_metrika,
    disconnect_yandex_metrika,
    get_site_by_id,
)


def get_connection_status(site_id, user_id=None):
    site = get_site_by_id(site_id, user_id=user_id)

    if not site:
        return {
            "connected": False,
            "connected_at": None,
            "token_status": "site_not_found"
        }

    return {
        "connected": bool(site[12]),
        "connected_at": site[14],
        "token_status": "stored" if site[13] else "missing"
    }


def connect(site_id, token, user_id=None):
    if not token:
        return False, "OAuth token is required."

    connected = connect_yandex_metrika(
        site_id=site_id,
        token=token,
        user_id=user_id
    )

    if not connected:
        return False, "Site was not found or does not belong to the current user."

    return True, None


def disconnect(site_id, user_id=None):
    disconnected = disconnect_yandex_metrika(
        site_id=site_id,
        user_id=user_id
    )

    if not disconnected:
        return False, "Site was not found or does not belong to the current user."

    return True, None
