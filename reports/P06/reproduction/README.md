# Public semantic task–tool matching audit

Ezekiel Ologunde, 18 October 2026. Preliminary reproducible benchmark note; not submitted or published. This is a bounded P06 experiment. The adjacent P13/P14/P15 questions are reviewed for overlap but are not completed by these measurements.

## Start here

- `DESIGN.md`: candidate question, hypotheses and prior-art boundary.
- `PROTOCOL.json`: first frozen implementation; its catalog load failed before scoring.
- `PROTOCOL_V2.json`: documented manifest-enumeration repair, frozen before any scored outcomes.
- `RESULTS.md`: full denominators, transfer failures, scope and novelty limits.
- `results/lexical-v2/`: original primary predictions/summary/independent arithmetic verification.
- `results/namespace_sensitivity.json`: explicitly exploratory post-hoc canonicalization; primary results are retained.
- `paper/main.tex`: ACM-layout working note, not an accepted publication.

The existing ASTRA method already performs semantic authorization matching; TF-IDF and validation-based thresholds are established. This experiment adds an auditable low-resource baseline and a limited transfer/coverage audit. Standalone publication novelty is not established by the measurements alone. False-appropriate rates are disagreements with synthetic/processed benchmark labels, not actual access-token failures or enterprise exploit probabilities.

## Offline reproduction after acquisition

Core scoring and verification need only Python 3.12 standard libraries. The two text representations use catalog-only IDF and validation-only thresholds; no model calls or test-label calibration occurs.

```powershell
python lexical_baseline.py
python verify_analysis.py
python namespace_sensitivity.py
python write_note.py
```

Do not rerun `freeze_protocol.py` or `amend_protocol.py` over an existing freeze. Their recorded files are retained. The original failed code is preserved at `work/frozen/lexical_baseline_v1.py`; the authored review bundle includes that file even though general scratch files are excluded.

Fresh source acquisition uses `acquire_artifacts.py` then `download_data.py`; the source manifest in `author_artifacts/data/` pins repository revisions. Full primary-paper acquisition uses `acquire.py`, whose saved HTML version strings are recorded separately. The selected JSON artifact count is 139 (9,877,472 bytes). The raw-content route fails on two Unicode names; the downloader recovers exact bytes through Git blob APIs and verifies object identity.

The authored bundle contains code, source manifests, aggregate/per-case predictions and the upstream ASTRA license notice, but omits the 10 MB benchmark data and third-party paper reading copies. Reacquisition preserves provenance. Original ASTRA and TOUCAN attributions/terms remain distinct; no blanket project/data license is assigned here. No public repository or artifact release has yet been created for this note.

The manuscript is compiled with the existing portable Tectonic executable from P02. Native editor compilation remains unavailable due to a platform-directory error. PDF rendering additionally uses PyMuPDF 1.28.2; no TeX installation is needed for the app's editor.
