from sqlalchemy.orm import Session

from app.models import Topic, UserProgress

DEFAULT_USER_ID = 1


def progress_map(db: Session, user_id: int = DEFAULT_USER_ID) -> dict[int, UserProgress]:
    rows = db.query(UserProgress).filter_by(user_id=user_id).all()
    return {row.topic_id: row for row in rows}


def subject_percent(db: Session, topics: list[Topic], user_id: int = DEFAULT_USER_ID) -> int:
    content_topics = [t for t in topics if t.has_content]
    if not content_topics:
        return 0
    prog = progress_map(db, user_id)
    passed = sum(1 for t in content_topics if prog.get(t.id) and prog[t.id].status == "passed")
    return round(passed / len(content_topics) * 100)
