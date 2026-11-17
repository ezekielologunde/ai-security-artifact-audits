# P02 loader-context engineering supplement

Collection version 14 adds an optional Boolean `loading_path.trust_remote_code` selection and its controlled diagnostic. Explicit `false` prevents README-wide enabled-code text from establishing selected-path custom-code use; invalid flag types are rejected. The raw document match and selected flag remain separately visible in evidence. False is not proof of compatibility or safety and does not hide pickle exposure. A true or missing flag still leaves README example/target association unverified. This is not complete call binding. See `SELECTED_TRUST_FLAG_PROTOCOL.md`.

Ezekiel Ologunde, 17 November 2026. A separate implementation extension, not a revision of the six-page preliminary study. Independent review is pending. No general reuse licence has been selected for authored code or results; upstream model repositories retain their own terms.

The overlay adds lexical loader mentions, candidate conditions, exact source locations, and code/blockquote flags. Mentions within four README lines of an extracted claim are referenced by that claim. Other mentions remain document-level. `scope_binding: unverified` explicitly leaves the actual loading path unresolved. Security verdicts are unchanged. These fields do not prove compatibility, provenance, safe loading, comprehensive language understanding, or novelty.

Use Python 3.12 and run from this folder:

```
python run_replay.py --output ../context-regression-run
python -m pip install -r requirements-tests.txt
python -m pytest -q
```

The first command uses only the standard library and compares all previous output fields for 36 developer-authored cases under five modes (180 comparisons), excluding added context and selected-flag evidence fields. It also reproduces `selected_flag_case.json`: the earlier implementation emits a contradiction, while the updated implementation abstains. The 18 test instances comprise seven original tests, five context tests and six selected-flag cases. `core_before.py` is the preserved pre-extension implementation. Tests do not execute artifact/model code or deserialize weights.

Optional public-data reacquisition:

```
python run_replay.py --acquire --output ../context-discovery-run
```

This requires curl and network access. It downloads only seven README/config files at four pinned repository revisions, checking size and SHA-256. `candidates.json` records source URLs and metadata-listed filenames, not verified contents of every listed artifact. No model weights or repository Python files are downloaded/executed. Failures remain failures; there is no gate bypass. Every output directory must be new. Downloaded material stays outside the supplement and is subject to upstream terms; do not commit acquired files automatically.

`expected_observations.json` contains the implementation's exploratory outputs, not truth labels. Three targeted cards match the explicit-claim grammar and receive unverifiable dispositions; one historical search lead has no matching positive phrase in its pinned README. All four loading exposures remain indeterminate. Do not interpret regression against these outputs as precision, recall, prevalence, human validation or improved scanner effectiveness. The separate original 59-case cohort, blinded review and controlled-only publication package are unchanged. No raw model cards, natural metadata payloads, review keys, credentials or downloaded paper copies are bundled here.

After optional acquisition, the CLI can analyze one saved snapshot in the usual way: `python -m model_consistency analyze --snapshot PATH --output PATH`. The reacquisition runner itself assembles snapshots in memory and saves augmented reports; its receipts record the exact compact-file hashes.
