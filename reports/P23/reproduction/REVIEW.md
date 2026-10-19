# Lifecycle disposal and RAG source revocation

18 October 2026. P09 physical disposal and P23 logical source revocation remain distinct. This directory contains a controlled implementation audit of P23's closest prior artifact, not a physical-erasure experiment.

## Prior work and scope

- [RAGtrap](https://github.com/CristhianKapelinski/sbseg2026-ragtrap), pinned `c11da0ba9e6071773b11113c47a69bf80fcb916a`, MIT. The official SBSeg artifact page links this repository. README, implementation documentation, gate, datastore, traceback, revocation and relevant tests were inspected. Signed chunk provenance, indexed attribution, source revocation, future-ingestion refusal and known-source recovery already exist. The datastore is explicitly in-memory; the authors distinguish exact-hash limitations and algorithm latency from persistent vector-database remediation.
- [ForgetEval/Lethe v2](https://arxiv.org/html/2606.15903v2) already compares control-plane placement and heterogeneous forgetting primitives. Its admission/scoring and discussion were inspected, including substring-score artifacts, unavailable primitive denominators and limited architecture-sample claims. Its results are not rerun here.
- [EPITAPH](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7341378) and [institutional record](https://keele-repository.worktribe.com/output/1783633/epitaph-verifiable-decommissioning-of-stateful-agentic-systems) establish a close decommissioning protocol lead. The institutional page still returned HTTP 403 on direct retrieval. Full methods were not obtained in this session; no absence claim or full comparison is asserted.
- Existing P01 offboarding and P12 cross-layer memory-deletion manuscripts already contain relevant restoration/authority experiments. Their measurements are not independent new results of this audit. P09/P23 should not duplicate them as new papers.

## New controlled finding

The RAGtrap datastore's `put` accepts an existing chunk ID, replaces the current record/chunk, and appends new index memberships without removing old memberships. The gate's ordinary character splitter derives IDs from `document_id`; repeated ingestion with that same document ID reaches the same behavior without a forged signature or inconsistent record.

We froze an eight-case matrix after source inspection but before scoring: same/different ID, principal and text. All second ingestions are accepted by the original. Two cross-source ID-reuse cases have stale principal memberships and delete the current other-source record when the original source is revoked. Two changed-text ID-reuse cases retain an old hash bucket that resolves to a current record with a different content hash. All live record signatures verify. This is index-to-record inconsistency, not a cryptographic break or a poisoning-detection result.

An immutable-ID overlay rejects all four repeated-ID cases and accepts all four fresh-ID cases, with no observed inconsistency or cross-source false purge. Updated passages need new versioned IDs under that contract. A **post-hoc** alternative validates admission, removes the old memberships, and performs a single-threaded upsert; it accepts all eight cases and has no observed failures on the same matrix. The post-hoc comparator is separately recorded in `UPSERT_AMENDMENT.json`; it is not held-out efficacy evidence. Neither overlay provides concurrent transaction guarantees, ownership-transfer authorization, persistence or migration of already-corrupt stores.

Eight verification checks pass, including an end-to-end character-splitter/gate collision, valid-signature counterexample, versioned-ID control, rejection without mutation, source-denial preservation, record binding, matrix availability and post-hoc upsert consistency.

## Reproduction and boundaries

Thirty-two upstream source/document files were acquired and hashed. The author's frozen 337,536-byte BEIR sample was acquired and its published SHA-256 checked by the source unit test. Original offline suite: **32 passed, 1 skipped**; the skipped false-purge contrast requires pyarrow, absent here. We did not claim reproduction of that optional contrast or of full author experiments. Local runtime: Python 3.12.14, cryptography 50.0.2, pytest 8.4.2; this is not the author's full uv-locked runtime. No model calls occurred.

This revision-specific counterexample identifies an accepted input condition that requires an identity/update contract. It does not estimate natural collision incidence, attacker access to the trusted ingestion gate, production exploitability or errors in the paper's reported unique-ID experiments. Standard index maintenance and admission validation are not new algorithms. Standalone novelty and publication suitability remain unestablished; independent assessment is still needed. No maintainer message, public vulnerability claim or paper submission has been sent.

P09 remains a separate review question: logical suppression, key revocation, physical-media erasure, disposal of remote copies and parametric unlearning demand different evidence. The P23 result does not solve those endpoints.
