# Released identity-key overlap

17 November 2026. Descriptive extension under `KEY_OVERLAP_PROTOCOL_20261117.md`; no new agent runs, correctness labels or published-score reconstruction.

## Current acquisition boundary

The primary GitHub HEAD remains `a6aaf30ccdb15d774ac8bad136e52491db3e2a4a`, root tree `7950d83ca5c47efda4e101c94b3095504f8ae2a5`. The untruncated tree has 18 blobs and the GitHub releases endpoint returns an empty list. No raw correctness records were acquired. The primary arXiv record still lists v1. These checks concern those sources only, not every possible location of author data; no author was contacted.

## Observed overlap

All twelve original input hashes verified before/after analysis. Each model/task/perturbation key is unique in its table population. After omitting model identity, both populations have 218 distinct task/perturbation keys.

| Population | Rows | Keys shared by 3 models | Keys shared by 2 models | Rows whose reduced key is shared |
|---|---:|---:|---:|---:|
| Trace | 614 | 178 | 40 | 614 |
| Token | 624 | 188 | 30 | 624 |

These are observed identity memberships, not correctness judgments. Complete key membership is retained in `results/released_key_overlap_20261117.json`. Reduced keys cannot uniquely identify a model-labelled released row.

## Conditional join cardinality

Assume, only for this diagnostic, one outcome record for every complete identity in each population. A join on reduced keys would yield 1,762 rows for traces and 1,812 for tokens, versus 614 and 624 under complete-key matching. Grouped squared multiplicities and an independent explicit nested count agree. No correctness values were created or used.

These cardinalities are conditional constructions, not observed author correctness-merge outputs. Actual outcome coverage, duplicate structure and values remain unavailable. Equal labels could preserve some rates despite row expansion; different labels could change rates. Neither case is selected as the truth here. Do not report an error magnitude, affected ranking or model-correctness estimate from these counts.

## Decision

The earlier controlled counterexample now has a measured identity-overlap precondition in the released tables. This strengthens the source-contract scope of the technical note; it does not turn an ordinary complete-key join into a novel algorithm or establish that the paper's correctness findings were wrong. P11/P19 remain one shared artifact audit, with the original poisoning-lineage/reconstruction questions unresolved.

Script: `audit_key_overlap.py`. The original per-model table audit, controlled join results, manuscript and public release bytes were not modified by this extension. A future note revision must identify the new descriptive analysis separately from the earlier conformance result.
