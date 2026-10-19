# Controlled RAG source-revocation audit

Read `REVIEW.md` for primary work, measured results and limitations. This is a local, model-free implementation audit of a pinned author artifact. It is not a production exploitation or physical-erasure study.

Reproduction order:

1. Create an isolated Python environment; install `requirements.txt`.
2. Run `acquire.py` and `download_sample.py` to pin/read the author artifact and acquire its inert sample.
3. Run `run_upstream_tests.py`. Our recorded environment has 32 passes and one optional pyarrow skip.
4. Run `collision_experiment.py` and `verify_collision.py` for the original, immutable-ID and explicitly post-hoc upsert cases.

`COLLISION_PROTOCOL.json` precedes scoring; source inspection was exploratory. `UPSERT_AMENDMENT.json` records the post-hoc comparator. `results/` contains every case outcome and verification reports. No original source is edited. The overlay assumes single-threaded trusted admission and defines no cross-source ownership policy; updated passage identity must be handled explicitly by the caller.

Paper source is `paper/main.tex`; its compiled preliminary ACM-style note, Overleaf ZIP and authored review package are under `output/`. Raw source/code/sample acquisition stays separate from the authored review package. Independent review and public submission remain pending.
