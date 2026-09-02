from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.auth import AUTH_ENABLED

templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")
templates.env.globals["auth_enabled"] = AUTH_ENABLED


def add_user_to_context(request, db):
    """Helper to add current_user to template context."""
    from app.auth import current_user
    return {"current_user": current_user(db, request)}
