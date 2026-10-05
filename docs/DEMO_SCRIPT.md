# Demo Script — Apertus Evidence Ledger

Target length: 2–3 minutes.

## Before recording

- Use only the synthetic sample/evaluation documents in this repository.
- Do not show API keys, environment-variable values, browser profiles, personal files, or unrelated terminals.
- Start the local Apertus endpoint and index `examples/sample-policy.md`.
- Start `apertus-evidence-web` on `127.0.0.1:8787`.
- Keep the repository and `docs/TECHNICAL_REPORT.md` ready for the final section.

## 0:00–0:20 — Problem

Say:

> This is Apertus Evidence Ledger, a local-first document assistant for workflows where a plausible answer is not enough. The goal is to make the evidence behind an Apertus answer machine-verifiable while keeping the document pipeline under operator control.

Show the browser UI header.

## 0:20–0:45 — Local / sovereign architecture

Say:

> Documents are chunked and indexed locally with SQLite FTS5. Each chunk gets a SHA-256 fingerprint. Only retrieved evidence goes to Apertus. No hosted vector database, embedding API, analytics SDK, or proprietary model is required.

Briefly show the architecture section in the README or technical report.

## 0:45–1:25 — Grounded answer

Ask:

> How long are operational incident records retained after closure?

Show the result.

Point out:

- the answer;
- the **VERIFIED** status;
- the exact source quote;
- the retrieved chunk ID;
- the support-gate result;
- the evidence digest;
- the model-output digest.

Say:

> Apertus generates the language answer, but deterministic code decides whether the citation is acceptable. Unknown chunk IDs and fabricated quotes are rejected.

## 1:25–1:50 — Abstention

Ask a question not answered by the document, for example:

> Which encryption algorithm protects the incident records?

Show the abstention.

Say:

> The first Apertus pass is an evidence-sufficiency gate. If the retrieved evidence does not contain the requested fact, the system abstains instead of asking the answer generator to guess.

## 1:50–2:15 — Untrusted document content

Show `eval/multilingual.jsonl` or the evaluation summary.

Say:

> Retrieved documents are treated as untrusted data. The regression suite includes malicious text inside documents that tells the model to ignore system rules and invent missing facts. Those cases must still abstain.

Show `eval/results/2026-10-05-apertus-local-q4.json`.

Current validated result:

- 18 / 18 real-model regression cases;
- 6 grounded answers;
- 6 missing-information abstentions;
- 6 document prompt-injection abstentions;
- 6 languages: English, Spanish, German, French, Italian and Romansh;
- 15 / 15 software tests.

Add:

> This is a small synthetic engineering regression suite, not a claim of general 100 percent model accuracy.

## 2:15–2:40 — Why Apertus

Say:

> Apertus is used where probabilistic language reasoning is useful. Retrieval integrity, hashing and citation acceptance remain deterministic. The full pipeline can run locally; during development Apertus 1.5 8B ran quantized on a 16 GB consumer GPU.

## 2:40–3:00 — Close

Say:

> The result is a small open blueprint for auditable, sovereign document QA: local retrieval, Apertus reasoning, exact evidence verification and an answer ledger that can be inspected after every response.

End on the project UI and repository name.

## Recording acceptance checklist

The final video should visibly demonstrate:

- a real Apertus-backed answer;
- at least one exact verified citation;
- evidence/model-output hashes;
- one unsupported-question abstention;
- the current evaluation summary;
- the public repository name.

Do not claim the small synthetic evaluation is a general Apertus benchmark.
