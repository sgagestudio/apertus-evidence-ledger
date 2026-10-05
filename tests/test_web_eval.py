from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from apertus_evidence.evaluation import load_cases, run_evaluation
from apertus_evidence.web import INDEX_HTML, MAX_BODY_BYTES, _client_from_env


class WebTests(unittest.TestCase):
    def test_ui_exposes_question_form_and_api(self):
        self.assertIn("Apertus Evidence Ledger", INDEX_HTML)
        self.assertIn("/api/ask", INDEX_HTML)
        self.assertGreater(MAX_BODY_BYTES, 4000)

    def test_ui_exposes_verification_and_ledger(self):
        self.assertIn("Verified answer", INDEX_HTML)
        self.assertIn("Evidence ledger", INDEX_HTML)
        self.assertIn("support_gate_supported", INDEX_HTML)
        self.assertIn("evidence_digest_sha256", INDEX_HTML)

    def test_hack_apertus_standard_llm_environment(self):
        with patch.dict(
            os.environ,
            {
                "LLM_NAME": "apertus-ci",
                "LLM_BASE_URL": "http://model.example/v1",
                "LLM_API_KEY": "test-only-key",
                "APERTUS_MODEL": "legacy-model",
                "APERTUS_BASE_URL": "http://legacy.invalid/v1",
                "APERTUS_API_KEY": "legacy-key",
            },
            clear=True,
        ):
            client = _client_from_env()

        self.assertEqual(client.model, "apertus-ci")
        self.assertEqual(client.base_url, "http://model.example/v1")
        self.assertEqual(client.api_key, "test-only-key")


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


    def test_evaluator_records_verification_failure(self):
        from apertus_evidence.evaluation import evaluate_case
        from apertus_evidence.service import EvidenceService
        from apertus_evidence.store import EvidenceStore

        class InvalidModel:
            model = "invalid"
            def generate_json(self, *, system: str, user: str) -> dict:
                return {"answer": "unsupported answer", "abstain": False, "citations": []}

        with tempfile.TemporaryDirectory() as tmp:
            with EvidenceStore(Path(tmp) / "eval.db") as store:
                result = evaluate_case(
                    {
                        "id": "reject",
                        "language": "en",
                        "source_text": "Only approved auditors have access.",
                        "question": "Who has access?",
                        "required_evidence_substring": "Only approved auditors have access.",
                    },
                    EvidenceService(store, InvalidModel()),
                )
        self.assertFalse(result.passed)
        self.assertIn("rejected model output", result.reason)


    def test_loader_accepts_multiple_required_evidence_substrings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.jsonl"
            path.write_text(
                '{"id":"x","language":"en","source_text":"fact a fact b",'
                '"question":"both?","required_evidence_substrings":["fact a","fact b"]}\n',
                encoding="utf-8",
            )
            cases = load_cases(path)
            self.assertEqual(
                cases[0]["required_evidence_substrings"],
                ["fact a", "fact b"],
            )

    def test_loader_rejects_empty_required_evidence_substrings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.jsonl"
            path.write_text(
                '{"id":"x","language":"en","source_text":"fact",'
                '"question":"fact?","required_evidence_substrings":[]}\n',
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_cases(path)


    def test_run_evaluation_isolates_cases(self):
        import json
        import re

        class IsolationModel:
            model = "isolation-model"

            def generate_json(self, *, system: str, user: str) -> dict:
                if "evidence sufficiency gate" in system:
                    return {"supported": "BLUEBIRD" in user}
                match = re.search(r"chunk_id=(\d+)", user)
                if match is None:
                    raise AssertionError("missing chunk id in evaluation prompt")
                return {
                    "answer": "The code is BLUEBIRD.",
                    "abstain": False,
                    "citations": [
                        {
                            "chunk_id": int(match.group(1)),
                            "quote": "Legacy secret code is BLUEBIRD.",
                        }
                    ],
                }

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "isolation.jsonl"
            rows = [
                {
                    "id": "first",
                    "language": "en",
                    "source_text": "Legacy secret code is BLUEBIRD.",
                    "question": "What is the legacy secret code?",
                    "required_evidence_substring": "Legacy secret code is BLUEBIRD.",
                },
                {
                    "id": "second",
                    "language": "en",
                    "source_text": "Maintenance occurs every Sunday.",
                    "question": "What is the legacy secret code?",
                    "expected_abstain": True,
                },
            ]
            path.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )
            report = run_evaluation(str(path), IsolationModel())

        self.assertEqual(report["passed"], 2)
        self.assertTrue(report["results"][1]["abstain"])


if __name__ == "__main__":
    unittest.main()
