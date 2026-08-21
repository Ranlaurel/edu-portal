import os

from fastapi import Request

PORTAL_LOGIN = os.environ.get("EDU_PORTAL_LOGIN", "admin")
PORTAL_PASSWORD = os.environ.get("EDU_PORTAL_PASSWORD")
AUTH_ENABLED = bool(PORTAL_PASSWORD)

SECRET_KEY = os.environ.get("EDU_PORTAL_SECRET_KEY") or os.urandom(32).hex()

PUBLIC_PATHS = {"/login"}
PUBLIC_PREFIXES = ("/static",)


def is_authenticated(request: Request) -> bool:
    if not AUTH_ENABLED:
        return True
    return request.session.get("authenticated") is True


def is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)
