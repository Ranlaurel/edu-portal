"""ОГЭ mode: exam config, mock-variant assembly and primary-score -> mark conversion.

Each ОГЭ subject folder has content/<slug>/exam.json describing the КИМ: the list of
tasks (number, title, max points, whether it's self-checked), the duration, the
primary-score scale and extra conditions (e.g. math: >= 2 points for geometry).
Kept as data, not code: ФИПИ/Рособрнадзор adjust these every year and regions may
use their own scale.
"""
import json
import random
from pathlib import Path

OGE_GRADE = 9
CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"


def load_exam_config(subject_slug: str) -> dict | None:
    path = CONTENT_DIR / subject_slug / "exam.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def question_task(question) -> str | None:
    return question.exam_task or question.topic.exam_task


def build_variant(config: dict, questions, rng: random.Random | None = None) -> list[dict]:
    """Pick one question per КИМ task.

    Questions marked "exam": true in quiz.json are the exam-format ones; a task with
    none of those falls back to any question of its topics. Questions sharing an
    exam_set (e.g. math tasks 1-5 built on one practical text) are taken together,
    so a variant never mixes two different sets.
    Tasks with no questions at all are skipped -- the caller reports the variant as
    incomplete instead of failing.
    """
    from app.routers.quiz import question_extra

    rng = rng or random.Random()
    pool: dict[str, list] = {}
    for q in questions:
        task = question_task(q)
        if task is not None:
            pool.setdefault(task, []).append(q)

    chosen: dict[str, int] = {}
    for task in config["tasks"]:
        tid = task["id"]
        if tid in chosen or tid not in pool:
            continue
        candidates = [q for q in pool[tid] if question_extra(q).get("exam")] or pool[tid]
        q = rng.choice(candidates)
        if q.exam_set:
            for sibling in questions:
                if sibling.topic_id == q.topic_id and sibling.exam_set == q.exam_set:
                    chosen.setdefault(question_task(sibling), sibling.id)
        chosen[tid] = q.id

    return [{"task": t["id"], "question_id": chosen[t["id"]]} for t in config["tasks"] if t["id"] in chosen]


def task_by_id(config: dict) -> dict[str, dict]:
    return {t["id"]: t for t in config["tasks"]}


def max_score(config: dict) -> int:
    return sum(t["points"] for t in config["tasks"])


def compute_mark(config: dict, task_points: dict[str, int], criterion_points: dict[str, int]) -> tuple[int, list[str]]:
    """Primary score -> school mark (2..5) using config["scale"] and config["conditions"].

    A condition caps the mark: if its tasks/criteria earn less than min_points, a mark
    of at least `applies_from_mark` drops to `fallback_mark`. Conditions are checked
    from the highest mark down, so e.g. Russian "5 needs >= 9 literacy" demotes to 4,
    and then "4 needs >= 6 literacy" can demote further to 3.
    Returns (mark, human-readable notes about every condition that lowered it).
    """
    total = sum(task_points.values())
    mark = 2
    for step in sorted(config["scale"], key=lambda s: s["min"]):
        if total >= step["min"]:
            mark = step["mark"]

    notes = []
    for cond in sorted(config.get("conditions", []), key=lambda c: -c["applies_from_mark"]):
        if mark < cond["applies_from_mark"]:
            continue
        earned = sum(task_points.get(t, 0) for t in cond.get("tasks", [])) + sum(
            criterion_points.get(c, 0) for c in cond.get("criteria", [])
        )
        if earned < cond["min_points"]:
            notes.append(f"{cond['label']}: набрано {earned}, нужно {cond['min_points']} — оценка снижена до «{cond['fallback_mark']}»")
            mark = min(mark, cond["fallback_mark"])
    return mark, notes
