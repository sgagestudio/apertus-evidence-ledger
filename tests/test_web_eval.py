from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apertus_evidence.evaluation import load_cases
from apertus_evidence.web import INDEX_HTML, MAX_BODY_BYTES


class WebTests(unittest.TestCase):
    def test_ui_exposes_question_form_and_api(self):
        self.assertIn("Apertus Evidence Ledger", INDEX_HTML)
        self.assertIn("/api/ask", INDEX_HTML)
        self.assertGreater(MAX_BODY_BYTES, 4000)


class EvaluationDatasetTests(unittest.TestCase):
    def test_loader_accepts_multilingual_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.jsonl"
            path.write_text(
                '{"id":"x","language":"es","source_text":"dato importante",'
                '"question":"¿dato?","required_evidence_substring":"dato"}\n',
                encoding="utf-8",
            )
            cases = load_cases(path)
            self.assertEqual(cases[0]["language"], "es")

    def test_loader_rejects_missing_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.jsonl"
            path.write_text('{"id":"x"}\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_cases(path)


    def test_loader_accepts_abstention_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.jsonl"
            path.write_text(
                '{"id":"x","language":"en","source_text":"retained 30 days",'
                '"question":"which cloud?","expected_abstain":true}\n',
                encoding="utf-8",
            )
            cases = load_cases(path)
            self.assertTrue(cases[0]["expected_abstain"])

    def test_loader_rejects_grounded_case_without_required_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.jsonl"
            path.write_text(
                '{"id":"x","language":"en","source_text":"a","question":"b"}\n',
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_cases(path)


if __name__ == "__main__":
    unittest.main()
