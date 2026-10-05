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

The official Apertus 1.5 model card documents vLLM serving with the model `swiss-ai/Apertus-v1.5-8B`. This project consumes an OpenAI-compatible chat-completions endpoint, so the model can stay on infrastructure controlled by the operator.

For the zero-cost development smoke on Windows, the project was also exercised with `llama.cpp` and a third-party Q4_K_M GGUF derivative:

    llama-server -hf Colby/apertus-v1.5-8b-text-Q4_K_M-GGUF:Q4_K_M \
      --alias apertus-local --host 127.0.0.1 --port 8080 -c 4096 -ngl 99

That GGUF is a development convenience and is **not** claimed to be an official Hack Apertus-provided quantization.

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

MVP supports UTF-8 text and Markdown, a local browser UI, real Apertus-backed inference, a multilingual support gate, exact-quote verification, and a six-language grounded/abstention regression set. On the current per-case-isolated evaluator, the latest real local Apertus run passes 17/18 regression cases, 12/12 holdout cases, and 3/3 multi-evidence cases; the software suite passes 20/20 tests. The one regression miss is a supported Romansh case whose generated citation failed the exact-source-quote contract, so the system rejected it rather than accepting an unverifiable answer. A historical pre-isolation run passed 18/18 and is retained as an earlier artifact, not the current headline result. If a supported answer fails deterministic citation verification, the service permits one bounded correction attempt and then re-verifies the corrected output. The evaluation is deliberately small and synthetic; see `docs/TECHNICAL_REPORT.md` for methodology and limitations.

## Licensing

Hack Apertus output is split by artifact type to match the event terms:

- Source code and software configuration: **Apache License 2.0** (`LICENSE`).
- Documentation, designs, reports, and other non-code text authored for the project: **CC BY 4.0** (`LICENSES/CC-BY-4.0.txt`).
- Submitted evaluation dataset: **CDLA-Permissive-2.0** (`LICENSES/CDLA-Permissive-2.0.txt`).

Third-party components retain their own licenses.


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

## Evaluation

The main regression/hardening set lives at `eval/multilingual.jsonl` and currently contains 18 synthetic cases across English, Spanish, German, French, Italian, and Romansh:

- 6 grounded supported questions;
- 6 missing-information abstentions;
- 6 retrieved-document prompt-injection abstentions.

A separate `eval/holdout.jsonl` contains 12 synthetic cases (6 grounded + 6 abstentions) across the same six languages. It passed 12/12 in the original frozen holdout run and again in the October 6 per-case-isolated revalidation. An additional `eval/multievidence.jsonl` set exercises questions that require citing two facts from separated chunks; the current isolated real-model run passes 3/3. The October 6 raw summaries are frozen under `eval/results/`.

Run either dataset against a real Apertus endpoint:

    apertus-evidence-eval --dataset eval/multilingual.jsonl --base-url http://127.0.0.1:8080/v1 --model apertus-local --out evaluation-report.json

Grounded cases pass only when verified citations contain all required source evidence. Unsupported and injection cases pass only when the system abstains with zero citations. Invalid chunk IDs or invented quotes fail in the deterministic verifier.

These are small synthetic engineering regression/holdout sets, not statistically representative benchmarks of general Apertus accuracy. See `docs/TECHNICAL_REPORT.md` for methodology and limitations.