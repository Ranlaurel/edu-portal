from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import verify_password, current_user
from app.db import get_db
from app.models import User
from app.templating import templates

router = APIRouter()


@router.get("/login")
def login_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("login.html", {"request": request, "error": None, "current_user": current_user(db, request)})


@router.post("/login")
def login_submit(request: Request, login: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=login, is_active=True).first()
    password_ok = user is not None and verify_password(password, user.password_hash)
    if password_ok:
        request.session.clear()
        request.session["user_id"] = user.id
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": "Неверный логин или пароль", "current_user": None}, status_code=401
    )


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")
