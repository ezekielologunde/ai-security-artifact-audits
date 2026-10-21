# When an MCP benchmark's data and evaluator disagree: a pinned artifact audit

Ezekiel Ologunde

Technical report draft, 21 October 2026. Not peer reviewed. This draft is local and has not been added to the public collection.

## Abstract

Security benchmark results depend on consistent interpretation of data labels and evaluation inputs. We audit seven separate exports of AgentDefense-Bench at revision b5dfdf3c6cf33fb3c0b39865384b9ca833aa4183. On the documented 640-record tier-1 CLI path, the evaluator ignores the Boolean is_benign labels and defaults to an allowed expectation. An unchanged mock detector blocks 39 records: the original evaluator counts these as false positives, whereas explicit label normalization counts them as true positives. All paired adapter decisions are unchanged. A separate README example selects an absent attacks array and consequently iterates over zero available cases. These results identify bounded artifact contract failures; they do not measure production defense efficacy or establish effects on published model scores.

## Questions and scope

RQ1: Does the documented evaluator interpret the named export's declared labels consistently?

RQ2: Does the documented programmatic example actually select the available records?

RQ3: How do confusion counts change when only the label representation is normalized?

The inspected code suggested a directional expectation: labels encoded only as is_benign would fall through to default allowed, while explicit expected fields would retain their interpretation. This expectation was formed after code and data inspection, not preregistered or independently blinded. Natural label validity is outside the experiment.

## Method

We obtained pinned Git objects without checking out or executing attack code and verified selected source/data hashes. A protocol fixed seven export-level frames and a mock-only paired comparison. The harness extracts inspected upstream MockDefense, EvaluationResult, load_dataset and run_evaluation definitions by AST, preserving their bodies. It does not load network-adapter factories. Requests remain inert strings serialized and substring-matched by the mock.

The comparator adds expected_block = not is_benign only where the latter is Boolean; other labels and every request remain unchanged. ASCII-escaped temporary JSON preserves parsed strings while avoiding an upstream Windows default-encoding dependency. The harness checks equal call counts and identical paired decision vectors. Ten input source/data/protocol hashes remain unchanged.

## Results

For tier 1, original TP/FP/TN/FN are 0/39/601/0; normalized counts are 39/0/0/601. The guide explicitly recommends this file with the evaluator, so it is a documented compatibility issue. The README's programmatic attacks selector yields zero records, whereas tests contains 640. Only the selector was evaluated; its HTTP endpoint was not contacted.

Secondary tier-2 counts change from 0/30/27,092/0 to 30/0/0/27,092. Tier-3 counts change from 0/102/5,504/0 to 102/0/250/5,254. Unlike tiers 1 and 2, tier 3 includes 250 benign-labelled records. Across the three tier files, 33,118 attack-labelled records reach default allowed. Exports with explicit expected labels remain unchanged. The separate 250-record benign export supplies no selected request fields, producing empty dictionaries; the 93-record benign baseline is a different request-bearing export.

Do not pool exports: overlap and provenance of counts have not been resolved. The README's advertised corpus total cannot be compared to one convenient frame as if both had an established common denominator. The published checksum for the novel export differs from its pinned bytes; acquisition identities still verify. This supports a checksum-maintenance observation, not an attribution of tampering.

## Interpretation and related work

The result is a pinned artifact audit, not a new classification method. AgentDefense-Bench provides the source artifact [1]. Existing mcp-defense-bench positioning already distinguishes coverage and detection accuracy [2]. MCP-Guard reports AgentDefense external evaluation [3], but we have not established that its evaluation uses this code path; its results are not re-evaluated here. The evaluator is byte-identical between the inspected December 2025 integration commit and April 2026 pinned revision. Our limited issue/history search found no discussion of these particular failures, which cannot establish first discovery.

## Limitations and reproducibility

The mock is an interface demonstration, not a production defense. No attack was executed, and no model or external defense was queried. The experiment uses dataset-declared labels rather than independent maliciousness adjudication. AST-selected execution reproduces relevant definitions but does not reproduce full CLI startup. Schema normalization is a post-inspection baseline, not a proposed novel algorithm. Actual third-party ranking effects require matching predictions, versions and evaluation paths. Request-level configuration_drift records do not provide longitudinal authority ground truth.

The protocol, harness and JSON outputs are local beside this draft. The standalone replay package provides three commands: `python restore_agentdefense.py`, `python audit_agentdefense_entrypoints.py`, and `python verify_agentdefense_replay.py`. In a clean extracted directory, all three completed successfully using CPython 3.12.14 and Git. Restoration verified 14 files totaling 46,306,066 bytes; the replay matched the retained result exactly. Raw third-party corpora are restored from the pinned original repository rather than bundled. The package has been tested locally; this draft and supplement have not yet been added to the public GitHub collection.

## References

[1] Arun Sanna. AgentDefense-Bench. Pinned revision b5dfdf3c6cf33fb3c0b39865384b9ca833aa4183. https://github.com/arunsanna/AgentDefense-Bench

[2] Gowthaman90. mcp-defense-bench, docs/PRIOR-ART.md. Mutable main-branch page inspected 21 October 2026. https://github.com/Gowthaman90/mcp-defense-bench/blob/main/docs/PRIOR-ART.md

[3] Wenpeng Xing et al. MCP-Guard: A Multi-Stage Defense-in-Depth Framework for Securing Model Context Protocol in Agentic AI. Findings of ACL 2026, pages 4877–4889. https://aclanthology.org/2026.findings-acl.240/
