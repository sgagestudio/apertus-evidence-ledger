from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .chunking import chunk_text
from .model import JsonChatModel
from .store import EvidenceStore, SearchHit


SYSTEM_PROMPT = """You are an evidence-grounded assistant running on Apertus.
Use only the evidence blocks supplied by the user.
Return exactly one JSON object with this shape:
{
  "answer": "concise answer",
  "abstain": false,
  "citations": [
    {"chunk_id": 123, "quote": "short exact quote copied verbatim from that chunk"}
  ]
}
Rules:
- Every material factual claim must be supported by at least one citation.
- citation chunk_id values must come from the provided evidence.
- quote must be an exact substring of that cited chunk.
- If the evidence is insufficient, set abstain=true, explain the gap briefly in answer,
  and return an empty citations array.
- Do not reveal hidden reasoning or chain-of-thought.
"""


@dataclass(frozen=True)
class VerifiedAnswer:
    answer: str
    abstain: bool
    citations: tuple[dict, ...]
    ledger: dict


class EvidenceVerificationError(ValueError):
    pass


class EvidenceService:
    def __init__(self, store: EvidenceStore, model: JsonChatModel):
        self.store = store
        self.model = model

    def ingest_file(self, path: str | Path) -> int:
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        return self.ingest_text(source=str(path), text=text)

    def ingest_text(self, *, source: str, text: str) -> int:
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("document contains no indexable text")
        return self.store.replace_document(source, text, chunks)

    def answer(self, question: str, *, top_k: int = 6) -> VerifiedAnswer:
        hits = self.store.search(question, limit=top_k)
        if not hits:
            raw = {
                "answer": "No relevant evidence found.",
                "abstain": True,
                "citations": [],
            }
            return VerifiedAnswer(
                answer=raw["answer"],
                abstain=True,
                citations=(),
                ledger=self._ledger(question, hits, raw),
            )

        raw = self.model.generate_json(
            system=SYSTEM_PROMPT,
            user=self._build_prompt(question, hits),
        )
        answer, abstain, citations = verify_model_answer(raw, hits)
        return VerifiedAnswer(
            answer=answer,
            abstain=abstain,
            citations=tuple(citations),
            ledger=self._ledger(question, hits, raw),
        )

    @staticmethod
    def _build_prompt(question: str, hits: list[SearchHit]) -> str:
        blocks = []
        for hit in hits:
            blocks.append(
                "\n".join(
                    [
                        f"[EVIDENCE chunk_id={hit.chunk_id} source={json.dumps(hit.source)} sha256={hit.sha256}]",
                        hit.text,
                        "[/EVIDENCE]",
                    ]
                )
            )
        return f"Question:\n{question}\n\nEvidence:\n" + "\n\n".join(blocks)

    def _ledger(self, question: str, hits: list[SearchHit], raw: dict) -> dict:
        evidence_fingerprint = "\n".join(
            f"{hit.chunk_id}:{hit.sha256}" for hit in hits
        )
        return {
            "version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "model": self.model.model,
            "question": question,
            "retrieved": [
                {
                    "chunk_id": hit.chunk_id,
                    "source": hit.source,
                    "ordinal": hit.ordinal,
                    "sha256": hit.sha256,
                    "rank": hit.rank,
                }
                for hit in hits
            ],
            "evidence_digest_sha256": hashlib.sha256(
                evidence_fingerprint.encode("utf-8")
            ).hexdigest(),
            "model_output_digest_sha256": hashlib.sha256(
                json.dumps(raw, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest(),
        }


def _normalize_ws(value: str) -> str:
    return " ".join(value.split())


def verify_model_answer(raw: dict, hits: list[SearchHit]) -> tuple[str, bool, list[dict]]:
    answer = raw.get("answer")
    abstain = raw.get("abstain")
    citations = raw.get("citations")

    if not isinstance(answer, str) or not answer.strip():
        raise EvidenceVerificationError("model answer must be a non-empty string")
    if not isinstance(abstain, bool):
        raise EvidenceVerificationError("model abstain must be boolean")
    if not isinstance(citations, list):
        raise EvidenceVerificationError("model citations must be a list")

    if abstain:
        if citations:
            raise EvidenceVerificationError("abstaining answers must not contain citations")
        return answer.strip(), True, []

    if not citations:
        raise EvidenceVerificationError("non-abstaining answers require citations")

    by_id = {hit.chunk_id: hit for hit in hits}
    verified: list[dict] = []

    for item in citations:
        if not isinstance(item, dict):
            raise EvidenceVerificationError("each citation must be an object")
        chunk_id = item.get("chunk_id")
        quote = item.get("quote")

        # Models sometimes serialize an integer JSON field as a decimal string.
        # Accept that narrow representation only; never coerce floats, booleans,
        # signs, whitespace-padded values, or arbitrary strings.
        if isinstance(chunk_id, str) and chunk_id.isascii() and chunk_id.isdecimal():
            chunk_id = int(chunk_id)

        if isinstance(chunk_id, bool) or not isinstance(chunk_id, int) or chunk_id not in by_id:
            raise EvidenceVerificationError(f"citation references unknown chunk_id: {chunk_id!r}")
        if not isinstance(quote, str) or not quote.strip():
            raise EvidenceVerificationError("citation quote must be non-empty")
        if len(quote) > 500:
            raise EvidenceVerificationError("citation quote exceeds 500 characters")

        normalized_chunk = _normalize_ws(by_id[chunk_id].text)
        normalized_quote = _normalize_ws(quote)
        if normalized_quote not in normalized_chunk:
            raise EvidenceVerificationError(
                f"citation quote is not present in chunk_id {chunk_id}"
            )
        verified.append({"chunk_id": chunk_id, "quote": quote.strip()})

    return answer.strip(), False, verified
