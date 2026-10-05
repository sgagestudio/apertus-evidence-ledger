from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apertus_evidence.chunking import chunk_text
from apertus_evidence.service import (
    SUPPORT_PROMPT,
    EvidenceService,
    EvidenceVerificationError,
    verify_model_answer,
    verify_support_gate,
)
from apertus_evidence.store import EvidenceStore, SearchHit


class FakeModel:
    model = "fake-apertus"

    def __init__(self, output: dict, *, support: bool = True):
        self.output = output
        self.support = support
        self.calls: list[str] = []

    def generate_json(self, *, system: str, user: str) -> dict:
        self.calls.append(system)
        if system == SUPPORT_PROMPT:
            return {"supported": self.support}
        return self.output


class ChunkingTests(unittest.TestCase):
    def test_chunking_is_deterministic_and_overlapping(self):
        text = ("alpha beta gamma delta\n" * 120).strip()
        first = chunk_text(text, max_chars=300, overlap=50)
        second = chunk_text(text, max_chars=300, overlap=50)
        self.assertEqual(first, second)
        self.assertGreater(len(first), 1)
        self.assertTrue(all(c.text.strip() for c in first))
        self.assertLess(
            first[1].start_offset,
            first[0].end_offset,
        )


class StoreAndServiceTests(unittest.TestCase):
    def test_search_and_verified_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "evidence.db"
            with EvidenceStore(db) as store:
                service = EvidenceService(store, FakeModel({}))
                service.ingest_text(
                    source="policy.md",
                    text=(
                        "The retention period is ninety days. "
                        "Active records must never be purged."
                    ),
                )
                hits = store.search("retention period")
                self.assertTrue(hits)

                hit = hits[0]
                model = FakeModel(
                    {
                        "answer": (
                            "The retention period is ninety days."
                        ),
                        "abstain": False,
                        "citations": [
                            {
                                "chunk_id": hit.chunk_id,
                                "quote": (
                                    "The retention period is "
                                    "ninety days."
                                ),
                            }
                        ],
                    }
                )
                service.model = model
                result = service.answer(
                    "What is the retention period?"
                )
                self.assertFalse(result.abstain)
                self.assertEqual(
                    result.citations[0]["chunk_id"],
                    hit.chunk_id,
                )
                self.assertTrue(
                    result.ledger["support_gate_supported"]
                )
                self.assertEqual(result.ledger["version"], 2)
                self.assertEqual(len(model.calls), 2)

    def test_support_gate_abstains_without_answer_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            with EvidenceStore(
                Path(tmp) / "evidence.db"
            ) as store:
                model = FakeModel(
                    {
                        "answer": "should not be generated",
                        "abstain": False,
                        "citations": [],
                    },
                    support=False,
                )
                service = EvidenceService(store, model)
                service.ingest_text(
                    source="policy.md",
                    text=(
                        "Incident records are retained for "
                        "90 days."
                    ),
                )
                result = service.answer(
                    "Which encryption algorithm protects "
                    "incident records?"
                )

        self.assertTrue(result.abstain)
        self.assertEqual(result.citations, ())
        self.assertFalse(
            result.ledger["support_gate_supported"]
        )
        self.assertEqual(len(model.calls), 1)

    def test_invalid_support_gate_is_rejected(self):
        with self.assertRaises(EvidenceVerificationError):
            verify_support_gate({"supported": "true"})
        with self.assertRaises(EvidenceVerificationError):
            verify_support_gate(
                {"supported": True, "reason": "extra"}
            )

    def test_unknown_citation_is_rejected(self):
        hits = [
            SearchHit(
                chunk_id=7,
                source="x",
                ordinal=0,
                text=(
                    "Only approved operators may access "
                    "the system."
                ),
                sha256="a" * 64,
                rank=0.0,
            )
        ]
        with self.assertRaises(EvidenceVerificationError):
            verify_model_answer(
                {
                    "answer": "Anyone can access it.",
                    "abstain": False,
                    "citations": [
                        {"chunk_id": 999, "quote": "Anyone"}
                    ],
                },
                hits,
            )

    def test_non_exact_quote_is_rejected(self):
        hits = [
            SearchHit(
                chunk_id=7,
                source="x",
                ordinal=0,
                text=(
                    "Only approved operators may access "
                    "the system."
                ),
                sha256="a" * 64,
                rank=0.0,
            )
        ]
        with self.assertRaises(EvidenceVerificationError):
            verify_model_answer(
                {
                    "answer": "Access is restricted.",
                    "abstain": False,
                    "citations": [
                        {
                            "chunk_id": 7,
                            "quote": "All operators may access",
                        }
                    ],
                },
                hits,
            )

    def test_decimal_string_chunk_id_is_normalized(self):
        hits = [
            SearchHit(
                chunk_id=7,
                source="x",
                ordinal=0,
                text=(
                    "Only approved operators may access "
                    "the system."
                ),
                sha256="a" * 64,
                rank=0.0,
            )
        ]
        answer, abstain, citations = verify_model_answer(
            {
                "answer": "Access is restricted.",
                "abstain": False,
                "citations": [
                    {
                        "chunk_id": "7",
                        "quote": (
                            "Only approved operators may "
                            "access the system."
                        ),
                    }
                ],
            },
            hits,
        )
        self.assertFalse(abstain)
        self.assertEqual(
            answer,
            "Access is restricted.",
        )
        self.assertEqual(citations[0]["chunk_id"], 7)

    def test_non_decimal_string_chunk_id_is_rejected(self):
        hits = [
            SearchHit(
                chunk_id=7,
                source="x",
                ordinal=0,
                text=(
                    "Only approved operators may access "
                    "the system."
                ),
                sha256="a" * 64,
                rank=0.0,
            )
        ]
        with self.assertRaises(EvidenceVerificationError):
            verify_model_answer(
                {
                    "answer": "Access is restricted.",
                    "abstain": False,
                    "citations": [
                        {
                            "chunk_id": "7.0",
                            "quote": (
                                "Only approved operators may "
                                "access the system."
                            ),
                        }
                    ],
                },
                hits,
            )


    def test_answer_retries_once_after_verification_failure(self):
        class RepairModel:
            model = "repair-apertus"

            def __init__(self):
                self.calls = 0

            def generate_json(self, *, system: str, user: str) -> dict:
                self.calls += 1
                if system == SUPPORT_PROMPT:
                    return {"supported": True}
                if self.calls == 2:
                    return {
                        "answer": "Retention is ninety days.",
                        "abstain": False,
                        "citations": [
                            {
                                "chunk_id": 1,
                                "quote": "Retention is 90 days.",
                            }
                        ],
                    }
                return {
                    "answer": "Retention is ninety days.",
                    "abstain": False,
                    "citations": [
                        {
                            "chunk_id": 1,
                            "quote": "The retention period is ninety days.",
                        }
                    ],
                }

        with tempfile.TemporaryDirectory() as tmp:
            with EvidenceStore(Path(tmp) / "evidence.db") as store:
                model = RepairModel()
                service = EvidenceService(store, model)
                service.ingest_text(
                    source="policy.md",
                    text="The retention period is ninety days.",
                )
                result = service.answer("What is the retention period?")

        self.assertFalse(result.abstain)
        self.assertEqual(len(result.citations), 1)
        self.assertEqual(model.calls, 3)
        self.assertEqual(result.ledger["answer_attempt_count"], 2)


if __name__ == "__main__":
    unittest.main()
