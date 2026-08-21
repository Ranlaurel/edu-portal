from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Subject, Topic, UserProgress
from app.progress_utils import DEFAULT_USER_ID
from app.templating import templates

router = APIRouter()


def due_topics(db: Session):
    today = date.today()
    rows = (
        db.query(UserProgress, Topic)
        .join(Topic, Topic.id == UserProgress.topic_id)
        .filter(
            UserProgress.user_id == DEFAULT_USER_ID,
            UserProgress.status == "passed",
            UserProgress.next_review_at != None,  # noqa: E711
            UserProgress.next_review_at <= today,
        )
        .all()
    )
    return rows


@router.get("/review")
def review_page(request: Request, db: Session = Depends(get_db)):
    rows = due_topics(db)

    by_subject = {}
    for prog, topic in rows:
        subject = topic.section.subject
        by_subject.setdefault(subject, []).append({"topic": topic, "progress": prog})

    groups = [
        {"subject": subject, "rows": topic_rows}
        for subject, topic_rows in sorted(by_subject.items(), key=lambda kv: kv[0].id)
    ]

    return templates.TemplateResponse("review.html", {"request": request, "groups": groups})
