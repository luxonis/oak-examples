import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from decision import parse_answers, validate_questions


QUESTION = {
    "type": "noul",
    "instructions": "Is the object damaged?",
    "options": [
        {"label": "Yes", "description": "Visible damage"},
        {"label": "No", "description": "No visible damage"},
    ],
}


class MultiQuestionTests(unittest.TestCase):
    def test_question_ids_and_probabilities_are_checked(self):
        questions = validate_questions([QUESTION, QUESTION])
        response = {
            "answers": {
                "q1": {"type": "noul", "noul": 0.8},
                "q2": {"type": "noul", "noul": 0.1},
            }
        }
        answers = parse_answers(response, questions)
        self.assertEqual([a["yes_probability"] for a in answers], [0.8, 0.1])
        del response["answers"]["q2"]
        with self.assertRaises(ValueError):
            parse_answers(response, questions)

    def test_question_count_is_bounded(self):
        with self.assertRaises(ValueError):
            validate_questions([QUESTION] * 5)


if __name__ == "__main__":
    unittest.main()
