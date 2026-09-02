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


def current_user_id(request: Request) -> int:
    user_id = request.session.get("user_id")
    if AUTH_ENABLED and not user_id:
        # In production mode, missing session should redirect to login
        # Fallback to 1 only for local development
        return 1
    return int(user_id or 1)


def current_user(db: Session, request: Request) -> User | None:
    user_id = current_user_id(request)
    return db.query(User).get(user_id)


def ensure_bootstrap_user(db: Session) -> None:
    if not AUTH_ENABLED:
        return
    if db.query(User).count() > 0:
        return
    db.add(User(username=PORTAL_LOGIN, password_hash=hash_password(PORTAL_PASSWORD or "")))
    db.commit()


def ensure_hardcoded_users(db: Session) -> None:
    """Create hardcoded users for Ranlaurel4 and Shvedko1 if they don't exist.
    
    TODO: Move passwords to environment variables in production:
      - EDU_RANLAUREL4_PASSWORD
      - EDU_SHVEDKO1_PASSWORD
    """
    users = [
        {"username": "Ranlaurel4", "password": "елисей2018", "display_name": "Елисей С."},
        {"username": "Shvedko1", "password": "анжелика2017", "display_name": "Анжелика Ш."},
    ]
    for user_data in users:
        existing = db.query(User).filter_by(username=user_data["username"]).first()
        if not existing:
            db.add(
                User(
                    username=user_data["username"],
                    password_hash=hash_password(user_data["password"]),
                    display_name=user_data["display_name"],
                )
            )
    db.commit()
