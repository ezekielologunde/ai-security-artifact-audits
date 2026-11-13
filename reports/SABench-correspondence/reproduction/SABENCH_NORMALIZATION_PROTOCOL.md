# Runtime-to-offline normalization correspondence test

12 November 2026. Explicitly post-replay and source-informed; baseline outcomes are known. This is not preregistration or a new normalization mechanism.

## Evidence motivating the test

The observed GitHub history has two commits; their comparison lists only LICENSE, README.md and pyproject.toml changes. The HF camera-ready task file at 62691d5e56a41faf78be378966f676da8d60591e is byte-identical to the pinned task file. These observed revision differences therefore do not explain the replay discrepancy.

Paper Table 4 correspondence localizes substantive differences to DeepSeek V3.2, MiniMax M2.5 and GLM-5. GPT-5.4-mini has only a 0.1-point goal-display difference. The exact replay remains preserved; rounded table percentages are not per-trace ground truth.

Source inspection identifies a candidate correspondence issue. `scripts/run_pilot_streaming.py:execute_tool_call` normalizes reply arguments using current state before creating APICall. Its normalization can resolve a thread_id to an unread/latest message id when no explicit entity id is supplied. By contrast, direct `Trace.from_dict` plus `oracle_verify` can retain the thread id as the write target. Some inspected released D-MT-2 traces use thread-only reply arguments. It is not yet established that this path accounts for all aggregate differences, or which production path generated the paper's outputs.

## Frozen comparison

Use the unchanged baseline, tasks and traces. Load only the exact reviewed normalizer and its three pure helper bodies from the pinned runner via AST selection; do not import or execute its API runner. The selected functions are normalize_write_args, email_id_from_thread_or_message_id, latest_email_id_in_thread and iter_emails. Preserve their source hashes and do not rewrite their logic.

For each trace, create a separate adapted copy. Process calls in order against a separately copied task state, applying the same argument normalization before each operation. Preserve explicit ids, call success, step, messages and final response. Update simulated state with the existing one-operation interpreter; do not call any external API or agent. Feed the adapted trace into the unchanged oracle and compare full goal/CD/external flags with the baseline. Report every changed trace and both argument forms. Never overwrite downloaded traces or the initial reports.

Controls before full recount: explicit id takes precedence over a thread id; thread containing an unread message resolves as implemented; all-read thread resolves its final message; missing thread remains unresolved; unrelated tool arguments are unchanged; original arguments/state remain unmodified by normalization. These controls test correspondence with the released implementation, not semantic policy truth.

Count changed calls, changed traces, goal/CD/external transitions and per-model totals. If rounded paper rates match, state only aggregate correspondence under this runtime normalization; do not claim proof of the author's actual scoring pipeline or independent authorization validity. If they do not match, preserve residual differences. Even a confirmed path mismatch would be a bounded artifact observation, not a novel general authorization defense.
