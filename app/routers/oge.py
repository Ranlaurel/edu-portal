import json
from datetime import date, datetime

import markdown as md
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import current_user, current_user_id
from app.db import get_db
from app.models import ExamAttempt, Question, Section, Subject, Topic
from app.oge import OGE_GRADE, build_variant, compute_mark, load_exam_config, max_score, task_by_id
from app.progress_utils import progress_map
from app.routers.quiz import (
    grade_question,
    question_extra,
    self_check_points,
    self_check_points_one,
    serialize_question,
)
from app.templating import templates

router = APIRouter()

RECENT_EXAMS_FOR_STATS = 5


def oge_subjects(db: Session) -> list[tuple[Subject, dict]]:
    subjects = db.query(Subject).filter_by(grade=OGE_GRADE).order_by(Subject.id).all()
    return [(s, cfg) for s in subjects if (cfg := load_exam_config(s.slug))]


def subject_questions(db: Session, subject: Subject) -> list[Question]:
    return (
        db.query(Question)
        .join(Topic, Topic.id == Question.topic_id)
        .join(Section, Section.id == Topic.section_id)
        .filter(Section.subject_id == subject.id, Topic.has_content == True)  # noqa: E712
        .all()
    )


def task_stats(db: Session, subject: Subject, config: dict, user_id: int, finished: list[ExamAttempt]) -> list[dict]:
    """Per КИМ task: how much of its theory is passed and how it went in recent mock exams."""
    prog = progress_map(db, user_id)
    topics_by_task: dict[str, list[Topic]] = {}
    for sec in subject.sections:
        for t in sec.topics:
            if t.exam_task:
                topics_by_task.setdefault(t.exam_task, []).append(t)
    # A topic can serve several tasks via per-question exam_task (math 1-5 block).
    for q in subject_questions(db, subject):
        if q.exam_task and q.topic not in topics_by_task.setdefault(q.exam_task, []):
            topics_by_task[q.exam_task].append(q.topic)

    exam_hits: dict[str, list[float]] = {}
    for attempt in finished[:RECENT_EXAMS_FOR_STATS]:
        for tid, r in json.loads(attempt.results_json or "{}").items():
            if r["max"]:
                exam_hits.setdefault(tid, []).append(r["points"] / r["max"])

    rows = []
    for task in config["tasks"]:
        topics = topics_by_task.get(task["id"], [])
        with_content = [t for t in topics if t.has_content]
        passed = sum(1 for t in with_content if prog.get(t.id) and prog[t.id].status == "passed")
        hits = exam_hits.get(task["id"], [])
        exam_rate = round(sum(hits) / len(hits) * 100) if hits else None
        if exam_rate is not None:
            level = "good" if exam_rate >= 80 else "mid" if exam_rate >= 50 else "bad"
        elif with_content and passed == len(with_content):
            level = "good"
        else:
            level = "none"
        rows.append(
            {
                "task": task,
                "topics": with_content,
                "first_topic": with_content[0] if with_content else None,
                "passed": passed,
                "total": len(with_content),
                "exam_rate": exam_rate,
                "exam_count": len(hits),
                "level": level,
            }
        )
    return rows


@router.get("/oge")
def oge_hub(request: Request, db: Session = Depends(get_db)):
    request.session["grade"] = OGE_GRADE
    user_id = current_user_id(request)
    cards = []
    for subject, config in oge_subjects(db):
        finished = (
            db.query(ExamAttempt)
            .filter_by(user_id=user_id, subject_id=subject.id, status="finished")
            .order_by(ExamAttempt.finished_at.desc())
            .all()
        )
        unfinished = (
            db.query(ExamAttempt)
            .filter(ExamAttempt.user_id == user_id, ExamAttempt.subject_id == subject.id, ExamAttempt.status != "finished")
            .order_by(ExamAttempt.id.desc())
            .first()
        )
        stats = task_stats(db, subject, config, user_id, finished)
        weak = sorted(
            [r for r in stats if r["exam_rate"] is not None and r["exam_rate"] < 80],
            key=lambda r: r["exam_rate"],
        )[:5]
        variant_size = len(build_variant(config, subject_questions(db, subject)))
        cards.append(
            {
                "subject": subject,
                "config": config,
                "stats": stats,
                "weak": weak,
                "finished": finished[:8],
                "unfinished": unfinished,
                "bank_tasks": variant_size,
                "max_score": max_score(config),
            }
        )

    exam_date = None
    days_left = None
    dates = [c["config"].get("exam_date") for c in cards if c["config"].get("exam_date")]
    if dates:
        exam_date = min(date.fromisoformat(d) for d in dates)
        days_left = (exam_date - date.today()).days

    return templates.TemplateResponse(
        "oge_hub.html",
        {
            "request": request,
            "cards": cards,
            "exam_date": exam_date,
            "days_left": days_left,
            "current_user": current_user(db, request),
        },
    )


@router.post("/oge/{slug}/exam")
def start_exam(slug: str, request: Request, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter_by(slug=slug, grade=OGE_GRADE).first()
    config = load_exam_config(slug) if subject else None
    if not config:
        return RedirectResponse("/oge", status_code=303)
    variant = build_variant(config, subject_questions(db, subject))
    if not variant:
        return RedirectResponse("/oge", status_code=303)
    attempt = ExamAttempt(
        user_id=current_user_id(request),
        subject_id=subject.id,
        status="in_progress",
        variant_json=json.dumps(variant),
    )
    db.add(attempt)
    db.commit()
    return RedirectResponse(f"/oge/exam/{attempt.id}", status_code=303)


def own_attempt(db: Session, request: Request, attempt_id: int) -> ExamAttempt | None:
    attempt = db.query(ExamAttempt).get(attempt_id)
    if not attempt or attempt.user_id != current_user_id(request):
        return None
    return attempt


def variant_rows(db: Session, attempt: ExamAttempt, config: dict) -> list[dict]:
    tasks = task_by_id(config)
    rows = []
    for item in json.loads(attempt.variant_json):
        q = db.query(Question).get(item["question_id"])
        task = tasks.get(item["task"])
        if q is None or task is None:  # content reloaded since the variant was built
            continue
        rows.append({"task": task, "question": q})
    return rows


@router.get("/oge/exam/{attempt_id}")
def exam_page(attempt_id: int, request: Request, db: Session = Depends(get_db)):
    attempt = own_attempt(db, request, attempt_id)
    if not attempt:
        return RedirectResponse("/oge")
    if attempt.status == "self_check":
        return RedirectResponse(f"/oge/exam/{attempt.id}/self-check")
    if attempt.status == "finished":
        return RedirectResponse(f"/oge/exam/{attempt.id}/result")

    config = load_exam_config(attempt.subject.slug)
    items = []
    for row in variant_rows(db, attempt, config):
        q = serialize_question(row["question"])
        if q["type"] == "self_check":
            # During the exam the reference stays hidden -- it's shown on the self-check step.
            q.pop("reference_html", None)
            q.pop("criteria", None)
        q["task"] = row["task"]["id"]
        q["task_title"] = row["task"]["title"]
        q["points"] = row["task"]["points"]
        items.append(q)

    return templates.TemplateResponse(
        "oge_exam.html",
        {
            "request": request,
            "attempt": attempt,
            "config": config,
            "questions_json": json.dumps(items, ensure_ascii=False),
            "incomplete": len(items) < len(config["tasks"]),
            "current_user": current_user(db, request),
        },
    )


class ExamSubmit(BaseModel):
    answers: dict


@router.post("/oge/exam/{attempt_id}/submit")
def submit_exam(attempt_id: int, payload: ExamSubmit, request: Request, db: Session = Depends(get_db)):
    attempt = own_attempt(db, request, attempt_id)
    if not attempt or attempt.status != "in_progress":
        return {"redirect": "/oge"}
    config = load_exam_config(attempt.subject.slug)

    results = {}
    needs_self_check = False
    for row in variant_rows(db, attempt, config):
        q, task = row["question"], row["task"]
        answer = payload.answers.get(str(q.id))
        if q.type == "self_check":
            needs_self_check = True
            results[task["id"]] = {"question_id": q.id, "points": 0, "max": task["points"], "correct": None, "self": True}
        else:
            correct = grade_question(q, answer)
            results[task["id"]] = {
                "question_id": q.id,
                "points": task["points"] if correct else 0,
                "max": task["points"],
                "correct": correct,
                "self": False,
            }

    attempt.answers_json = json.dumps(payload.answers, ensure_ascii=False)
    attempt.results_json = json.dumps(results, ensure_ascii=False)
    if needs_self_check:
        attempt.status = "self_check"
        db.commit()
        return {"redirect": f"/oge/exam/{attempt.id}/self-check"}
    finalize(attempt, config)
    db.commit()
    return {"redirect": f"/oge/exam/{attempt.id}/result"}


def finalize(attempt: ExamAttempt, config: dict) -> None:
    results = json.loads(attempt.results_json or "{}")
    task_points = {tid: r["points"] for tid, r in results.items()}
    criterion_points: dict[str, int] = {}
    for r in results.values():
        for code, pts in (r.get("criteria") or {}).items():
            criterion_points[code] = criterion_points.get(code, 0) + pts

    attempt.primary_score = sum(task_points.values())
    attempt.max_score = sum(r["max"] for r in results.values())
    complete = len(results) == len(config["tasks"])
    attempt.mark = compute_mark(config, task_points, criterion_points)[0] if complete else None
    attempt.status = "finished"
    attempt.finished_at = datetime.now()


def answer_text(answers: dict, question_id: int) -> str:
    value = answers.get(str(question_id))
    if isinstance(value, dict):
        return value.get("text") or ""
    return value or ""


@router.get("/oge/exam/{attempt_id}/self-check")
def self_check_page(attempt_id: int, request: Request, db: Session = Depends(get_db)):
    attempt = own_attempt(db, request, attempt_id)
    if not attempt:
        return RedirectResponse("/oge")
    if attempt.status != "self_check":
        return RedirectResponse(f"/oge/exam/{attempt.id}")
    config = load_exam_config(attempt.subject.slug)
    answers = json.loads(attempt.answers_json or "{}")

    items = []
    for row in variant_rows(db, attempt, config):
        q = row["question"]
        if q.type != "self_check":
            continue
        extra = question_extra(q)
        items.append(
            {
                "task": row["task"],
                "question": q,
                "prompt_html": md.markdown(q.text, extensions=["tables"]),
                "reference_html": md.markdown(extra.get("reference") or "", extensions=["tables"]),
                "criteria": extra.get("criteria") or [],
                "answer": answer_text(answers, q.id),
                "no_text": bool(extra.get("no_text")),
            }
        )
    return templates.TemplateResponse(
        "oge_self_check.html",
        {"request": request, "attempt": attempt, "items": items, "current_user": current_user(db, request)},
    )


@router.post("/oge/exam/{attempt_id}/self-check")
async def self_check_submit(attempt_id: int, request: Request, db: Session = Depends(get_db)):
    attempt = own_attempt(db, request, attempt_id)
    if not attempt or attempt.status != "self_check":
        return RedirectResponse("/oge", status_code=303)
    config = load_exam_config(attempt.subject.slug)
    form = await request.form()
    results = json.loads(attempt.results_json or "{}")

    for tid, r in results.items():
        if not r.get("self"):
            continue
        q = db.query(Question).get(r["question_id"])
        if q is None:
            continue
        criteria = question_extra(q).get("criteria") or []
        scores = {c["code"]: form.get(f"score-{tid}-{c['code']}", 0) for c in criteria}
        earned, _ = self_check_points(q, scores)
        r["criteria"] = {c["code"]: self_check_points_one(scores[c["code"]], c["max"]) for c in criteria}
        r["points"] = min(earned, r["max"])
        r["correct"] = r["max"] > 0 and r["points"] * 2 >= r["max"]

    attempt.results_json = json.dumps(results, ensure_ascii=False)
    finalize(attempt, config)
    db.commit()
    return RedirectResponse(f"/oge/exam/{attempt.id}/result", status_code=303)


@router.get("/oge/exam/{attempt_id}/result")
def result_page(attempt_id: int, request: Request, db: Session = Depends(get_db)):
    attempt = own_attempt(db, request, attempt_id)
    if not attempt:
        return RedirectResponse("/oge")
    if attempt.status != "finished":
        return RedirectResponse(f"/oge/exam/{attempt.id}")
    config = load_exam_config(attempt.subject.slug)
    results = json.loads(attempt.results_json or "{}")
    answers = json.loads(attempt.answers_json or "{}")

    task_points = {tid: r["points"] for tid, r in results.items()}
    criterion_points: dict[str, int] = {}
    for r in results.values():
        for code, pts in (r.get("criteria") or {}).items():
            criterion_points[code] = criterion_points.get(code, 0) + pts
    _mark, notes = compute_mark(config, task_points, criterion_points)

    rows = []
    for task in config["tasks"]:
        r = results.get(task["id"])
        if r is None:
            rows.append({"task": task, "missing": True})
            continue
        q = db.query(Question).get(r["question_id"])
        rows.append(
            {
                "task": task,
                "missing": False,
                "result": r,
                "question": q,
                "given": given_answer_text(q, answers.get(str(r["question_id"]))),
                "correct_answer": correct_answer_text(q),
                "topic": q.topic if q else None,
            }
        )

    return templates.TemplateResponse(
        "oge_result.html",
        {
            "request": request,
            "attempt": attempt,
            "config": config,
            "rows": rows,
            "notes": notes if attempt.mark is not None else [],
            "current_user": current_user(db, request),
        },
    )


def given_answer_text(q: Question | None, value) -> str | None:
    if q is None or value in (None, "", [], {}):
        return None
    if q.type == "fill_blank":
        return value if isinstance(value, str) else None
    if q.type in ("single", "dropdown", "multiple"):
        ids = set(value) if isinstance(value, list) else {value}
        return "; ".join(o.text for o in q.options if o.id in ids) or None
    if q.type == "matching" and isinstance(value, dict):
        by_id = {p.id: p for p in q.pairs}
        return "; ".join(
            f"{by_id[int(lid)].left_text} — {by_id[rid].right_text}"
            for lid, rid in value.items()
            if str(lid).isdigit() and int(lid) in by_id and rid in by_id
        ) or None
    return None


def correct_answer_text(q: Question | None) -> str | None:
    if q is None:
        return None
    if q.type == "fill_blank":
        return (q.answer or "").split("|")[0]
    if q.type in ("single", "multiple", "dropdown"):
        return "; ".join(o.text for o in q.options if o.is_correct)
    if q.type == "matching":
        return "; ".join(f"{p.left_text} — {p.right_text}" for p in q.pairs)
    return None
