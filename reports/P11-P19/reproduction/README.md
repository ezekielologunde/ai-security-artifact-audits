# Identity-preserving contamination-table audit

This project pins a public author artifact, independently checks its table coverage, reproduces available aggregates and demonstrates a controlled failure of an optional cross-model correctness join. Read `REVIEW.md` for scope and limitations.

Order: `acquire_trace_artifact.py`, `download_trace_tables.py`, `audit_tables.py`, then `test_join_counterexample.py`. Acquisition uses Python standard-library downloads; the controlled comparison additionally needs the versions in `requirements.txt`. No paid API, live agent, external endpoint or model training is used. The experiment does not estimate the error in unreleased author records.

Results are in `results/`. `AUDIT_PROTOCOL.json` and `JOIN_PROTOCOL.json` distinguish prior exploratory inspection from local controlled checks. Source code and raw author tables remain local acquisition material; the authored review package excludes them. `strict_join.py` requires explicit model/task/perturbation identity, rejects duplicates, and retains missing correctness as unknown. For other datasets, define run identity before applying it.

The ACM-style preliminary technical note is saved in `paper/main.tex`; Overleaf source and the compiled PDF are under `output/`. An earlier version is publicly available in the GitHub technical-report collection; no external preprint-server or peer-reviewed acceptance is claimed. The 17 November revision adds the separate released-key analysis and must pass its own packaging/replay checks before claiming that revised version public.

After pinned acquisition, reproduce the descriptive extension without model or pandas dependencies:

```
python audit_key_overlap.py --tables-only --output results/replayed_key_overlap.json
```

The output path must be new. Compare its `populations` with `results/released_key_overlap_20261117.json`; release-metadata checks are deliberately not repeated in tables-only mode. All twelve input hashes must match. Conditional join cardinalities assume one outcome per complete identity; no correctness labels are supplied or inferred. See `KEY_OVERLAP_PROTOCOL_20261117.md` and `RELEASED_KEY_OVERLAP_RESULTS_20261117.md`.
