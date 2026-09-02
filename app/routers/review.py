from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth import current_user_id, current_user
from app.db import get_db
from app.models import Section, Subject, Topic, UserProgress
from app.templating import templates

router = APIRouter()


def due_topics(db: Session, user_id: int, grade: int):
    today = date.today()
    rows = (
        db.query(UserProgress, Topic)
        .join(Topic, Topic.id == UserProgress.topic_id)
        .join(Section, Section.id == Topic.section_id)
        .join(Subject, Subject.id == Section.subject_id)
        .filter(
            UserProgress.user_id == user_id,
            Subject.grade == grade,
            UserProgress.status == "passed",
            UserProgress.next_review_at != None,  # noqa: E711
            UserProgress.next_review_at <= today,
        )
        .all()
    )
    return rows


@router.get("/review")
def review_page(request: Request, db: Session = Depends(get_db)):
    rows = due_topics(db, current_user_id(request), request.session.get("grade", 6))

    by_subject = {}
    for prog, topic in rows:
        subject = topic.section.subject
        by_subject.setdefault(subject, []).append({"topic": topic, "progress": prog})

    groups = [
        {"subject": subject, "rows": topic_rows}
        for subject, topic_rows in sorted(by_subject.items(), key=lambda kv: kv[0].id)
    ]

    return templates.TemplateResponse("review.html", {"request": request, "groups": groups, "current_user": current_user(db, request)})
