import json
import random
import unittest
from pathlib import Path

from app.auth import hash_password, verify_password
from app.oge import build_variant, compute_mark, load_exam_config
from app.routers.quiz import grade_question

CONTENT = Path(__file__).resolve().parents[1] / "content"


class FakeOption:
    def __init__(self, option_id, correct):
        self.id = option_id
        self.is_correct = correct


class FakeQuestion:
    def __init__(self, question_type, options=None, answer=None, pairs=None, extra=None):
        self.type = question_type
        self.options = options or []
        self.answer = answer
        self.pairs = pairs or []
        self.extra = json.dumps(extra) if extra else None


class FakeTopic:
    def __init__(self, exam_task):
        self.exam_task = exam_task


class FakeExamQuestion:
    def __init__(self, qid, task, topic_id=1, exam_set=None, exam=False, question_task=None):
        self.id = qid
        self.topic_id = topic_id
        self.topic = FakeTopic(task)
        self.exam_task = question_task
        self.exam_set = exam_set
        self.extra = json.dumps({"exam": True}) if exam else None


class FakePair:
    def __init__(self, pair_id):
        self.id = pair_id


class CoreBehaviorTests(unittest.TestCase):
    def test_password_hash_is_not_plaintext_and_verifies(self):
        encoded = hash_password("correct horse")
        self.assertNotEqual(encoded, "correct horse")
        self.assertTrue(verify_password("correct horse", encoded))
        self.assertFalse(verify_password("wrong", encoded))

    def test_quiz_grading_supports_all_question_types(self):
        single = FakeQuestion("single", [FakeOption(1, True), FakeOption(2, False)])
        multiple = FakeQuestion("multiple", [FakeOption(1, True), FakeOption(2, True), FakeOption(3, False)])
        fill_blank = FakeQuestion("fill_blank", answer="москва")
        matching = FakeQuestion("matching", pairs=[FakePair(1), FakePair(2)])
        self.assertTrue(grade_question(single, 1))
        self.assertFalse(grade_question(single, 2))
        self.assertTrue(grade_question(multiple, [1, 2]))
        self.assertFalse(grade_question(multiple, [1]))
        self.assertTrue(grade_question(fill_blank, "Москва"))
        self.assertTrue(grade_question(matching, {"1": 1, "2": 2}))
        self.assertFalse(grade_question(matching, {"1": 2, "2": 1}))

    def test_short_answers_are_compared_like_oge_forms(self):
        decimal = FakeQuestion("fill_blank", answer="-0,55")
        self.assertTrue(grade_question(decimal, "-0.55"))
        self.assertTrue(grade_question(decimal, " -0,55 "))
        self.assertFalse(grade_question(decimal, "0,55"))
        words = FakeQuestion("fill_blank", answer="туман поднимался|поднимался туман")
        self.assertTrue(grade_question(words, "ТУМАНПОДНИМАЛСЯ"))
        yo = FakeQuestion("fill_blank", answer="решённый")
        self.assertTrue(grade_question(yo, "решенный"))
        digits = FakeQuestion("fill_blank", answer="135", extra={"any_order": True})
        self.assertTrue(grade_question(digits, "531"))
        self.assertFalse(grade_question(digits, "13"))
        self.assertFalse(grade_question(FakeQuestion("fill_blank", answer="135"), "531"))
        self.assertFalse(grade_question(decimal, None))

    def test_self_check_counts_at_half_of_points_and_clamps(self):
        q = FakeQuestion("self_check", extra={"criteria": [{"code": "A", "max": 2}, {"code": "B", "max": 2}]})
        self.assertTrue(grade_question(q, {"text": "...", "scores": {"A": 2, "B": 0}}))
        self.assertFalse(grade_question(q, {"text": "...", "scores": {"A": 1, "B": 0}}))
        self.assertFalse(grade_question(q, {"text": "...", "scores": None}))  # reference never opened
        self.assertFalse(grade_question(q, {"scores": {"A": -5, "B": "x"}}))
        self.assertTrue(grade_question(q, {"scores": {"A": 99}}))  # clamped to 2 of 4 -> still half

    def test_math_mark_needs_geometry_points(self):
        config = load_exam_config("oge-math")
        algebra_only = {str(n): 1 for n in range(1, 15)} | {"20": 2, "21": 2, "22": 2}  # 20 points, no geometry
        self.assertEqual(compute_mark(config, algebra_only, {})[0], 2)
        with_geometry = dict(algebra_only, **{"15": 1, "16": 1})  # 22 points
        mark, notes = compute_mark(config, with_geometry, {})
        self.assertEqual((mark, notes), (5, []))
        self.assertEqual(compute_mark(config, dict(with_geometry, **{"21": 0}), {})[0], 4)
        self.assertEqual(compute_mark(config, {"6": 1}, {})[0], 2)

    def test_russian_mark_is_capped_by_literacy(self):
        config = load_exam_config("oge-russian")
        points = {"13": 8, "1": 6, "ГК": 7} | {str(n): 1 for n in range(2, 13)}  # 32 points
        self.assertEqual(compute_mark(config, points, {"ГК1": 2, "ГК2": 2, "ГК3": 2, "ФК1": 1})[0], 4)
        mark, notes = compute_mark(config, points, {"ГК1": 1, "ГК2": 2, "ГК3": 1, "ФК1": 2})
        self.assertEqual(mark, 3)
        self.assertEqual(len(notes), 1)
        top = dict(points, ГК=12)  # 37 points
        self.assertEqual(compute_mark(config, top, {"ГК1": 3, "ГК2": 3, "ГК3": 3, "ГК4": 1, "ФК1": 2})[0], 5)
        self.assertEqual(compute_mark(config, top, {"ГК1": 3, "ГК2": 3, "ГК3": 2, "ГК4": 0})[0], 4)

    def test_variant_takes_one_question_per_task_and_keeps_sets_together(self):
        config = {"tasks": [{"id": "1"}, {"id": "2"}, {"id": "6"}, {"id": "9"}]}
        questions = [
            FakeExamQuestion(1, "1", topic_id=1, exam_set="a", question_task="1"),
            FakeExamQuestion(2, "1", topic_id=1, exam_set="a", question_task="2"),
            FakeExamQuestion(3, "1", topic_id=1, exam_set="b", question_task="1"),
            FakeExamQuestion(4, "1", topic_id=1, exam_set="b", question_task="2"),
            FakeExamQuestion(5, "6", topic_id=2),
            FakeExamQuestion(6, "6", topic_id=2, exam=True),
        ]
        for seed in range(20):
            variant = build_variant(config, questions, random.Random(seed))
            by_task = {v["task"]: v["question_id"] for v in variant}
            self.assertEqual(set(by_task), {"1", "2", "6"})  # task 9 has no questions -> skipped
            self.assertIn((by_task["1"], by_task["2"]), [(1, 2), (3, 4)])
            self.assertEqual(by_task["6"], 6)  # exam-format question preferred

    def test_oge_content_matches_exam_config(self):
        for slug in ("oge-math", "oge-russian"):
            config = load_exam_config(slug)
            task_ids = {t["id"] for t in config["tasks"]}
            self.assertEqual(sum(t["points"] for t in config["tasks"]), {"oge-math": 31, "oge-russian": 38}[slug])
            manifest = json.loads((CONTENT / slug / "topics.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["subject"]["grade"], 9)
            topics = [t for sec in manifest["sections"] for t in sec["topics"]]
            # every КИМ task has a home; math 2-5 live in the shared 1-5 block topic (per-question exam_task)
            shared_block = {"2", "3", "4", "5"} if slug == "oge-math" else set()
            self.assertEqual({t["exam_task"] for t in topics} | shared_block, task_ids)
            for t in topics:
                quiz_path = CONTENT / slug / t["slug"] / "quiz.json"
                if not quiz_path.exists():
                    continue
                task = next(x for x in config["tasks"] if x["id"] == t["exam_task"])
                for q in json.loads(quiz_path.read_text(encoding="utf-8"))["questions"]:
                    self.assertIn(q.get("exam_task", t["exam_task"]), task_ids)
                    if q["type"] == "self_check":
                        self.assertTrue(q["criteria"])
                        self.assertEqual(sum(c["max"] for c in q["criteria"]), task["points"], t["slug"])
                    elif task.get("self_check"):
                        self.fail(f"{t['slug']}: task {task['id']} is self-checked, question is {q['type']}")

    def test_every_grade_has_a_generated_calendar(self):
        content = Path(__file__).resolve().parents[1] / "content"
        for grade in (5, 6):
            schedule = content / f"schedule-{grade}.json"
            self.assertTrue(schedule.exists())
            data = json.loads(schedule.read_text(encoding="utf-8"))
            self.assertEqual(len(data["days"]), 166)


if __name__ == "__main__":
    unittest.main()
