# Validated reference experiment

This package contains actual measured storage-contract results, not LLM behavior or vendor-framework evaluations. The full grid consists of 140 episodes, two backends, six configurations and nine managed events, plus two boundary events for the full overlay: 15,680 trials. The two measured input files are LongMemEval oracle and LoCoMo10. Dataset revisions, licenses and SHA-256 hashes are in the companion directories and download manifest.

## Reproduce without overwriting reference results

Use Python 3.12 and NumPy (`python -m pip install numpy`). Run these commands from the package root (the directory containing `experiment/` and `datasets/`):

```
python experiment/download_data.py
python -m unittest discover -s experiment -p test_overlay.py -v
python experiment/run_experiment.py --out experiment/reproduction --scratch work/reproduction-runtime
python experiment/analyze.py --results experiment/reproduction
```

The default complete run takes substantial time. A quick smoke run can use `--limit 1`; the full analyzer intentionally rejects an incomplete grid. The recorded run used four independent processes with `--shards 4 --shard-index 0` through `3`, each writing to its own results/shard-N directory and scratch directory. Do not let two processes share a scratch directory. Each run records the source files present at its launch, so a fresh run has a different code-manifest inventory from the original run after the additional analysis/documentation helpers were added. Original source hashes for overlay.py, run_experiment.py, test_overlay.py are preserved in the run manifests; the analyzer was subsequently extended to accept a reproduction destination. The overlay, runner and unit-test sources remain unchanged.

## Interpret the evidence

- `results/trials.jsonl`: all measured outcomes, including failures and boundary controls.
- `results/summary.json`, `cell-results.csv`, `arm-results.csv`: derived counts and timings.
- `results/validation.json`: completeness, uniqueness, acquisition, backend consistency and negative-control checks.
- `results/run-manifests.json`: recorded environment, protocol and input/code hashes.
- `results/unit-tests.txt`: all 18 unit tests passed.
- `protocol.json`: locally frozen before measurement; not an externally preregistered protocol.

The full overlay has zero recoveries in 2,520 managed trials. It fails all 560 authority-rollback/adapter-bypass boundary trials. Replay fixtures retain the marker in every trial. Hash-based lexical vectors are not learned embeddings. Summaries, caches and checkpoints are deterministic copied records. No LLM was called, no semantic behavioral forgetting was measured, and no physical-media sanitization guarantee is established. Latencies come from a shared-host batch execution and are descriptive.

LongMemEval data carries the upstream MIT declaration. LoCoMo carries CC BY-NC 4.0: preserve attribution and its noncommercial restriction. Consult the included upstream license/card files before reuse. The supplied overlay is a research prototype; package inclusion does not change upstream data terms.

