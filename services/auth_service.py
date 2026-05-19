import base64
import hashlib
import hmac
import os
import re

from database.db import create_user, get_user_by_email, get_user_by_id


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
HASH_ITERATIONS = 260_000


def normalize_email(email):
    return (email or "").strip().lower()


def is_valid_email(email):
    return bool(EMAIL_PATTERN.match(normalize_email(email)))


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        HASH_ITERATIONS
    )

    return "pbkdf2_sha256${}${}${}".format(
        HASH_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii")
    )


def verify_password(password, password_hash):
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


def register_user(email, password):
    normalized_email = normalize_email(email)

    if not is_valid_email(normalized_email):
        return None, "Введите корректный email."

    if len(password or "") < 8:
        return None, "Пароль должен быть не короче 8 символов."

    user_id = create_user(normalized_email, hash_password(password))

    if not user_id:
        return None, "Пользователь с таким email уже существует."

    return get_public_user(user_id), None


def authenticate_user(email, password):
    user = get_user_by_email(normalize_email(email))

    if not user:
        return None

    user_id, user_email, password_hash, created_at = user

    if not verify_password(password or "", password_hash):
        return None

    return {
        "id": user_id,
        "email": user_email,
        "created_at": created_at
    }


def get_public_user(user_id):
    user = get_user_by_id(user_id)

    if not user:
        return None

    return {
        "id": user[0],
        "email": user[1],
        "created_at": user[2]
    }
