from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apertus_evidence.chunking import chunk_text
from apertus_evidence.service import (
    EvidenceService,
    EvidenceVerificationError,
    verify_model_answer,
)
from apertus_evidence.store import EvidenceStore, SearchHit


class FakeModel:
    model = "fake-apertus"

    def __init__(self, output: dict):
        self.output = output

    def generate_json(self, *, system: str, user: str) -> dict:
        return self.output


class ChunkingTests(unittest.TestCase):
    def test_chunking_is_deterministic_and_overlapping(self):
        text = ("alpha beta gamma delta\n" * 120).strip()
        first = chunk_text(text, max_chars=300, overlap=50)
        second = chunk_text(text, max_chars=300, overlap=50)
        self.assertEqual(first, second)
        self.assertGreater(len(first), 1)
        self.assertTrue(all(c.text.strip() for c in first))
        self.assertLess(first[1].start_offset, first[0].end_offset)


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
                service.model = FakeModel(
                    {
                        "answer": "The retention period is ninety days.",
                        "abstain": False,
                        "citations": [
                            {
                                "chunk_id": hit.chunk_id,
                                "quote": "The retention period is ninety days.",
                            }
                        ],
                    }
                )
                result = service.answer("What is the retention period?")
                self.assertFalse(result.abstain)
                self.assertEqual(result.citations[0]["chunk_id"], hit.chunk_id)
                self.assertIn("evidence_digest_sha256", result.ledger)

    def test_unknown_citation_is_rejected(self):
        hits = [
            SearchHit(
                chunk_id=7,
                source="x",
                ordinal=0,
                text="Only approved operators may access the system.",
                sha256="a" * 64,
                rank=0.0,
            )
        ]
        with self.assertRaises(EvidenceVerificationError):
            verify_model_answer(
                {
                    "answer": "Anyone can access it.",
                    "abstain": False,
                    "citations": [{"chunk_id": 999, "quote": "Anyone"}],
                },
                hits,
            )

    def test_non_exact_quote_is_rejected(self):
        hits = [
            SearchHit(
                chunk_id=7,
                source="x",
                ordinal=0,
                text="Only approved operators may access the system.",
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
                        {"chunk_id": 7, "quote": "All operators may access"}
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
                text="Only approved operators may access the system.",
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
                        "quote": "Only approved operators may access the system.",
                    }
                ],
            },
            hits,
        )
        self.assertFalse(abstain)
        self.assertEqual(answer, "Access is restricted.")
        self.assertEqual(citations[0]["chunk_id"], 7)

    def test_non_decimal_string_chunk_id_is_rejected(self):
        hits = [
            SearchHit(
                chunk_id=7,
                source="x",
                ordinal=0,
                text="Only approved operators may access the system.",
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
                            "quote": "Only approved operators may access the system.",
                        }
                    ],
                },
                hits,
            )


if __name__ == "__main__":
    unittest.main()
