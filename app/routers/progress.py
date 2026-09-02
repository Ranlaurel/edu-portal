from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth import current_user_id
from app.models import Subject
from app.progress_utils import subject_percent

router = APIRouter()


@router.get("/api/progress")
def progress_overview(request: Request, db: Session = Depends(get_db)):
    grade = request.session.get("grade", 6)
    user_id = current_user_id(request)
    subjects = db.query(Subject).filter_by(grade=grade).order_by(Subject.id).all()
    return [
        {
            "subject": s.slug,
            "name": s.name,
            "percent": subject_percent(db, [t for sec in s.sections for t in sec.topics], user_id),
        }
        for s in subjects
    ]
