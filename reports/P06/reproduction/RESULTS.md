# First lexical baseline and transfer experiment

Measured 18 October 2026. Primary frozen version: `lexical-v2`; original pre-scoring input-enumeration failure and source freeze are retained separately. No test outcomes were available when that repair was frozen. This is local reproducibility freezing, not preregistration or independent validation.

## What ran

- 139 revision-pinned JSON artifacts, 9,877,472 bytes, from ASTRA repository revision `ee05b9b6e6c1c91688db45b187da68f6b2ecb8e7`; all SHA-256 verified.
- 1,592 catalog tool definitions from the ASTRA/processed-TOUCAN catalogs.
- 3,477 ASTRA validation requests for threshold selection; 2,824 ASTRA held-out test requests and 6,333 processed-TOUCAN test requests for evaluation.
- Two established lexical representations: tool names alone, or names plus descriptions. Public catalogs supply IDF, including test-server descriptions; no test task/label is used to fit representations or select thresholds.
- Request score is the minimum cosine over its requested tools; a single validation-calibrated threshold per representation is applied unchanged to all test complexities/sources. The grid maximizes macro-F1, with a higher threshold breaking exact ties. Names select 0.03; names+descriptions select 0.04.

## Primary results

| Test source / tools | Names macro-F1 | Names+descriptions macro-F1 | Description-inclusive false-appropriate rate | Description-inclusive recall | Indeterminate |
|---|---:|---:|---:|---:|---:|
| ASTRA / 1 | 0.675 | 0.770 | 95/473 = 20.1% | 351/474 = 74.1% | 0 |
| ASTRA / 2 | 0.633 | 0.761 | 55/465 = 11.8% | 301/465 = 64.7% | 0 |
| ASTRA / 3 | 0.502 | 0.621 | 35/473 = 7.4% | 177/474 = 37.3% | 0 |
| TOUCAN / 1 | 0.633 | 0.661 | 617/1055 = 58.5% | 1009/1056 = 95.5% | 0 |
| TOUCAN / 2 | 0.731 | 0.698 | 480/1055 = 45.5% | 908/1048 = 86.6% | 8 |
| TOUCAN / 3 | 0.717 | 0.721 | 424/1055 = 40.2% | 901/1056 = 85.3% | 0 |

The TOUCAN/two-tool primary denominator for recall excludes eight indeterminate positive requests. All eight have tool identifiers prefixed with `Server::` that the initial exact lookup does not canonicalize. They remain in the raw request count and coverage report. The secondary post-hoc namespace sensitivity explicitly strips only a prefix matching the separately supplied server. It resolves all eight cases, yields full coverage and leaves false-positive counts unchanged; names+descriptions then has 916 TP and 140 FN on that split, macro-F1 0.6984. Primary results are not overwritten. This is an integration-format sensitivity, not a newly discovered semantic-model error or claimed source-label defect.

H1 is supported on the declared ASTRA test slices for macro-F1, but the descriptions also increase false-appropriate predictions. The names-only false-appropriate rates on ASTRA are 9.9%, 3.0%, 0.6%; on TOUCAN they are 38.0%, 21.3%, 13.2%. Descriptions do not universally improve macro-F1 on transfer: the TOUCAN two-tool slice performs better with names alone. H2's qualitative calibration-transfer concern is supported descriptively in this experiment; no population or statistical-significance claim is made.

## Validation and scope

Five boundary checks pass. An independently implemented confusion-count loop reproduces all saved TP/FP/FN/TN/indeterminate counts. Original source file SHA-256 verification passes for all 139 selected JSONs. The feature scorer accepts only the visible `input` object; source labels and expected-tool metadata are not feature inputs. The original code/protocol and failed pre-scoring run are preserved. Runtime is a descriptive single local run, not a benchmarked performance comparison.

These rates are disagreements with the published synthetic/processed semantic-match labels. They are not unauthorized token issuance, exploit success, resource-level least privilege or real enterprise incident probabilities. The original authors' generative matchers were not rerun, so no SOTA, speed/cost superiority or published-result replication is claimed. Repeated same-task positive/negative variants are not independent samples. No known-neural-model cost is inferred from our runtime.

## Contribution decision

The measured contribution is an auditable, no-generative-call baseline and a source-transfer/format-coverage audit on an existing benchmark. TF-IDF, threshold calibration and semantic authorization matching are established. Its standalone novelty/venue suitability remain unestablished; the strongest output at this stage is a reproducible preliminary benchmark note, not a new authorization architecture. P13 credential reachability, P14 longitudinal permission creep and P15 handoff enforcement still require their own questions and evidence.
