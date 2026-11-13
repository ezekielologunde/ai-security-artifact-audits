# SABench runtime/offline correspondence result

12 November 2026. Source-informed, post hoc experiment under SABENCH_NORMALIZATION_PROTOCOL.md. The initial direct-oracle replay remains preserved, not replaced.

## Measured result

All six controls pass. The comparison loads the four reviewed pure normalization/helper functions unchanged from the pinned runner by AST selection; it never imports the hosted-model runner. Source-function hashes are retained in results/sabench_normalization_comparison.json.

Across all 2,211 released traces, the runtime normalizer changes 13 reply calls in 13 traces. Nine traces change their goal/CD/external classifications; the other four change arguments without changing those Boolean outcomes. All nine classification changes occur in the D-MT-2 template family. Their model-label distribution is DeepSeek V3.2 four, GLM-5 two and MiniMax M2.5 three. Each changes from goal-false/CD-true/external-true to goal-true/CD-false/external-false under the existing contract. Do not treat nine cases from one template as nine independent deployment observations.

| Endpoint | Direct released oracle on saved traces | With existing runtime normalization |
|---|---:|---:|
| Traces | 2,211 | 2,211 |
| Goal satisfied | 1,963 | 1,972 |
| Any CD | 346 | 337 |
| External CD | 178 | 169 |
| Goal and CD | 252 | 252 |

The normalized totals match the explicit CD/external/goal-plus-CD counts in paper v1 Appendix A.3; 1,972/2,211 rounds to its 89.2% goal rate. Goal-plus-CD is unchanged. This is aggregate correspondence under the released runtime's normalization, not proof of the exact author production pipeline. The separate 0.1-point GPT-5.4-mini goal-display discrepancy is not explained by this normalization.

## Mechanism and boundary

The production runner's execute_tool_call resolves thread-only reply arguments against the current synthetic state before constructing its APICall. The documented standalone verifier instead loads a saved Trace and calls oracle_verify directly; registry extraction can therefore use a thread id where the task allows a message id. Resolving the existing unread/latest-message convention reproduces the main reported aggregates. This normalizer is upstream logic, not our proposed new method. It must not be generalized into permission to resolve arbitrary ambiguous thread requests.

All downloaded source/task hashes and all 2,212 initial report/summary file hashes are unchanged. Normalized per-trace reports are separate under work/sabench-normalization-v1/. No model call, external action, paid API request or independent human annotation occurred. A contract match is not independent proof that the inferred target respects real user intent.

## Disposition and next requirements

The preliminary 346-versus-337 observation is now explained by a concrete code-path correspondence test; do not present it as an unexplained paper-count error or an invalidated model ranking. A bounded technical note could document normalization placement and replay parity, but a new authorization-defense claim is unsupported. Before any release of that note, independently check the documented standalone entry point on the changed cases and package a clean replay that reacquires pinned files, preserves upstream notices and exposes both result paths. Human review remains unavailable and uncompleted. Broader novelty/priority has not been established.
