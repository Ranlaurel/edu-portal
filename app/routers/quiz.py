import json
import random

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Question, Topic, UserProgress
from app.progress_utils import DEFAULT_USER_ID
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


@router.get("/topics/{topic_id}/quiz")
def quiz_page(topic_id: int, request: Request, db: Session = Depends(get_db)):
    topic = db.query(Topic).get(topic_id)
    if not topic:
        return RedirectResponse("/subjects")
    questions = [serialize_question(q) for q in topic.questions]
    return templates.TemplateResponse(
        "quiz.html",
        {"request": request, "topic": topic, "questions_json": json.dumps(questions, ensure_ascii=False)},
    )


class SubmitPayload(BaseModel):
    answers: dict


@router.post("/topics/{topic_id}/quiz/submit")
def submit_quiz(topic_id: int, payload: SubmitPayload, db: Session = Depends(get_db)):
    topic = db.query(Topic).get(topic_id)
    if not topic:
        return {"error": "topic not found"}

    results = []
    correct_count = 0

    for q in topic.questions:
        user_answer = payload.answers.get(str(q.id))
        is_correct = False

        if q.type in ("single", "dropdown"):
            correct_opt = next((o for o in q.options if o.is_correct), None)
            is_correct = correct_opt is not None and user_answer == correct_opt.id

        elif q.type == "multiple":
            correct_ids = {o.id for o in q.options if o.is_correct}
            given_ids = set(user_answer or [])
            is_correct = given_ids == correct_ids

        elif q.type == "fill_blank":
            accepted = set((q.answer or "").split("|"))
            given = (user_answer or "").strip().lower()
            is_correct = given in accepted

        elif q.type == "matching":
            given = user_answer or {}
            # correct mapping: each pair's id maps to itself (left_id -> right's pair id)
            pair_ids = {p.id for p in q.pairs}
            is_correct = (
                isinstance(given, dict)
                and set(str(k) for k in pair_ids) <= set(given.keys())
                and all(str(given.get(str(pid))) == str(pid) for pid in pair_ids)
            )

        if is_correct:
            correct_count += 1

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

    total = len(topic.questions)
    score = round(correct_count / total * 100) if total else 0
    passed = score >= PASS_THRESHOLD

    prog = (
        db.query(UserProgress)
        .filter_by(user_id=DEFAULT_USER_ID, topic_id=topic_id)
        .first()
    )
    if not prog:
        prog = UserProgress(user_id=DEFAULT_USER_ID, topic_id=topic_id, attempts=0, best_score=0)
        db.add(prog)

    prog.attempts += 1
    prog.best_score = max(prog.best_score, score)
    if passed:
        prog.status = "passed"
    elif prog.status != "passed":
        prog.status = "needs_review"
    db.commit()

    return {
        "score": score,
        "passed": passed,
        "correct_count": correct_count,
        "total": total,
        "results": results,
    }
