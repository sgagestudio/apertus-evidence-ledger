# Hack Apertus Submission Checklist

Track: **2B — Apertus Adoption: Own Project**  
Project: **Apertus Evidence Ledger**  
Deadline: **16 October 2026, 12:00 CEST**

The organizer states that the final submission is handled through the Hack Apertus website, not solely through the Devpost project page.

## Already complete

- [x] Owner joined Hack Apertus on Devpost.
- [x] Public repository created after the official hacking start.
- [x] Track 2B project concept implemented.
- [x] Real Apertus 1.5 local inference validated.
- [x] Deterministic local chunking + SQLite FTS5 retrieval.
- [x] SHA-256 evidence fingerprints.
- [x] Separate multilingual evidence-sufficiency gate.
- [x] Exact-quote / known-chunk citation verifier.
- [x] Explicit abstention flow.
- [x] Evidence ledger with evidence and model-output digests.
- [x] Local provenance-focused browser UI.
- [x] 18/18 current real-model regression cases.
- [x] 15/15 current software tests.
- [x] Document prompt-injection cases included.
- [x] Technical report committed.
- [x] Machine-readable evaluation result committed.
- [x] Code licensing: Apache-2.0.
- [x] Documentation/report licensing: CC-BY-4.0.
- [x] Evaluation data licensing: CDLA-Permissive-2.0.
- [x] Direct experiment spend remains EUR 0.

## Before final submission

- [ ] Expand with a few paraphrase / multi-chunk cases if they add signal without weakening reliability.
- [ ] Re-run clean-clone unit tests.
- [ ] Re-run real Apertus evaluation and freeze the final result.
- [ ] Capture final browser screenshots using synthetic data only.
- [ ] Record the short demo using `docs/DEMO_SCRIPT.md`.
- [ ] Convert/finalize the technical report in the format requested by the organizer.
- [ ] Check the organizer submission form for any newly added fields.
- [ ] Verify public repository visibility and README from an unauthenticated view.
- [ ] Verify all submission links work.
- [ ] Confirm no secrets, private data, employer material, or personal documents are in the repository/video/report.
- [ ] Submit through the organizer's official submission page before the deadline.

## Final facts to use consistently

### Project name
Apertus Evidence Ledger

### Elevator pitch
A local-first, auditable AI assistant powered by Apertus that grounds answers in your documents, verifies every citation against the source, and keeps sensitive data under your control.

### Core judging story
- **Purposeful AI:** Apertus performs language reasoning and evidence-sufficiency judgment.
- **Technical rigour:** deterministic retrieval boundaries, exact-quote validation, regression/adversarial tests.
- **Value / cost / scalability:** lightweight SQLite FTS5, no required managed vector service, EUR 0 experiment spend.
- **Sovereign deployability:** documents, retrieval, verification and Apertus inference can remain local.
- **Implementation feasibility:** working CLI, web UI, tests, CI, real model validation.

## Claims not to make

Do not claim:
- that 18/18 means Apertus has 100% general accuracy;
- that hashes prove document authorship or provide immutable non-repudiation;
- that the MVP supports production PDF provenance if that has not been implemented;
- that the local Q4 quantization is an official Hack Apertus-provided quantization;
- that a hosted public demo exists unless one is actually deployed.
