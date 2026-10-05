from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .model import ApertusClient, ModelError
from .service import EvidenceService, EvidenceVerificationError
from .store import EvidenceStore


@dataclass(frozen=True)
class EvalResult:
    case_id: str
    language: str
    passed: bool
    abstain: bool
    citation_count: int
    reason: str


def load_cases(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            required = {"id", "language", "source_text", "question"}
            if not isinstance(value, dict) or not required.issubset(value):
                raise ValueError(f"invalid evaluation case: {line[:80]}")
            expected_abstain = value.get("expected_abstain", False)
            if not isinstance(expected_abstain, bool):
                raise ValueError(f"expected_abstain must be boolean: {line[:80]}")
            if not expected_abstain and not isinstance(value.get("required_evidence_substring"), str):
                raise ValueError(f"grounded case needs required_evidence_substring: {line[:80]}")
            rows.append(value)
    if not rows:
        raise ValueError("evaluation dataset is empty")
    return rows


def evaluate_case(case: dict, service: EvidenceService) -> EvalResult:
    source = f"eval://{case['id']}"
    service.ingest_text(source=source, text=case["source_text"])
    try:
        result = service.answer(case["question"], top_k=4)
    except (EvidenceVerificationError, ModelError) as exc:
        return EvalResult(
            case_id=case["id"],
            language=case["language"],
            passed=False,
            abstain=False,
            citation_count=0,
            reason=f"rejected model output: {exc}",
        )

    expected_abstain = case.get("expected_abstain", False)
    if expected_abstain:
        passed = result.abstain and not result.citations
        reason = "correct abstention" if passed else "expected abstention but model answered"
    else:
        required = " ".join(case["required_evidence_substring"].split())
        cited = " ".join(
            " ".join(citation["quote"].split())
            for citation in result.citations
        )
        passed = not result.abstain and required in cited
        reason = "grounded evidence found" if passed else (
            "unexpected abstention" if result.abstain else "required evidence was not cited"
        )
    return EvalResult(
        case_id=case["id"],
        language=case["language"],
        passed=passed,
        abstain=result.abstain,
        citation_count=len(result.citations),
        reason=reason,
    )


def run_evaluation(dataset: str, client: ApertusClient) -> dict:
    cases = load_cases(dataset)
    results: list[EvalResult] = []
    with tempfile.TemporaryDirectory() as tmp:
        with EvidenceStore(Path(tmp) / "eval.db") as store:
            service = EvidenceService(store, client)
            for case in cases:
                results.append(evaluate_case(case, service))

    passed = sum(item.passed for item in results)
    return {
        "model": client.model,
        "cases": len(results),
        "passed": passed,
        "grounded_accuracy": passed / len(results),
        "results": [asdict(item) for item in results],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="eval/multilingual.jsonl")
    parser.add_argument("--base-url", default="http://localhost:8000/v1")
    parser.add_argument("--model", default="swiss-ai/Apertus-v1.5-8B")
    parser.add_argument("--api-key")
    parser.add_argument("--out")
    args = parser.parse_args()

    report = run_evaluation(
        args.dataset,
        ApertusClient(base_url=args.base_url, model=args.model, api_key=args.api_key),
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0 if report["passed"] == report["cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
