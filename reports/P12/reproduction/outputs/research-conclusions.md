# Final questions, hypotheses, and measured conclusions

The finished study comprises 15,680 original storage trials, 96 process-cache cases, and 792 actual local-model inferences. The model extension uses 24 episodes with no exclusion, one Qwen2.5-1.5B-Instruct Q4_K_M model and greedy decoding. Original protocols/results remain intact.

| Question / hypothesis | Recorded result | Interpretation |
|---|---|---|
| RQ1 / H1: Can purge pass initially and fail later? | Dependency purge passed immediate/restart/rebuild and failed six other schedules on both backends. | Yes, under the specified stale-state schedules. |
| H2: Does the full overlay lower active recovery? | 0/2,520 managed full-overlay recoveries; dependency purge 840/1,260 per backend. | Supported within the tested persistent-store contract. |
| H3: Do missing guards expose their corresponding failures? | Commit, restore and lineage ablations fail in 5, 2 and 7 schedules respectively. | Mechanism-specific support; not a distributed concurrency proof. |
| H4: Is unrelated stored material preserved? | All full-overlay background records, foil records and matched rankings preserved. | Storage preservation supported; generated-answer preservation is a different measure. |
| RQ2 / H5: Can derivatives/restored evidence influence a model? | Source-only route rate 87.5%; purge/restore 100%; never-seen 50%. Source-only and purge/restore emitted codes in 20/24 and 21/24 episodes. | Supported for supplied-context influence in this model. |
| H6: Does full restore with fresh caller context match clean evidence? | 120/120 prompts and response texts identical to never-seen; 0/24 code emission; 50% route rate. | Construction/reproducibility check, not statistical equivalence or weight unlearning. |
| H7: Can unmanaged live summaries retain influence? | Clean managed store in all 24 episodes, code emission in 8/24, route rate 89.6%; paired route increase 0.396, descriptive episode interval [0.229, 0.562]. | Supported boundary failure. In the 16 episodes without either direct code emission, target-route selection was still 87.5% versus 50% in matched never-seen episodes; this is descriptive subgroup analysis. |
| H8: Does the memoizer retain text after persistent purge? | 48/48 v1 cases retain reachable plaintext keys; explicit clear 0/48; all 96 active-file scans clean. | Supported CPython-specific reference-remanence finding; not physical heap erasure. |
| Exploratory label-swap check | 42/48 follow swapped preference, 37/48 reverse route, 47/48 valid; prompt token-count differences -1 or +1. | Sensitivity to evidence content; explicitly designed after early primary outputs. |
| Retained answer utility | Full/never-seen day accuracy 19/24; sham/source-only/purge-restore/live-summary 24/24. | Five fewer correct answers than contaminated state despite preserving the independent Y record. Clean-counterfactual equality does not preserve every earlier benefit. |
| Outside-boundary recovery | 560/560 authority-rollback/bypass cases recover; all replay fixtures retain targets. | No complete-erasure claim is justified. |

The gap is operational validation across distinct copy and admission boundaries, not the invention of cross-layer deletion or behavioral counterfactuals. `novelty-update.md` records strong overlapping work and incomplete-access comparisons. The completed artifact can support a bounded systems-study manuscript; stronger journal/deployment claims require native-framework integration, additional models and stochastic probes, realistic concurrency, lineage-error tests and backup/log policies.
