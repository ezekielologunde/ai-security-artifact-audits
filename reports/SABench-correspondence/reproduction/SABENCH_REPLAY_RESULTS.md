# SABench pinned offline replay: initial result

12 November 2026. Protocol: SABENCH_ACQUISITION_PROTOCOL.md. Code/traces: `hjj194/sabench-artifact@1baf318fbdc55df2d190467a1b6bf91dfc5f6524`; tasks: `Phaedrus/sabench@21b40adec3f49d954c524c5c5aa95f30c2cb91fd`. These separate revisions are not assumed to be the exact paper-production pair.

## Acquisition and coverage

All 2,222 code/trace blobs match the pinned Git tree, totaling 1,511,229 bytes. Three separately pinned HF files total 318,527 bytes. Task/license notices are retained. There are 201 unique tasks from 47 templates, 45 ambiguous tasks and all 16 declared state/trap strata. All eleven source model-label cohorts contain exactly one trace for every task, with matching task/template IDs: 2,211 traces total.

The full local core (models, registry, state, oracle, package initialization and IO helpers) was inspected before import. No package installation or runner execution was needed. The unmodified oracle replays all 2,211 traces successfully. All acquired source/task hashes remain unchanged afterward; bytecode writes were disabled. Full per-trace reports are saved in work/sabench-oracle-replay-v1/. Exact results are in results/sabench_oracle_replay.json.

## Comparison needing investigation

| Endpoint | This pinned replay | Paper v1 statement |
|---|---:|---:|
| All traces | 2,211 | 2,211 |
| Goal satisfied | 1,963 (88.78%) | 89.2% (§6.1) |
| Any unauthorized write/CD | 346 (15.65%) | 337 (Appendix A.3), 15.2% |
| Goal and CD | 252 (11.40%) | 252 (Appendix A.3) |
| External CD | 178 (8.05%) | 169 (Appendix A.3), 7.6% |
| Ambiguous-task CD | 192/495 (38.79%) | 192/495 (Appendix A.7) |
| Non-ambiguous CD | 154/1,716 (8.97%) | 8.4% (Appendix A.7) |
| CD among goal-satisfied | 252/1,963 (12.84%) | 12.8% rounded |

Primary paper: https://arxiv.org/html/2610.34167v1 . A matching rounded conditional rate does not establish exact reproduction of its denominator. The paper's explicit count is 337 CD traces; do not infer an alternative integer solely from its rounded percentage.

These are discrepancies between separately pinned release components and the inspected versioned paper. They do not yet establish an oracle bug, fabricated data, changed model behavior or an invalid scientific conclusion. No paired historical task release or paper-production report has yet been identified. Next inspect revision history and metric normalization, then localize per-model differences without changing reference inputs. Preserve this initial replay rather than overwriting it.

## Claim boundary

Follow-up: SABENCH_NORMALIZATION_RESULTS.md now accounts for the main aggregate discrepancy using the already released runtime normalizer. It changes nine classifications and produces 337 CD and 169 external-CD cases while retaining 252 goal-plus-CD cases. The table above remains the preserved initial direct-replay result. It must not be cited as a currently unexplained paper-count error.

This recount measures an author-defined synthetic authorization contract. It does not authenticate model identities, establish independent semantic labels, measure actual harm or reproduce live agent execution. No new model inference or external tool action occurred. The existing ASTRA/TOUCAN lexical results are untouched and are not directly comparable to these stateful oracle outcomes. No new paper or defense is justified by this initial discrepancy alone.
