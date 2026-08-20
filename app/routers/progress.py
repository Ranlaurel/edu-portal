from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Subject
from app.progress_utils import subject_percent

router = APIRouter()


@router.get("/api/progress")
def progress_overview(db: Session = Depends(get_db)):
    subjects = db.query(Subject).order_by(Subject.id).all()
    return [
        {
            "subject": s.slug,
            "name": s.name,
            "percent": subject_percent(db, [t for sec in s.sections for t in sec.topics]),
        }
        for s in subjects
    ]
