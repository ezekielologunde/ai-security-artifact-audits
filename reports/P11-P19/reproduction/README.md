# Identity-preserving contamination-table audit

This project pins a public author artifact, independently checks its table coverage, reproduces available aggregates and demonstrates a controlled failure of an optional cross-model correctness join. Read `REVIEW.md` for scope and limitations.

Order: `acquire_trace_artifact.py`, `download_trace_tables.py`, `audit_tables.py`, then `test_join_counterexample.py`. Acquisition uses Python standard-library downloads; the controlled comparison additionally needs the versions in `requirements.txt`. No paid API, live agent, external endpoint or model training is used. The experiment does not estimate the error in unreleased author records.

Results are in `results/`. `AUDIT_PROTOCOL.json` and `JOIN_PROTOCOL.json` distinguish prior exploratory inspection from local controlled checks. Source code and raw author tables remain local acquisition material; the authored review package excludes them. `strict_join.py` requires explicit model/task/perturbation identity, rejects duplicates, and retains missing correctness as unknown. For other datasets, define run identity before applying it.

The ACM-style preliminary technical note is saved in `paper/main.tex`; Overleaf source and the compiled PDF are under `output/`. Compilation, visual review and external scientific review are separate steps. No public submission is recorded.
