"""Load subject/section/topic structure + lesson/quiz content from content/<subject>/
into the SQLite database. Idempotent: safe to re-run, replaces content per topic.

Usage:
    python pipeline/load_content.py russian
    python pipeline/load_content.py            # loads every subject folder under content/
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import Base, SessionLocal, engine
from app.models import Lesson, MatchPair, Option, Question, Section, Subject, Topic

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"


def load_subject(db, subject_dir: Path):
    manifest_path = subject_dir / "topics.json"
    if not manifest_path.exists():
        print(f"  skip {subject_dir.name}: no topics.json")
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    subject_data = manifest["subject"]
    grade = subject_data.get("grade", 6)
    subject = db.query(Subject).filter_by(slug=subject_data["slug"]).first()
    if not subject:
        subject = Subject(name=subject_data["name"], slug=subject_data["slug"], grade=grade)
        db.add(subject)
        db.flush()
        print(f"  + subject {subject.name} (grade {grade})")
    else:
        subject.grade = grade

    for section_data in manifest["sections"]:
        section = (
            db.query(Section)
            .filter_by(subject_id=subject.id, name=section_data["name"])
            .first()
        )
        if not section:
            section = Section(
                subject_id=subject.id,
                name=section_data["name"],
                order=section_data.get("order", 0),
            )
            db.add(section)
            db.flush()
            print(f"    + section {section.name}")

        for topic_data in section_data["topics"]:
            topic = db.query(Topic).filter_by(slug=topic_data["slug"]).first()
            if not topic:
                topic = Topic(
                    section_id=section.id,
                    title=topic_data["title"],
                    slug=topic_data["slug"],
                    order=topic_data.get("order", 0),
                    source_uid=topic_data.get("source_uid"),
                )
                db.add(topic)
                db.flush()
            else:
                topic.title = topic_data["title"]
                topic.order = topic_data.get("order", 0)
                topic.section_id = section.id  # topic may have moved to a different section

            load_topic_content(db, subject_dir, topic, topic_data["slug"])

    # Sections whose topics all moved elsewhere (e.g. renamed/regrouped) are now
    # empty -- remove them so the old section name stops showing up in the UI.
    db.flush()
    empty_sections = (
        db.query(Section)
        .filter(Section.subject_id == subject.id, ~Section.topics.any())
        .all()
    )
    for s in empty_sections:
        print(f"    - removing empty section {s.name}")
        db.delete(s)


def load_topic_content(db, subject_dir: Path, topic: Topic, slug: str):
    topic_dir = subject_dir / slug
    lesson_path = topic_dir / "lesson.md"
    quiz_path = topic_dir / "quiz.json"

    if not lesson_path.exists() or not quiz_path.exists():
        print(f"      - {slug}: no content yet")
        topic.has_content = False
        return

    lesson_md = lesson_path.read_text(encoding="utf-8")
    if topic.lesson:
        topic.lesson.content_md = lesson_md
    else:
        db.add(Lesson(topic_id=topic.id, content_md=lesson_md))

    quiz_data = json.loads(quiz_path.read_text(encoding="utf-8"))

    # wipe existing questions for this topic (cascades via explicit deletes)
    existing_questions = db.query(Question).filter_by(topic_id=topic.id).all()
    for q in existing_questions:
        db.query(Option).filter_by(question_id=q.id).delete()
        db.query(MatchPair).filter_by(question_id=q.id).delete()
        db.delete(q)
    db.flush()

    for i, q_data in enumerate(quiz_data["questions"]):
        question = Question(
            topic_id=topic.id,
            type=q_data["type"],
            text=q_data["text"],
            explanation=q_data.get("explanation"),
            order=i,
        )
        if q_data["type"] == "fill_blank":
            accepted = q_data.get("accepted") or [q_data["answer"]]
            question.answer = "|".join(a.strip().lower() for a in accepted)
        db.add(question)
        db.flush()

        if q_data["type"] in ("single", "multiple", "dropdown"):
            for j, opt in enumerate(q_data["options"]):
                db.add(
                    Option(
                        question_id=question.id,
                        text=opt["text"],
                        is_correct=opt.get("correct", False),
                        order=j,
                    )
                )
        elif q_data["type"] == "matching":
            for j, pair in enumerate(q_data["pairs"]):
                db.add(
                    MatchPair(
                        question_id=question.id,
                        left_text=pair["left"],
                        right_text=pair["right"],
                        order=j,
                    )
                )

    topic.has_content = True
    print(f"      + {slug}: lesson + {len(quiz_data['questions'])} questions")


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        target = sys.argv[1] if len(sys.argv) > 1 else None
        subject_dirs = (
            [CONTENT_DIR / target] if target else [d for d in CONTENT_DIR.iterdir() if d.is_dir()]
        )
        for subject_dir in subject_dirs:
            print(f"Loading {subject_dir.name}...")
            load_subject(db, subject_dir)
        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
