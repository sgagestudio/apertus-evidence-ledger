# Apertus Evidence Ledger

A new Hack Apertus 2026 Track 2B prototype started after the official 1 October 12:00 CEST hacking start.

Apertus Evidence Ledger is a local-first evidence-grounded assistant designed for regulated or privacy-sensitive document workflows. It deliberately keeps retrieval and verification deterministic and local, while Apertus 1.5 is used only for the language reasoning step.

## Why this exists

Normal RAG demos often make citations a presentation feature. This project treats evidence as a machine-verifiable contract:

1. Source documents are chunked locally.
2. Each chunk receives a SHA-256 digest.
3. Retrieval runs locally with SQLite FTS5; no external vector database is required.
4. Apertus receives only the retrieved evidence blocks and must return structured citations.
5. Every citation must include an exact quote from a retrieved chunk.
6. The verifier rejects unknown chunk IDs or fabricated quotes.
7. Each answer emits an evidence ledger with the retrieved chunk hashes and model-output digest.

This creates a narrow, auditable path from source bytes to generated answer without requiring a closed embedding API, managed vector store, or proprietary model.

## Hack Apertus fit

Track: 2B — Apertus Adoption: Own Project

The design targets the published judging criteria:

- Purposeful use of AI: Apertus performs evidence-constrained synthesis rather than deterministic work.
- Technical rigour: exact-quote verification, source digests, deterministic retrieval and regression tests.
- Value, cost and scalability: SQLite FTS5 avoids an always-on vector service for small and medium document sets.
- Sovereign deployability: the complete data plane can run on one machine with a local Apertus endpoint.
- Implementation feasibility: Python standard library plus SQLite, with an OpenAI-compatible Apertus endpoint.

## Architecture

    UTF-8 / Markdown source
            |
            v
      deterministic chunking
            |
            +--> SHA-256 per chunk
            |
            v
         SQLite FTS5
            |
         top-k evidence
            |
            v
      Apertus 1.5 endpoint
            |
      structured JSON answer
            |
            v
       citation verifier
       - known chunk IDs only
       - exact source quote
            |
            v
       evidence ledger JSON

## Quick start

Python 3.11+ is enough for indexing, retrieval and tests.

    python -m venv .venv
    .venv\Scripts\activate
    pip install -e .

Index the included example:

    apertus-evidence --db demo.db ingest examples/sample-policy.md

Run Apertus 1.5 behind an OpenAI-compatible vLLM endpoint, then ask:

    apertus-evidence --db demo.db ask "How long are incident records retained?" --ledger-out ledger.json

The default endpoint is http://localhost:8000/v1 and the default model name is swiss-ai/Apertus-v1.5-8B. They can also be set through APERTUS_BASE_URL and APERTUS_MODEL. APERTUS_API_KEY is optional for endpoints that require authentication.

## Apertus local serving

The official Apertus 1.5 model card documents vLLM serving with the model swiss-ai/Apertus-v1.5-8B. This project consumes the resulting OpenAI-compatible chat-completions endpoint, so the model can stay on infrastructure controlled by the operator.

## Verification behavior

A non-abstaining model response is accepted only when:

- answer is non-empty;
- citations is a non-empty array;
- every citation references a chunk retrieved for this question;
- every citation quote is an exact substring of that chunk;
- no quote exceeds the configured defensive bound.

If retrieval returns nothing, the system abstains without invoking the model.

## Tests

    PYTHONPATH=src python -m unittest discover -s tests -v
    python -m compileall -q src tests

CI runs both checks on every push and pull request.

## Current scope

MVP supports UTF-8 text and Markdown. Next work for the hackathon is a small browser UI, PDF extraction with clear provenance boundaries, multilingual retrieval evaluation and a real Apertus-backed demo/evaluation set.

## License

MIT.


## Browser demo

After indexing at least one document, run:

    apertus-evidence-web

By default the UI binds only to `127.0.0.1:8787`. It sends questions to the same evidence-verification pipeline used by the CLI and displays the verified citations plus the answer ledger.

Environment variables:

- `APERTUS_EVIDENCE_DB` — SQLite database path.
- `APERTUS_BASE_URL` — OpenAI-compatible Apertus endpoint.
- `APERTUS_MODEL` — served model name.
- `APERTUS_API_KEY` — optional endpoint token.
- `APERTUS_WEB_HOST` / `APERTUS_WEB_PORT` — bind address/port.

## Multilingual grounded evaluation

A small reproducible four-language evaluation set lives at `eval/multilingual.jsonl` (English, Spanish, German and French).

Run it against a real Apertus endpoint:

    apertus-evidence-eval --dataset eval/multilingual.jsonl --base-url http://localhost:8000/v1 --out evaluation-report.json

A case passes only when Apertus returns a non-abstaining answer and its verified citations contain the required source evidence. Invalid chunk IDs or invented quotes fail earlier in the citation verifier, so the reported grounded accuracy is measured after structural verification.
