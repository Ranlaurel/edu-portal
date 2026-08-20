from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import Base, engine
from app.routers import progress, quiz, schedule, topics

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Учебный портал")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(topics.router)
app.include_router(quiz.router)
app.include_router(progress.router)
app.include_router(schedule.router)
