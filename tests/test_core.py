import json
import unittest
from pathlib import Path

from app.auth import hash_password, verify_password
from app.routers.quiz import grade_question


class FakeOption:
    def __init__(self, option_id, correct):
        self.id = option_id
        self.is_correct = correct


class FakeQuestion:
    def __init__(self, question_type, options=None, answer=None, pairs=None):
        self.type = question_type
        self.options = options or []
        self.answer = answer
        self.pairs = pairs or []


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

    def test_every_grade_has_a_generated_calendar(self):
        content = Path(__file__).resolve().parents[1] / "content"
        for grade in (5, 6):
            schedule = content / f"schedule-{grade}.json"
            self.assertTrue(schedule.exists())
            data = json.loads(schedule.read_text(encoding="utf-8"))
            self.assertEqual(len(data["days"]), 166)


if __name__ == "__main__":
    unittest.main()
