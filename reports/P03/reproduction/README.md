# P03 — Synthetic Shadow AI dataset audit

Author: Ezekiel Ologunde. Local technical-note draft, 18 October 2026. Not submitted, accepted or published.

The original broad asset-inventory question was narrowed after reviewing existing discovery tools and inspecting a public synthetic source. The completed bounded experiment concerns detector-view label isolation and repeatability. The policy/authorization counterfactual experiment in the initial design was not executed or claimed as a result.

## Actual finding

Pinned source: `Deepa-15/shadowai-enterprise-dataset`, revision `b1d2966939edde18edc08a08f52145fc1378d567`. Two fresh unchanged generator processes each produce 191,370 synthetic sessions, 43 injected violations and ten output files. The detector export retains `session_type=shadow_ai_violation` for exactly the positive rows. Its original validator accepts the view. A direct field-equality shortcut has 43 TP, 0 FP and 0 FN. This is a leakage finding, not a detector result.

The always-negative control has 99.9775% accuracy and zero recall. Predicting a violation from the five configured AI domains yields 43 TP and 79,510 FP. Service use is not the injected violation outcome, nor independently verified organizational authorization.

Generated raw hashes differ across fresh processes because UUIDs differ; canonical detector and labeled rows match after removing session IDs and row order. The two runs are repeated executions of one synthetic design, not independent enterprise samples.

`view_guard.py` removes the confirmed alias and separates join identities from model features. Five boundary checks pass. Projection of all 191,370 rows in both runs leaves original files byte-identical. The guard is schema hygiene, not a novel detector or exhaustive leakage proof.

## Reproduce

Use Python 3.12 in an isolated environment and install `requirements.txt` (the measured run used NumPy 2.3.5, pandas 3.0.1 and Faker 37.0.0). The manuscript/package script additionally uses PyMuPDF 1.28.2 for rendering; compilation used the existing project-local Tectonic executable from P02.

```powershell
python scripts/acquire_sources.py
python scripts/reproduce_generator.py
python scripts/audit_generated_views.py
python scripts/verify_view_guard.py
python scripts/write_paper.py
```

Acquisition caches immutable source receipts. `data/source_manifest.json` records repositories/revisions. On a fresh reproduction, preserve its pinned revision rather than resolving a newer upstream head. Full runs write only into fresh `work/generator-run-N/` copies; a partial run is preserved for inspection. The generated raw files stay local.

## Evidence and publication boundary

The source review identified the mechanism before the local audit protocol was frozen. This is exploratory confirmation, not blinded independent testing or preregistration. No maintainer adjudication or independent human review is claimed. No published trained-detector performance was reproduced or invalidated. General label-leakage hazards and feature allow-lists are established prior art; the contribution is the concrete revision-specific audit and its reproducible evidence. Publication suitability and priority remain unestablished.

The source repository did not expose a recognized root license in the inspected inventory. The authored review ZIP therefore excludes third-party source and generated raw exports; it includes source URLs/hashes, our scripts, aggregate results, feature contract and manuscript. Public availability alone does not grant a blanket redistribution license. No external report or message has been sent.

The app's native LaTeX compiler still reports an environment-directory error. The actual ACM-layout PDF is exported with portable Tectonic and separately rendered/checked. No ACM venue, DOI or acceptance is implied.
