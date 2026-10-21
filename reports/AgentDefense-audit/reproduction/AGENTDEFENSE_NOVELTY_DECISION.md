# Bounded novelty and publication decision

21 October 2026. Previous turn made progress: a frozen post-inspection protocol, executable paired evaluation, seven frame-specific results, and corrected label counts were saved. This review adds source-history evidence and a related-work boundary.

## Source-history check

GitHub's current default-branch path history returned two commits for scripts/evaluate.py and one for docs/INTEGRATION.md (first page, limit 100). The latest returned evaluator commit is f196a8e05501fca455a9598e0d0f4160c44b9f92, dated 3 December 2025. Its fetched evaluator is byte-identical to the pinned April 2026 evaluator: Git blob a8903d2ff1b5e9abf9c68252310a4311c0be16c4, SHA-256 1156ccf1a44088b53e9bd50e207c3b80d31f5bfdb82f312fd55982d7fcfa10eb. This verifies persistence across those two versions, not every historical branch or fork.

Repository issue search returned one issue, a complementary-benchmark cross-reference. Its returned body does not discuss the observed label projection or README selector. Comments and all external discussion were not exhaustively searched. No maintainer was contacted.

Receipts: results/agentdefense_history_review.json and results/agentdefense_evaluator_history_comparison.json. The exact historical connector transport is retained locally.

## Adjacent primary sources

- AgentDefense-Bench's own integration guide recommends the affected tier-1 CLI path. The source artifact, rather than a general field-wide gap, is the object of this audit: https://github.com/arunsanna/AgentDefense-Bench/tree/b5dfdf3c6cf33fb3c0b39865384b9ca833aa4183
- mcp-defense-bench's PRIOR-ART.md already distinguishes vector coverage from AgentDefense-Bench detection accuracy and discusses repackaging general safety prompts as MCP requests. Its general realism/coverage criticism is therefore prior positioning, not our discovery. Read on 21 October from a mutable main-branch page; not pinned or independently validated: https://github.com/Gowthaman90/mcp-defense-bench/blob/main/docs/PRIOR-ART.md
- MCP-Guard (Xing et al., Findings of ACL 2026) uses layered prompt detection and reports external AgentDefense results in Section 5.2/Table 4b. The accessible methods/results sections do not establish use of this pinned evaluator or the tier-1 path. Our mock-only audit cannot invalidate its scores. Primary paper: https://aclanthology.org/2026.findings-acl.240.pdf

The targeted web searches were `"AgentDefense-Bench" "is_benign"` and `"AgentDefense-Bench" evaluation benchmark labels`. They surfaced source/related artifacts, not a confirmed earlier reproduction of this exact mismatch. Search absence does not prove novelty. This is not an exhaustive systematic review.

## Decision

Prepare one artifact-specific reproducibility draft. The measured increment is the pinned demonstration that a documented evaluation path changes confusion-matrix semantics, with constant adapter decisions, and that a separate documented selector yields no evaluation rows. Label normalization and schema checks are established engineering techniques; claim no new defense, algorithm, first repair, complete audit, or field-wide prevalence.

Do not count this as solving P13/P14/P15/P17. Their temporal authority question requires state and event ground truth unavailable in these request-level fixtures. Keep the audit shared rather than generating four papers. A public note may be appropriate after self-contained acquisition/replay packaging and independent scrutiny of the paired-label interpretation. The raw multi-source corpus must not be redistributed under a blanket Apache claim; preserve upstream source-specific terms and restore pinned bytes from origin instead.
