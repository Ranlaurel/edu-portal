import secrets

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.auth import PORTAL_LOGIN, PORTAL_PASSWORD
from app.templating import templates

router = APIRouter()


@router.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login_submit(request: Request, login: str = Form(...), password: str = Form(...)):
    login_ok = secrets.compare_digest(login, PORTAL_LOGIN)
    password_ok = secrets.compare_digest(password, PORTAL_PASSWORD or "")
    if login_ok and password_ok:
        request.session["authenticated"] = True
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": "Неверный логин или пароль"}, status_code=401
    )


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")
