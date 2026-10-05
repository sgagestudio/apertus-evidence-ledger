# Technical Report — Apertus Evidence Ledger

## 1. Project summary

Apertus Evidence Ledger is a local-first evidence-grounded assistant for document workflows where source traceability, data control, and reproducibility matter.

The project uses Apertus for the language-reasoning step while keeping ingestion, chunking, retrieval, evidence hashing, citation validation, and answer auditing deterministic and locally deployable.

Track: **2B — Apertus Adoption: Own Project**

## 2. Problem

A typical retrieval-augmented generation demo can display citations without proving that those citations correspond to the retrieved source text. It may also depend on a managed vector database, proprietary embeddings, or a hosted closed model.

For regulated and privacy-sensitive workflows, this makes three questions harder to answer:

1. Which exact source evidence was available to the model?
2. Did the model cite text that actually exists in that evidence?
3. Can the workflow run without exporting the document corpus to a third-party service?

Apertus Evidence Ledger treats evidence as a machine-verifiable boundary rather than a presentation feature.

## 3. Architecture

The current pipeline is:

1. Read local UTF-8/Markdown source material.
2. Chunk it deterministically while preserving source offsets.
3. Compute SHA-256 for each chunk.
4. Index chunk text in SQLite FTS5.
5. Retrieve a bounded top-k evidence set for a question.
6. Send only those evidence blocks plus the question to Apertus.
7. Require structured JSON containing:
   - answer;
   - abstention flag;
   - citations with retrieved chunk IDs and short exact quotes.
8. Verify each citation before returning the answer:
   - chunk ID must belong to the retrieved evidence set;
   - quote must be non-empty and bounded;
   - quote must occur verbatim in the cited chunk.
9. Emit an evidence ledger containing retrieved chunk hashes, model name, question, evidence-set digest, and model-output digest.

If retrieval returns no relevant evidence, the model is not called and the system abstains.

## 4. Purposeful use of Apertus

Deterministic components handle deterministic work: indexing, retrieval, hashing, validation, and provenance.

Apertus is used for the part that benefits from a language model: synthesizing an answer from heterogeneous evidence and deciding when the supplied evidence is insufficient.

This separation makes the model replaceable while keeping the evidence contract stable and testable.

## 5. Technical rigour

### Citation verification

A non-abstaining answer is rejected unless it contains at least one citation. A citation is accepted only when it references a retrieved chunk and its quoted text is an exact substring of that chunk.

During real-model testing, Apertus returned a numeric chunk identifier as the JSON string `"1"` rather than the integer `1`. The verifier was intentionally not weakened to general coercion. It now accepts only ASCII decimal strings and normalizes them to integers; floats, booleans, signs, padded values, and arbitrary strings remain invalid.

### Defensive boundaries

The local browser API currently:
- binds to `127.0.0.1` by default;
- limits request bodies;
- bounds question length;
- returns no-store responses;
- sets `X-Content-Type-Options: nosniff`;
- denies framing.

The model endpoint is not exposed by the application.

### Regression tests

The repository has unit tests covering deterministic chunking, local search, valid citation verification, unknown citation rejection, fabricated quote rejection, strict numeric-ID normalization, evaluation-data validation, rejected model-output handling, and the browser UI surface.

## 6. Sovereign deployment

The full data path can run on one operator-controlled machine:

- Python standard library application;
- SQLite/FTS5 retrieval;
- local source documents;
- local Apertus inference through an OpenAI-compatible endpoint.

No external vector database, embedding service, analytics SDK, or proprietary model is required.

For development, Apertus 1.5 8B was run locally through `llama.cpp` with a Q4_K_M GGUF derivative. The application itself remains endpoint-compatible so operators can instead use another self-hosted Apertus runtime such as vLLM.

## 7. Cost and scalability

The current MVP has a direct cash cost of **EUR 0**.

SQLite FTS5 avoids operating a separate vector service for small and medium document collections. This design is intentionally simple and inexpensive rather than claiming to solve internet-scale retrieval.

For larger corpora, the retrieval interface can be replaced while preserving the same evidence-hash and citation-verification contract.

## 8. Real model validation

A real local Apertus 1.5 8B Q4_K_M runtime was exercised on an NVIDIA RTX 3080 Ti Laptop GPU with 16 GB VRAM.

Observed development smoke:
- local model successfully loaded with a 4096-token context;
- a grounded question returned the correct source-supported answer;
- the exact source quote passed verification;
- an evidence ledger was emitted;
- generation after model load was approximately 7.6 tokens/second in the observed short runs.

The final current regression suite contains 12 cases across English, Spanish, German, French, Italian, and Romansh: six grounded questions and six deliberately unsupported questions.

The latest real local Apertus run passed **12/12** cases:
- grounded answers: **6/6**;
- correct abstentions: **6/6**;
- software regression tests: **14/14**.

An earlier run passed 11/12 because the support gate was over-conservative on a supported Romansh case. The fix was general rather than case-specific: the support prompt now explicitly instructs Apertus to judge evidence in its own language, including low-resource languages. The complete suite then passed 12/12.

These results are engineering regression evidence on a small synthetic set, not a statistically representative benchmark of Apertus quality.

## 9. Evaluation methodology

Each grounded test case contains:
- source text;
- question;
- language;
- required evidence substring.

It passes only when:
1. the model does not abstain;
2. the answer survives structural/citation verification;
3. the verified citations contain the required source evidence.

Adversarial missing-information cases declare `expected_abstain=true`. They pass only if the model abstains and returns no citations.

Malformed or unverifiable model outputs are recorded as failures rather than silently repaired by the evaluator.

## 10. Browser demo

The included local browser UI provides:
- a question input;
- a call to the same `/api/ask` evidence pipeline used by the CLI;
- verified citations;
- the evidence ledger.

The UI is intentionally small so evaluation focuses on the evidence workflow rather than front-end complexity.

## 11. Reproducibility

Core checks:

    PYTHONPATH=src python -m unittest discover -s tests -v
    python -m compileall -q src tests

Index sample evidence:

    apertus-evidence --db demo.db ingest examples/sample-policy.md

Run the browser UI:

    apertus-evidence-web

Run evaluation against an OpenAI-compatible Apertus endpoint:

    apertus-evidence-eval \
      --dataset eval/multilingual.jsonl \
      --base-url http://localhost:8000/v1 \
      --model apertus-local \
      --out evaluation-report.json

## 12. Limitations

The current prototype intentionally has narrow scope.

- FTS5 is lexical retrieval, not semantic retrieval.
- The present evaluation dataset is small and synthetic.
- Exact-quote verification proves citation fidelity, not that every sentence in a longer generated answer is semantically entailed by the evidence.
- UTF-8 text and Markdown are the primary ingestion formats; PDF provenance boundaries are not implemented yet.
- The current browser UI is local-only and not a multi-user service.
- Quantized local inference trades some model fidelity for accessibility on consumer hardware.

These are explicit boundaries rather than hidden fallbacks.

## 13. Next steps before submission

1. Improve the browser presentation of evidence and source hashes.
2. Add a deliberately adversarial citation-fabrication demo.
3. Capture final screenshots and a short demo.
4. Re-run and freeze the final evaluation artifact immediately before submission.
5. Finalize the organizer submission materials before 16 October 2026, 12:00 CEST.

A compact machine-readable result from the current real-model run is stored at `eval/results/2026-10-05-apertus-local-q4.json`.

## 14. Open-source status

The project is public. Hackathon artifacts are licensed by type to match the Hack Apertus terms:

- source code and software configuration: **Apache License 2.0**;
- documentation, designs, reports, and other project text: **CC BY 4.0**;
- submitted evaluation data: **CDLA-Permissive-2.0**.

Third-party components retain their respective licences.
