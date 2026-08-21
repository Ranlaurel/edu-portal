import markdown as md
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Subject, Topic
from app.progress_utils import progress_map, subject_percent
from app.templating import templates

router = APIRouter()


@router.get("/")
def home(db: Session = Depends(get_db)):
    subjects = db.query(Subject).order_by(Subject.id).all()
    if len(subjects) == 1:
        return RedirectResponse(f"/subjects/{subjects[0].slug}")
    return RedirectResponse("/subjects")


@router.get("/subjects")
def subject_list(request: Request, db: Session = Depends(get_db)):
    subjects = db.query(Subject).order_by(Subject.id).all()
    cards = []
    for s in subjects:
        all_topics = [t for sec in s.sections for t in sec.topics]
        cards.append({"subject": s, "percent": subject_percent(db, all_topics)})
    return templates.TemplateResponse(
        "subject_list.html", {"request": request, "cards": cards}
    )


@router.get("/subjects/{slug}")
def topic_list(slug: str, request: Request, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter_by(slug=slug).first()
    if not subject:
        return RedirectResponse("/subjects")

    all_topics = [t for sec in subject.sections for t in sec.topics]
    prog = progress_map(db)
    percent = subject_percent(db, all_topics)

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
        {"request": request, "subject": subject, "sections": sections, "percent": percent},
    )


@router.get("/topics/{topic_id}/lesson")
def lesson(topic_id: int, request: Request, db: Session = Depends(get_db)):
    topic = db.query(Topic).get(topic_id)
    if not topic or not topic.lesson:
        return RedirectResponse("/subjects")
    html = md.markdown(topic.lesson.content_md, extensions=["tables"])
    return templates.TemplateResponse(
        "lesson.html", {"request": request, "topic": topic, "content_html": html}
    )
