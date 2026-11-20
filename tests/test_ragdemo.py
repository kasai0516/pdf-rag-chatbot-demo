import json
import os
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from ragdemo import server
from ragdemo.answer import NOT_FOUND, answer
from ragdemo.evaluate import evaluate
from ragdemo.index import BM25Index, load_passages, split_sentences, stem, terms

ROOT = Path(__file__).resolve().parents[1]
INDEX = BM25Index(load_passages([ROOT / "samples"]))


class TextTests(unittest.TestCase):
    def test_stem_matches_word_forms(self):
        self.assertEqual(stem("refunded"), stem("refund"))
        self.assertEqual(stem("backups"), "backup")
        self.assertEqual(stem("access"), "access")  # no over-stemming of -ss

    def test_stopwords_removed(self):
        self.assertEqual(terms("What is the refund period?"), ["refund", "period"])


class AnswerTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("RAGDEMO_USE_CLAUDE", None)  # tests always run offline

    def test_answer_quotes_the_source_page(self):
        result = answer(INDEX, "What is the refund period for annual plans?")
        self.assertFalse(result.refused)
        self.assertIn("14 days", result.text)
        self.assertIn("northwind_terms.pdf p.1", result.text)

    def test_declines_when_documents_do_not_cover_it(self):
        result = answer(INDEX, "Is there a discount for students?")
        self.assertTrue(result.refused)
        self.assertEqual(result.text, NOT_FOUND)

    def test_no_headings_in_answers(self):
        result = answer(INDEX, "How long are backups kept?")
        self.assertNotIn("3. Data and backups", result.text)

    def test_right_subject_comes_first(self):
        # The question is about monthly plans: the monthly rule must lead, not the annual one.
        result = answer(INDEX, "Can monthly plans be refunded within 14 days?")
        self.assertTrue(result.text.startswith("Monthly plans are not refundable"))

    def test_right_subject_first_for_long_question(self):
        q = "Can monthly plans be refunded in full within 14 days of purchase or after cancellation?"
        result = answer(INDEX, q)
        self.assertIn("Monthly plans are not refundable", result.text)
        self.assertNotIn("Annual plans can be refunded", result.text)

    def test_polite_filler_does_not_cause_a_refusal(self):
        result = answer(INDEX, "What is the refund period for annual plans? Please give me a short answer.")
        self.assertFalse(result.refused)
        self.assertIn("14 days", result.text)


class SentenceTests(unittest.TestCase):
    def test_wrapped_lines_are_rejoined(self):
        text = "2. Refunds\nAnnual plans can be refunded in full within\n14 days of purchase. Monthly plans are not\nrefundable."
        self.assertEqual(
            split_sentences(text),
            ["2. Refunds", "Annual plans can be refunded in full within 14 days of purchase.", "Monthly plans are not refundable."],
        )


class AbbreviationTests(unittest.TestCase):
    def test_abbreviations_do_not_split_sentences(self):
        text = "Customer data is stored in the U.S. East region. Backups run daily, e.g. at 02:00."
        self.assertEqual(
            split_sentences(text),
            ["Customer data is stored in the U.S. East region.", "Backups run daily, e.g. at 02:00."],
        )


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.pop("RAGDEMO_USE_CLAUDE", None)
        cls.port = 8799
        threading.Thread(target=server.serve, args=(INDEX, "127.0.0.1", cls.port), daemon=True).start()
        time.sleep(0.3)

    def post(self, body: bytes):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/ask", data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_valid_question(self):
        status, data = self.post(json.dumps({"question": "How much is extra storage?"}).encode())
        self.assertEqual(status, 200)
        self.assertIn("5 USD", data["answer"])

    def test_bad_inputs_get_400_not_a_crash(self):
        huge_int = b'{"question": "x", "n": ' + b"9" * 5000 + b"}"
        deep = b"[" * 4500 + b"]" * 4500
        for body in [b"{", b"[]", b'{"question": null}', b'{"question": ""}', huge_int, deep]:
            status, data = self.post(body)
            self.assertEqual(status, 400, body)
            self.assertIn("error", data)


class EvalTests(unittest.TestCase):
    def test_sample_question_set_passes(self):
        os.environ.pop("RAGDEMO_USE_CLAUDE", None)
        passed, total, _ = evaluate(INDEX, ROOT / "samples" / "questions.yaml")
        self.assertEqual(passed, total)


if __name__ == "__main__":
    unittest.main()
