import re
import secrets

from passlib.context import CryptContext

from database.db import (
    create_auth_session,
    create_user,
    delete_auth_session,
    get_user_by_email,
    get_user_by_id,
    get_user_by_session_token,
    update_user_password_hash
)


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


def normalize_email(email):
    return (email or "").strip().lower()


def is_valid_email(email):
    return bool(EMAIL_PATTERN.match(normalize_email(email)))


def hash_password(password):
    return PASSWORD_CONTEXT.hash(password)


def verify_password(password, password_hash):
    if not password_hash:
        return False

    try:
        return PASSWORD_CONTEXT.verify(password, password_hash)
    except (ValueError, TypeError):
        return verify_legacy_pbkdf2_password(password, password_hash)


def verify_legacy_pbkdf2_password(password, password_hash):
    import base64
    import hashlib
    import hmac

    try:
        algorithm, iterations, salt, stored_digest = password_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        base64.b64decode(salt.encode("ascii")),
        int(iterations)
    )

    return hmac.compare_digest(
        base64.b64encode(digest).decode("ascii"),
        stored_digest
    )


def is_bcrypt_hash(password_hash):
    return str(password_hash or "").startswith(("$2a$", "$2b$", "$2y$"))


def register_user(email, password, name=""):
    normalized_email = normalize_email(email)

    if not is_valid_email(normalized_email):
        return None, "Введите корректный email."

    if len(password or "") < 8:
        return None, "Пароль должен быть не короче 8 символов."

    user_id = create_user(normalized_email, hash_password(password), name=name)

    if not user_id:
        return None, "Пользователь с таким email уже существует."

    return get_public_user(user_id), None


def authenticate_user(email, password):
    user = get_user_by_email(normalize_email(email))

    if not user:
        return None

    user_id, user_name, user_email, password_hash, created_at = user

    if not verify_password(password or "", password_hash):
        return None

    if not is_bcrypt_hash(password_hash):
        update_user_password_hash(user_id, hash_password(password))

    return {
        "id": user_id,
        "name": user_name or user_email.split("@")[0],
        "email": user_email,
        "created_at": created_at
    }


def get_public_user(user_id):
    user = get_user_by_id(user_id)

    if not user:
        return None

    return {
        "id": user[0],
        "name": user[1] or user[2].split("@")[0],
        "email": user[2],
        "created_at": user[3]
    }


def create_remember_session(user_id):
    token = secrets.token_urlsafe(32)
    create_auth_session(user_id, token)
    return token


def get_user_by_remember_token(token):
    if not token:
        return None

    user = get_user_by_session_token(token)

    if not user:
        return None

    return {
        "id": user[0],
        "name": user[1] or user[2].split("@")[0],
        "email": user[2],
        "created_at": user[3]
    }


def revoke_remember_session(token):
    if token:
        delete_auth_session(token)
