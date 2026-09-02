import os
import hashlib
import hmac
import secrets

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import User

PORTAL_LOGIN = os.environ.get("EDU_PORTAL_LOGIN", "admin")
PORTAL_PASSWORD = os.environ.get("EDU_PORTAL_PASSWORD")
AUTH_ENABLED = bool(PORTAL_PASSWORD)

SECRET_KEY = os.environ.get("EDU_PORTAL_SECRET_KEY") or os.urandom(32).hex()

PUBLIC_PATHS = {"/login"}
PUBLIC_PREFIXES = ("/static",)


def is_authenticated(request: Request) -> bool:
    if not AUTH_ENABLED:
        return True
    return isinstance(request.session.get("user_id"), int)


def is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"pbkdf2_sha256$240000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def current_user_id(request: Request) -> int | None:
    user_id = request.session.get("user_id")
    if isinstance(user_id, int):
        return user_id
    if AUTH_ENABLED:
        # No session yet -- caller must treat this as "not logged in", not fall
        # back to some default account (that caused GET /login to always think
        # a user was already signed in, redirecting back to "/" in a loop).
        return None
    return 1


def current_user(db: Session, request: Request) -> User | None:
    user_id = current_user_id(request)
    if user_id is None:
        return None
    return db.query(User).get(user_id)


def ensure_bootstrap_user(db: Session) -> None:
    """Create the primary account (EDU_PORTAL_LOGIN/EDU_PORTAL_PASSWORD) if the
    users table is still empty. This is the single source of truth for that
    account's password -- it's never overwritten here on later startups, so
    changing it means updating the DB directly, not just the env var.
    """
    if not AUTH_ENABLED:
        return
    if db.query(User).count() > 0:
        return
    db.add(User(username=PORTAL_LOGIN, password_hash=hash_password(PORTAL_PASSWORD or "")))
    db.commit()


def ensure_extra_users(db: Session) -> None:
    """Create any additional family accounts defined via env vars, if they
    don't exist yet. Real passwords must never be hardcoded here (this repo
    is public) -- add one env var per extra account:
      EDU_EXTRA_USER_<N>=<username>:<display name>
      EDU_EXTRA_PASSWORD_<N>=<password>
    """
    i = 1
    while True:
        spec = os.environ.get(f"EDU_EXTRA_USER_{i}")
        password = os.environ.get(f"EDU_EXTRA_PASSWORD_{i}")
        if not spec:
            break
        i += 1
        if not password:
            continue
        username, _, display_name = spec.partition(":")
        username = username.strip()
        if not username:
            continue
        existing = db.query(User).filter_by(username=username).first()
        if not existing:
            db.add(
                User(
                    username=username,
                    password_hash=hash_password(password),
                    display_name=display_name.strip() or None,
                )
            )
    db.commit()
