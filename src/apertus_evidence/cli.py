from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .model import ApertusClient
from .service import EvidenceService
from .store import EvidenceStore


class _NoModel:
    model = "unused"

    def generate_json(self, *, system: str, user: str) -> dict:
        raise RuntimeError("not used")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apertus-evidence")
    parser.add_argument("--db", default="evidence.db", help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Index a UTF-8 text/Markdown document")
    ingest.add_argument("path")

    ask = sub.add_parser("ask", help="Ask an evidence-grounded question")
    ask.add_argument("question")
    ask.add_argument(
        "--base-url",
        default=(
            os.getenv("LLM_BASE_URL")
            or os.getenv("APERTUS_BASE_URL", "http://localhost:8000/v1")
        ),
    )
    ask.add_argument(
        "--model",
        default=(
            os.getenv("LLM_NAME")
            or os.getenv("APERTUS_MODEL", "swiss-ai/Apertus-v1.5-8B")
        ),
    )
    ask.add_argument("--api-key-env", default="LLM_API_KEY")
    ask.add_argument("--top-k", type=int, default=6)
    ask.add_argument("--ledger-out")

    return parser


def main() -> int:
    args = build_parser().parse_args()
    with EvidenceStore(args.db) as store:
        if args.command == "ingest":
            service = EvidenceService(store, _NoModel())
            doc_id = service.ingest_file(args.path)
            print(
                json.dumps(
                    {
                        "indexed": True,
                        "document_id": doc_id,
                        "source": args.path,
                    }
                )
            )
            return 0

        api_key = os.getenv(args.api_key_env) if args.api_key_env else None
        if not api_key and args.api_key_env == "LLM_API_KEY":
            api_key = os.getenv("APERTUS_API_KEY")
        client = ApertusClient(
            base_url=args.base_url,
            model=args.model,
            api_key=api_key,
        )
        service = EvidenceService(store, client)
        result = service.answer(args.question, top_k=args.top_k)

        payload = {
            "answer": result.answer,
            "abstain": result.abstain,
            "citations": list(result.citations),
            "ledger": result.ledger,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))

        if args.ledger_out:
            Path(args.ledger_out).write_text(
                json.dumps(result.ledger, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
