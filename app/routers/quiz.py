import json
import random

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Attempt, Question, Topic, UserProgress
from app.progress_utils import DEFAULT_USER_ID
from app.spaced_repetition import on_fail, on_pass
from app.templating import templates

router = APIRouter()

PASS_THRESHOLD = 70


def serialize_question(q: Question) -> dict:
    base = {"id": q.id, "type": q.type, "text": q.text}
    if q.type in ("single", "multiple", "dropdown"):
        opts = list(q.options)
        random.shuffle(opts)
        base["options"] = [{"id": o.id, "text": o.text} for o in opts]
    elif q.type == "matching":
        pairs = list(q.pairs)
        lefts = [{"id": p.id, "text": p.left_text} for p in pairs]
        rights = [{"id": p.id, "text": p.right_text} for p in pairs]
        random.shuffle(rights)
        base["left"] = lefts
        base["right"] = rights
    elif q.type == "fill_blank":
        pass
    return base


def grade_question(q: Question, user_answer) -> bool:
    if q.type in ("single", "dropdown"):
        correct_opt = next((o for o in q.options if o.is_correct), None)
        return correct_opt is not None and user_answer == correct_opt.id

    if q.type == "multiple":
        correct_ids = {o.id for o in q.options if o.is_correct}
        given_ids = set(user_answer or [])
        return given_ids == correct_ids

    if q.type == "fill_blank":
        accepted = set((q.answer or "").split("|"))
        given = (user_answer or "").strip().lower()
        return given in accepted

    if q.type == "matching":
        given = user_answer or {}
        pair_ids = {p.id for p in q.pairs}
        return (
            isinstance(given, dict)
            and set(str(k) for k in pair_ids) <= set(given.keys())
            and all(str(given.get(str(pid))) == str(pid) for pid in pair_ids)
        )

    return False


def get_progress(db: Session, topic_id: int) -> UserProgress | None:
    return db.query(UserProgress).filter_by(user_id=DEFAULT_USER_ID, topic_id=topic_id).first()


def wrong_ids_set(prog: UserProgress | None) -> set[int]:
    if not prog or not prog.wrong_question_ids:
        return set()
    return {int(x) for x in prog.wrong_question_ids.split(",") if x}


@router.get("/topics/{topic_id}/quiz")
def quiz_page(topic_id: int, request: Request, mistakes: bool = False, db: Session = Depends(get_db)):
    topic = db.query(Topic).get(topic_id)
    if not topic:
        return RedirectResponse("/subjects")

    if mistakes:
        prog = get_progress(db, topic_id)
        wids = wrong_ids_set(prog)
        topic_questions = [q for q in topic.questions if q.id in wids]
        if not topic_questions:
            return RedirectResponse(f"/topics/{topic_id}/quiz")
    else:
        topic_questions = list(topic.questions)

    random.shuffle(topic_questions)
    questions = [serialize_question(q) for q in topic_questions]
    return templates.TemplateResponse(
        "quiz.html",
        {
            "request": request,
            "topic": topic,
            "questions_json": json.dumps(questions, ensure_ascii=False),
            "practice_mode": mistakes,
        },
    )


class SubmitPayload(BaseModel):
    answers: dict
    practice: bool = False


@router.post("/topics/{topic_id}/quiz/submit")
def submit_quiz(topic_id: int, payload: SubmitPayload, db: Session = Depends(get_db)):
    topic = db.query(Topic).get(topic_id)
    if not topic:
        return {"error": "topic not found"}

    prog = get_progress(db, topic_id)

    if payload.practice:
        wids = wrong_ids_set(prog)
        questions_to_grade = [q for q in topic.questions if q.id in wids]
    else:
        questions_to_grade = list(topic.questions)

    results = []
    correct_count = 0
    missed_ids = []

    for q in questions_to_grade:
        user_answer = payload.answers.get(str(q.id))
        is_correct = grade_question(q, user_answer)

        if is_correct:
            correct_count += 1
        else:
            missed_ids.append(q.id)

        results.append(
            {
                "id": q.id,
                "correct": is_correct,
                "explanation": q.explanation,
                "correct_options": [o.id for o in q.options if o.is_correct]
                if q.type in ("single", "multiple", "dropdown")
                else None,
                "correct_answer": (q.answer.split("|")[0] if q.answer else None)
                if q.type == "fill_blank"
                else None,
            }
        )

    total = len(questions_to_grade)
    score = round(correct_count / total * 100) if total else 0
    passed = score >= PASS_THRESHOLD

    db.add(Attempt(user_id=DEFAULT_USER_ID, topic_id=topic_id, score=score, passed=passed))

    if payload.practice:
        # Practice-by-mistakes: give feedback, don't touch status/best_score/schedule.
        db.commit()
        return {
            "score": score,
            "passed": passed,
            "correct_count": correct_count,
            "total": total,
            "results": results,
            "next_review_at": None,
            "practice": True,
        }

    if not prog:
        prog = UserProgress(user_id=DEFAULT_USER_ID, topic_id=topic_id, attempts=0, best_score=0)
        db.add(prog)

    prog.attempts += 1
    prog.best_score = max(prog.best_score, score)
    prog.wrong_question_ids = ",".join(str(i) for i in missed_ids) if missed_ids else None
    if passed:
        prog.status = "passed"
        on_pass(prog)
    elif prog.status != "passed":
        prog.status = "needs_review"
    else:
        # was passed before, failed this review attempt -> back into rotation sooner
        on_fail(prog)
    db.commit()

    return {
        "score": score,
        "passed": passed,
        "correct_count": correct_count,
        "total": total,
        "results": results,
        "next_review_at": prog.next_review_at.isoformat() if prog.next_review_at else None,
        "practice": False,
    }
