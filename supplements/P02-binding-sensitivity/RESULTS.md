# Controlled evidence-attribution sensitivity

19 November 2026. A new source-informed authored experiment, distinct from the original 36-case conformance study, 59-repository natural cohort and four-case disclosure discovery extension. No independent natural labels or runtime-security truth were created.

Under `BINDING_SENSITIVITY_PROTOCOL_20261119.md`, `run_binding_sensitivity.py` generated the full 72-case factorial design before evaluating either mode. Factors are selected-call syntax (literal / assigned variable / qualified class), selected Boolean flag, distractor (none / enabled other-model example / enabled HTML-comment text), one-/multi-line layout, and declared local-mapping presence. Every Python example parsed without being executed. Both modes received the same snapshots and selected source-line metadata. Reference route selection comes from the generator's explicit factors, not from either checker.

## Results

The reference property is whether the *authored selected example and declared mapping* describe an enabled custom route. It is not successful runtime loading or the truth of every security claim. There are 18 positive reference cases and 54 negative cases. Firings are `observed-loading-exposure`; non-firing includes abstention and must not be read as a safety verdict.

| Mode | Reference-positive firing | Reference-negative firing | Reference-positive non-firing | Reference-negative non-firing |
|---|---:|---:|---:|---:|
| Default README-wide check | 18 | 12 | 0 | 42 |
| Opt-in bound-loader check | 6 | 0 | 12 | 54 |

All 72 cases remain in the comparison. Of the 24 paired disagreements, 12 remove an unsupported firing and 12 lose a constructed enabled route. No significance test or generalization to a model population is justified by this enumerated authored design.

The default's 12 unsupported firings occur when the selected flag is false, a mapping exists, and an enabled other-model example or HTML comment supplies a README-wide True match. Strict mode's 12 missed enabled routes are the assigned-variable and qualified-class styles. It handles only the direct literal class/target form. One-/multi-line layout does not change the totals. This is a coverage-versus-attribution tradeoff, not an across-the-board improvement.

## Interpretation and limits

Both modes receive the explicit selector, but only strict mode consumes it. Thus this comparison is conditional on supplying selector information; it does not measure the cost, correctness or availability of selector annotations in natural repositories. The documented imports, target assignments and mapping factor are authored reference facts; no framework import, custom-module contents, real inference or dependency chain was verified. Wrong or misleading prose-claim association, aliases, shadowed imports, other languages and other loader families remain outside this design. Do not report the counts as natural precision/recall, malware detection, risk prevalence or proof of deployment safety.

The experiment supports a narrower engineering conclusion: replacing a document-wide signal with a limited bound-call grammar can remove some misattributions while reducing evidence coverage. It does not establish a new algorithmic contribution or justify a new paper by itself. Extending the parser directly against these now-visible cases would be development against known data, not a held-out improvement; a future efficacy comparison needs independent reference annotations and a frozen evaluation scope.

## Reproducibility

Complete cases and a preserved implementation are in `work/binding-sensitivity-20261119-v1`; all outputs, strata, paired counts and SHA-256 values are in `results/binding_sensitivity_20261119.json`. The runner refuses overwrites. The implementation and generated dataset were unchanged across execution. The original controlled input file, frozen natural-review plan and all 59 frozen prediction files also verified unchanged. No public artifact or manuscript was edited. Model calls, scanner runs, Python-example executions and independent annotations were all zero.
