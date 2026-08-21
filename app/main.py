from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app import migrate
from app.auth import AUTH_ENABLED, SECRET_KEY, is_authenticated, is_public_path
from app.db import Base, engine
from app.routers import auth, progress, quiz, review, schedule, topics

Base.metadata.create_all(bind=engine)
migrate.run(engine)

app = FastAPI(title="Учебный портал")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.middleware("http")
async def require_login(request: Request, call_next):
    if AUTH_ENABLED and not is_public_path(request.url.path) and not is_authenticated(request):
        return RedirectResponse("/login")
    return await call_next(request)


# Added after require_login so it ends up OUTERMOST in the stack (Starlette wraps
# most-recently-added middleware around earlier ones) -- request.session must exist
# before require_login's dispatch reads it.
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax")


app.include_router(auth.router)
app.include_router(topics.router)
app.include_router(quiz.router)
app.include_router(progress.router)
app.include_router(schedule.router)
app.include_router(review.router)
