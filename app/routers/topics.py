import markdown as md
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import current_user_id, current_user
from app.db import get_db
from app.models import Subject, Topic
from app.progress_utils import progress_map, subject_percent
from app.templating import templates

router = APIRouter()

AVAILABLE_GRADES = (5, 6)


def current_grade(request: Request) -> int:
    return request.session.get("grade", 6)


@router.get("/")
def home(request: Request):
    if "grade" not in request.session:
        return RedirectResponse("/select-grade")
    return RedirectResponse("/subjects")


@router.get("/select-grade")
def select_grade_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "select_grade.html", {"request": request, "current_grade": request.session.get("grade"), "current_user": current_user(db, request)}
    )


@router.get("/select-grade/{grade}")
def select_grade(grade: int, request: Request):
    if grade in AVAILABLE_GRADES:
        request.session["grade"] = grade
    return RedirectResponse("/subjects")


@router.get("/subjects")
def subject_list(request: Request, db: Session = Depends(get_db)):
    grade = current_grade(request)
    subjects = db.query(Subject).filter_by(grade=grade).order_by(Subject.id).all()
    user_id = current_user_id(request)
    cards = []
    for s in subjects:
        all_topics = [t for sec in s.sections for t in sec.topics]
        cards.append({"subject": s, "percent": subject_percent(db, all_topics, user_id)})
    return templates.TemplateResponse(
        "subject_list.html", {"request": request, "cards": cards, "grade": grade, "current_user": current_user(db, request)}
    )


@router.get("/subjects/{slug}")
def topic_list(slug: str, request: Request, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter_by(slug=slug).first()
    if not subject or subject.grade != current_grade(request):
        return RedirectResponse("/subjects")

    all_topics = [t for sec in subject.sections for t in sec.topics]
    user_id = current_user_id(request)
    prog = progress_map(db, user_id)
    percent = subject_percent(db, all_topics, user_id)

    sections = []
    for sec in subject.sections:
        topic_rows = []
        for t in sec.topics:
            p = prog.get(t.id)
            status = p.status if (p and t.has_content) else ("no_content" if not t.has_content else "not_started")
            has_mistakes = bool(p and p.wrong_question_ids)
            topic_rows.append(
                {"topic": t, "status": status, "best_score": p.best_score if p else None, "has_mistakes": has_mistakes}
            )
        sections.append({"section": sec, "topics": topic_rows})

    return templates.TemplateResponse(
        "topic_list.html",
        {"request": request, "subject": subject, "sections": sections, "percent": percent, "current_user": current_user(db, request)},
    )


@router.get("/topics/{topic_id}/lesson")
def lesson(topic_id: int, request: Request, db: Session = Depends(get_db)):
    topic = db.query(Topic).get(topic_id)
    if not topic or not topic.lesson or topic.section.subject.grade != current_grade(request):
        return RedirectResponse("/subjects")
    html = md.markdown(topic.lesson.content_md, extensions=["tables"])
    return templates.TemplateResponse(
        "lesson.html", {"request": request, "topic": topic, "content_html": html, "current_user": current_user(db, request)}
    )
