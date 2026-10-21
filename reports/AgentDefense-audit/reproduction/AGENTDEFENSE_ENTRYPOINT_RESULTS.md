# Documented entry-point reproduction

21 October 2026. Pinned revision b5dfdf3c6cf33fb3c0b39865384b9ca833aa4183. Protocol: AGENTDEFENSE_ENTRYPOINT_PROTOCOL.md. Machine-readable results: results/agentdefense_entrypoint_audit.json.

## Primary result

The integration guide explicitly recommends the tier-1 file with scripts/evaluate.py. On all 640 tier-1 cases, the unmodified evaluation function with the unmodified mock pattern matcher records TP=0, FP=39, TN=601, FN=0. Adding expected_block = not is_benign in a temporary parsed copy yields TP=39, FP=0, TN=0, FN=601. Requests and all 640 adapter decisions are identical between runs. This corrects interpretation of the dataset's own labels, not a defense's behavior or independently verified maliciousness.

The README programmatic example selects json.load(...).get('attacks', []), whereas the named file has a tests array. Its selected array has zero rows despite 640 available tests. We evaluated this selection only; its HTTP adapter was not instantiated.

## Secondary probes

| Export | Original TP / FP / TN / FN | Normalized TP / FP / TN / FN | Empty requests |
|---|---|---|---:|
| combined attacks, 319 | 65 / 0 / 0 / 254 | unchanged | 0 |
| novel export, 100 | 17 / 0 / 15 / 68 | unchanged | 0 |
| benign baseline, 93 | 0 / 0 / 93 / 0 | unchanged | 0 |
| tier 2, 27,122 | 0 / 30 / 27,092 / 0 | 30 / 0 / 0 / 27,092 | 0 |
| tier 3, 5,606 | 0 / 102 / 5,504 / 0 | 102 / 0 / 250 / 5,254 | 3 |
| separate benign export, 250 | 0 / 0 / 250 / 0 | unchanged | 250 |

These are separate export-level probes, not a pooled independent sample. The tier-3 file includes 250 benign-labelled records. The three tier files contain 33,118 attack-labelled records, correcting a preliminary prose count that incorrectly treated every tier record as an attack. The original machine-readable qualification output already retained the correct Boolean counts.

## Execution and limitations

Only selected, inspected upstream definitions were executed through AST extraction; imports, factories and network adapters were excluded. MockDefense serializes input and matches strings; no payload was executed. Input lists were serialized as ASCII-escaped JSON for the upstream loader's Windows default encoding; parsed strings and requests remain equal. Ten source/data/protocol SHA-256 values were unchanged. Paired adapter decisions matched in every frame. No model, external endpoint or production defense was evaluated. The first harness attempt failed before any evaluation because a typing namespace expansion duplicated abstractmethod; the harness then restricted typing names and completed. No upstream source was altered.

This demonstrates documented artifact incompatibilities, not published-score corruption: no released defense result logs were linked to these paths. It is not a novel classification or authority method. Keep this as a reproducibility candidate pending source-history and adjacent-work review; the temporal authority research question remains unresolved.
