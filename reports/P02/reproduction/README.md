# Controlled provenance-consistency experiment

Ezekiel Ologunde. Authored controlled-only reproduction supplement, 20 October 2026. No blanket reuse licence selected.

Use Python 3.12, install `requirements.txt`, run `python run_controlled.py`, then `python -m pytest -q`. The wrapper runs the original fixture generation, case builder and five-mode evaluation with isolated output roots. It compares all predictions and error cases exactly, excluding only elapsed runtime from the summary comparison. It refuses to overwrite a previous controlled run. Use a fresh copied package to repeat.

The full original runner is retained unchanged as source evidence, but its default main command requires the separate natural corpus, deliberately excluded here. The wrapper never invokes its acquisition/observational routines. The builder's natural-sources parameter is unused, checked during packaging.

This supplement reproduces the 36 developer-authored cases and seven original tests, not the 59-repository natural study, external comparators or independent annotation. It excludes model cards, natural metadata snapshots, downloaded weights, reading copies, review sheets and keys. References preserve the original controlled outcomes, including all three grammar misses. A static pickle fixture contains a suspicious global opcode; it is never unpickled or executed.

Results demonstrate implementation conformance, not natural precision/recall, confirmed malware, authenticated training lineage or field-wide novelty. PickleScan retains its own upstream terms; it is acquired as a pinned dependency rather than bundled.
