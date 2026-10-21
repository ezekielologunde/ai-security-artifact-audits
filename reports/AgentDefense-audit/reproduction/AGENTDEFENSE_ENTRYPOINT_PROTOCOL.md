# Entry-point reproduction protocol

21 October 2026, after source inspection and frame recount; not a blind or preregistered study.

The pinned integration guide explicitly recommends scripts/evaluate.py with consolidated/tier1_critical_tests.json (lines 249 onward). This makes the tier-1 combination a documented entry point. Other consolidated tiers are secondary schema-transfer probes. The README programmatic example instead selects the attacks key; inspect its iteration count against the actual tests-key file without connecting its HTTP adapter.

Run only the inspected MockDefense and run_evaluation definitions, with required standard-library definitions extracted by AST from pinned files. Never instantiate HTTP, OPA, NeMo, ModSecurity, or other external adapters. All payload strings remain inert inputs to json.dumps and substring matching. No source code rewriting, attack execution, model calls, or network traffic.

Evaluate seven previously qualified frames separately. Primary comparator: for records with a Boolean is_benign field, add expected_block = not is_benign in a temporary copy; otherwise keep original labels. Leave requests, prompts, IDs and adapter unchanged. This is a post-inspection label-schema normalization baseline, not a novel defense. Measure confusion counts, adapter call count, and empty request count. Check that adapter outcomes are identical between paired runs. Do not infer natural attack validity, real-world efficacy or published ranking effects.

Preserve SHA-256 of all inspected inputs before/after. Record the README selected-key iteration count separately. No new paper decision until prior-work/history and result scope have been reviewed.
