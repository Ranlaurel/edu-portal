from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.auth import AUTH_ENABLED

templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")
templates.env.globals["auth_enabled"] = AUTH_ENABLED
