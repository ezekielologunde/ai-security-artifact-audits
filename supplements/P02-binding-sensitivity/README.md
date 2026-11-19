# Authored evidence-attribution sensitivity replay

Ezekiel Ologunde, 19 November 2026. This standalone experimental package uses Python 3.12 and only the standard library. No general reuse licence has been selected for authored code/results. No third-party model code, weights, natural model cards, review keys, API credentials or reference human annotations are included.

From this folder, use fresh output names:

```
python generate_cases.py --output ../binding-cases-regenerated.json
python run_replay.py --cases ../binding-cases-regenerated.json --output ../binding-sensitivity-receipt.json
```

The first command recreates all 72 authored cases and parses the examples without executing them. The second verifies the dataset/implementation hashes, evaluates two modes and compares all 144 complete outputs to the recorded canonical output hash. It also checks aggregate counts and paired firings, and refuses to overwrite the receipt. No network, model calls, package installation, scanner or VM is needed. Raw experiment snapshots and the retained implementation are present for inspection.

Read PROTOCOL.md and RESULTS.md first. The full-factorial authored data show an attribution/coverage tradeoff: default mode yields 18 reference-positive and 12 reference-negative firings; strict mode yields 6 and 0 respectively, missing 12 reference-positive routes. This is not natural detection accuracy, actual model-loading behavior, independent validation, or proof of a new algorithm. The selector annotation cost is not measured. The existing papers and public collection version 14 were not revised for this experiment.
