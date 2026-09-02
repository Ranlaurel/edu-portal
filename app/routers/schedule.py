import json
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Topic
from app.routers.topics import current_grade
from app.auth import current_user
from app.templating import templates

router = APIRouter()

CONTENT_DIR = Path(__file__).resolve().parent.parent.parent / "content"

WEEKDAY_RU = {
    "Monday": "Пн", "Tuesday": "Вт", "Wednesday": "Ср",
    "Thursday": "Чт", "Friday": "Пт", "Saturday": "Сб", "Sunday": "Вс",
}


@router.get("/schedule")
def schedule_page(request: Request, db: Session = Depends(get_db)):
    grade = current_grade(request)
    schedule_path = CONTENT_DIR / f"schedule-{grade}.json"
    data = json.loads(schedule_path.read_text(encoding="utf-8"))
    topics_by_slug = {t.slug: t for t in db.query(Topic).all()}

    today = date.today().isoformat()

    weeks = {}
    week_order = []
    for d in data["days"]:
        day_date = datetime.fromisoformat(d["date"]).date()
        iso_year, iso_week, _ = day_date.isocalendar()
        week_key = (iso_year, iso_week)
        if week_key not in weeks:
            weeks[week_key] = {"iso_week": iso_week, "days": []}
            week_order.append(week_key)

        day_row = {
            "date": d["date"],
            "weekday": WEEKDAY_RU.get(d["weekday"], d["weekday"]),
            "is_today": d["date"] == today,
            "subjects": {},
        }
        for subj_slug, topic_ref in d["subjects"].items():
            if topic_ref is None:
                day_row["subjects"][subj_slug] = None
                continue
            if topic_ref.get("generic"):
                day_row["subjects"][subj_slug] = {
                    "generic": True,
                    "title": topic_ref["title"],
                    "lesson_number": topic_ref["lesson_number"],
                    "total": topic_ref["total"],
                }
                continue
            db_topic = topics_by_slug.get(topic_ref["slug"])
            day_row["subjects"][subj_slug] = {
                "title": topic_ref["title"],
                "topic_id": db_topic.id if db_topic else None,
                "has_content": db_topic.has_content if db_topic else False,
            }
        weeks[week_key]["days"].append(day_row)

    week_list = [weeks[k] for k in week_order]
    for i, w in enumerate(week_list):
        w["week_number"] = i + 1
        w["start_date"] = w["days"][0]["date"]
        w["end_date"] = w["days"][-1]["date"]
        w["is_current"] = w["start_date"] <= today <= w["end_date"]

    return templates.TemplateResponse("schedule.html", {"request": request, "weeks": week_list, "current_user": current_user(db, request)})
