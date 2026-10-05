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
        text = ("alpha beta gamma delta