from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Attempt, Subject, Topic, UserProgress
from app.progress_utils import DEFAULT_USER_ID, progress_map, subject_percent
from app.templating import templates

router = APIRouter()

WEAK_SCORE_THRESHOLD = 85
WEAK_TOPICS_LIMIT = 12


def compute_streak(db: Session) -> int:
    rows = db.query(Attempt.created_at).filter(Attempt.user_id == DEFAULT_USER_ID).all()
    activity_days = {r[0].date() for r in rows if r[0]}
    if not activity_days:
        return 0

    today = date.today()
    cursor = today if today in activity_days else today - timedelta(days=1)
    if cursor not in activity_days:
        return 0

    streak = 0
    while cursor in activity_days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def topics_this_week(db: Session):
    week_ago = date.today() - timedelta(days=6)
    rows = (
        db.query(Attempt, Topic)
        .join(Topic, Topic.id == Attempt.topic_id)
        .filter(
            Attempt.user_id == DEFAULT_USER_ID,
            Attempt.passed == True,  # noqa: E712
            Attempt.created_at >= week_ago,
        )
        .order_by(Attempt.created_at.desc())
        .all()
    )
    seen = set()
    result = []
    for attempt, topic in rows:
        if topic.id in seen:
            continue
        seen.add(topic.id)
        result.append({"topic": topic, "when": attempt.created_at})
    return result


def weak_topics(db: Session):
    rows = (
        db.query(UserProgress, Topic)
        .join(Topic, Topic.id == UserProgress.topic_id)
        .filter(
            UserProgress.user_id == DEFAULT_USER_ID,
            or_(
                UserProgress.status == "needs_review",
                UserProgress.best_score < WEAK_SCORE_THRESHOLD,
            ),
        )
        .order_by(UserProgress.best_score.asc())
        .limit(WEAK_TOPICS_LIMIT)
        .all()
    )
    return [{"progress": p, "topic": t} for p, t in rows]


@router.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    subjects = db.query(Subject).order_by(Subject.id).all()
    subject_cards = []
    total_topics = 0
    total_passed = 0
    prog = progress_map(db)
    for s in subjects:
        all_topics = [t for sec in s.sections for t in sec.topics if t.has_content]
        passed = sum(1 for t in all_topics if prog.get(t.id) and prog[t.id].status == "passed")
        total_topics += len(all_topics)
        total_passed += passed
        subject_cards.append(
            {"subject": s, "percent": subject_percent(db, all_topics), "passed": passed, "total": len(all_topics)}
        )

    overall_percent = round(total_passed / total_topics * 100) if total_topics else 0

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "subject_cards": subject_cards,
            "overall_percent": overall_percent,
            "total_passed": total_passed,
            "total_topics": total_topics,
            "streak": compute_streak(db),
            "week_items": topics_this_week(db),
            "weak_items": weak_topics(db),
        },
    )
