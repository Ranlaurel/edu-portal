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
RECENT_ACTIVITY_LIMIT = 15
HEATMAP_WEEKS = 12


def compute_streak(activity_days: set) -> int:
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


def build_heatmap(activity_by_day: dict) -> list:
    """Grid of weeks x weekdays (Mon-Sun) for the last HEATMAP_WEEKS weeks, GitHub-style."""
    today = date.today()
    start = today - timedelta(days=today.weekday())  # this week's Monday
    start -= timedelta(weeks=HEATMAP_WEEKS - 1)

    weeks = []
    cursor = start
    for _ in range(HEATMAP_WEEKS):
        week = []
        for _ in range(7):
            count = activity_by_day.get(cursor, 0)
            level = 0 if count == 0 else 1 if count == 1 else 2 if count <= 3 else 3
            week.append({"date": cursor, "count": count, "level": level, "is_future": cursor > today})
            cursor += timedelta(days=1)
        weeks.append(week)
    return weeks


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


def recent_activity(db: Session):
    rows = (
        db.query(Attempt, Topic)
        .join(Topic, Topic.id == Attempt.topic_id)
        .filter(Attempt.user_id == DEFAULT_USER_ID)
        .order_by(Attempt.created_at.desc())
        .limit(RECENT_ACTIVITY_LIMIT)
        .all()
    )
    return [{"attempt": a, "topic": t, "subject": t.section.subject} for a, t in rows]


@router.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    subjects = db.query(Subject).order_by(Subject.id).all()
    prog = progress_map(db)

    subject_cards = []
    total_topics = 0
    total_passed = 0
    for s in subjects:
        all_topics = [t for sec in s.sections for t in sec.topics if t.has_content]
        passed = sum(1 for t in all_topics if prog.get(t.id) and prog[t.id].status == "passed")
        needs_review = sum(1 for t in all_topics if prog.get(t.id) and prog[t.id].status == "needs_review")
        not_started = len(all_topics) - passed - needs_review
        total_topics += len(all_topics)
        total_passed += passed
        subject_cards.append(
            {
                "subject": s,
                "percent": subject_percent(db, all_topics),
                "passed": passed,
                "needs_review": needs_review,
                "not_started": not_started,
                "total": len(all_topics),
            }
        )

    overall_percent = round(total_passed / total_topics * 100) if total_topics else 0

    all_attempts = db.query(Attempt.created_at, Attempt.score).filter(Attempt.user_id == DEFAULT_USER_ID).all()
    activity_by_day: dict = {}
    for created_at, _score in all_attempts:
        if created_at:
            d = created_at.date()
            activity_by_day[d] = activity_by_day.get(d, 0) + 1

    total_attempts = len(all_attempts)
    avg_score = round(sum(s for _c, s in all_attempts) / total_attempts) if total_attempts else 0

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "subject_cards": subject_cards,
            "overall_percent": overall_percent,
            "total_passed": total_passed,
            "total_topics": total_topics,
            "streak": compute_streak(set(activity_by_day.keys())),
            "total_attempts": total_attempts,
            "avg_score": avg_score,
            "heatmap": build_heatmap(activity_by_day),
            "week_items": topics_this_week(db),
            "weak_items": weak_topics(db),
            "recent_items": recent_activity(db),
        },
    )
