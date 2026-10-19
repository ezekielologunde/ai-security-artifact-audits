# Memory integrity and cross-agent contamination: bounded artifact audit

18 October 2026. This directory contains primary-method review plus an actual local table reanalysis and controlled join counterexample. It does not contain a new memory-defense or agent-contamination trial.

## Closest work and limits

- [MemLineage](https://arxiv.org/html/2605.14421) already combines memory integrity, derivation lineage, persistent trust labels and sensitive-action enforcement. Its threat model, evaluation distinctions and limitations were inspected. It separates deterministic harnesses from live-model evidence and discusses trusted source-label integration and uninformative no-defense controls. No public complete artifact URL was verified from the inspected HTML links; references to shipped files are not evidence that we acquired them.
- [MemSecBench](https://arxiv.org/html/2607.27080) already separates memory write/persistence, recall, adoption, external effects, repair and benign preservation. Its lifecycle/adjudication and runtime appendix were inspected. Backend adapters and retrieval settings are part of the evaluated conditions. Our P12 storage/deletion study must be positioned against this prior lifecycle work rather than claiming the first cross-layer memory-security evaluation.
- [Mazhar, Suri and Galhotra](https://arxiv.org/html/2604.27586), *Trace-Level Analysis of Information Contamination in Multi-Agent Systems*, already measures divergence, silent corruption, recovery and cost. Its setup, outcomes, interpretation and generalization limits were inspected. The author artifact is pinned at `a6aaf30ccdb15d774ac8bad136e52491db3e2a4a`.

## Acquired and measured

Nine CSVs, author statistic code and retained reference outputs were acquired, with 12 source hashes verified. Independent stdlib analysis counts 614 trace rows over 32 tasks, versus 624 token rows. All trace keys have token matches; 9 GPT and 1 Qwen token keys lack trace matches. Model/task/perturbation keys are unique within each table. The source's 94/614 silent-label share rounds to 15.3%; its 247/614 reroute/extended share is 40.228% (40.2% directly rounded). The author script instead adds separately rounded components and reports 40.3%. The underlying counts agree; this small rounding distinction does not establish a qualitative contradiction. These reproduce released labels, not independently validated correctness.

The original statistics script was run locally using pandas 3.0.1 and NumPy 2.3.5, producing `results/author_stats_combined.json`; no agents or model APIs ran. Correctness-specific rates are unavailable without the raw summary records, which were not present in the inspected author tree. The retained reference log says it loaded additional correctness records. We do not impute them from answer changes or manifestation labels.

## Controlled join finding

The author's optional correctness loader emits task/perturbation fields without model identity, and the downstream correctness merge joins on those two fields. A frozen controlled example supplies two models with the same task/perturbation: the high-cost model is correct and the low-cost model is incorrect. The original merge expands each observation into two rows and reports 50% high-cost correctness and 50% low-cost incorrectness; the identity-preserving join reports the intended 100% and 100%, with one labeled observation per stratum. The equal-correctness control preserves rates but still exposes duplicated counts.

Six checks pass: counterexample, row-order invariance, equal-label control, missing identity rejection, unknown outcome preservation and duplicate-key rejection. `strict_join.py` is an explicit ordinary data-join contract, not a novel algorithm. A genuine repeated-trial corpus would need an additional run identity; the present complete key is scoped to this artifact's unique rows.

The finding identifies a source-code failure condition. It **does not** establish the incidence or magnitude of error in the published correctness rates, because the actual raw correctness records are unavailable. It does not contradict the independently reproduced count/manifestation results. External adjudication and maintainer assessment have not occurred.

## Decision

Preserve this as a revision-specific reproducibility technical note. Broad memory-integrity/contamination novelty is not established. Standalone venue suitability remains unestablished; a broader independent benchmark audit or author-provided raw correctness data would strengthen the evidence. Do not convert this artifact issue into a claim that a new memory-security gap has been solved. P11 and P19 share this audit and are not separate completed defense papers.
