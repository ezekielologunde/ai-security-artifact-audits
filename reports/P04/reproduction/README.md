# HelpBench scoring-helper audit

Ezekiel Ologunde. Preliminary technical report prepared 20 October 2026 from source/data acquired 19 October. Not peer reviewed. The original P04 question about end-user security outcomes remains unresolved; this note audits a benchmark's numerical scoring helpers. P05 patch-agreement and SecRespond materials in the local research directory are separate work and excluded from this report's package.

All 450 released expert overall scores reproduce. Two negative-subscale helpers return None instead of the defined inverted endpoint 1 for 19 of 439 applicable factual records and 39 of 450 delivery records. Nine original tests and nine independent checks pass. These findings do not establish errors in the original paper's headline scores or full model rankings.

Start with `HELPBENCH_RESEARCH_DECISION.md`, `HELPBENCH_RESULTS.md` and `paper/main.tex`. Protocol, failed ID-join attempt and amendments distinguish source inspection, primary score outcomes and post-hoc conditional aggregation. The first script version is retained under `work/frozen/` as history, not a runnable current entry point.

## Reproduce

Use Python 3.12 and the pinned requirements. Acquisition retrieves ten compact author-linked files under their original Apache-2.0 notices; it does not retrieve Reddit posts or run a model. The anonymous service exposes no full commit and may expire, so compare every SHA-256 with `data/helpbench_manifest.json`. A changed file is a different artifact, not an equivalent rerun.

```powershell
python -m pip install -r requirements-helpbench.txt
python download_helpbench.py
python -m pytest -q -p no:cacheprovider --junitxml=results/helpbench_upstream_junit.xml data/helpbench/files/tests/test_scoring.py
python audit_helpbench_scorer.py
python summarize_helpbench_effect.py
python verify_helpbench_scorer.py
```

`scorer_overlay.py` declares exact selected-rubric coverage and explicit scored/invalid/not-applicable states. A strict input contract is not a new judging algorithm or proof that criterion decisions are true. The minimal zero/None comparator is separate from the coverage adapter.

The authored package contains code, protocols, numeric per-endpoint outcomes and source receipts. Raw questions/model-response texts, upstream code, downloaded paper copies, other project data and generated ACM class files are excluded. The upstream licence notice is preserved for attribution; it does not licence the authored report or adapter. No blanket reuse licence is selected for authored material.

The Overleaf ZIP uses the standard installed ACM `acmart` class. The saved PDF was compiled with portable Tectonic and both rendered pages inspected; the desktop editor also reported successful compilation on this run. ACM layout does not imply ACM publication or endorsement. Independent external review, author contact and peer review have not occurred.
