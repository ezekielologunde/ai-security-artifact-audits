# Behavioral and reachable-cache extension

This extension preserves the original storage study in `../experiment`. It runs an actual local Qwen2.5-1.5B-Instruct Q4_K_M model and separately audits reachable CPython memoizer keys. It does not certify whole-system erasure.

The protocol fixes 24 background-grounded episodes, six paired arms, two direct probes, two counterbalanced route probes, and one unrelated meeting-day probe: 720 probe calls plus 24 model-authored summaries. All episodes are retained. LongMemEval and LoCoMo supply background diversity only; these are not official benchmark QA scores. A model-written summary with both X and Y lineage is removed wholesale when X is deleted; the independent Y source stays available.

`never_seen` contains only background and Y. `sham_delete` removes a separate neutral Z record while retaining X. `source_only` removes the X source but leaves its model-authored summary. `purge_then_restore` purges X once, then restores an old snapshot. `full_then_restore` rejects stale X artifacts at restore and uses fresh caller context. `full_live_summary` leaves managed storage clean but supplies the old summary through caller-retained conversation context. The sham is an operation control, not a length-matched neutral-content control.

The primary endpoint compares target-route choice against the measured never-seen baseline, averaged across both option orders within episode. Malformed/ambiguous responses count as failure to choose the target and are reported separately. Two direct probes measure exact synthetic-code emission. Day accuracy is absolute and paired, so poor baseline model capability remains visible. Greedy outputs and identical full/clean prompts are a construction check, not evidence of distributional equivalence or weight unlearning.

The cache audit examines directly reachable string keys of the v1 `functools.lru_cache` using `gc.get_referents`, which is CPython-specific. Clearing the cache removes its references; it does not overwrite Python heap pages or remove other references. `CacheClearingOverlay` adds this cleanup to the v1 overlay without changing the frozen v1 code.

## Reproduction

Use Python 3.12. Fetch the original corpora with `../experiment/download_data.py` first. Fetch the pinned portable runtime and model with `acquire_llm.py`; hashes and upstream license/card are recorded in `model-manifest.json`. The model is approximately 1.12 GB and is excluded from result ZIPs.

From the project root, start the local runtime in a terminal:

```powershell
work/llm/runtime/llama-server.exe -m work/llm/qwen2.5-1.5b-instruct-q4_k_m.gguf -c 4096 -t 8 -tb 8 -np 1 --host 127.0.0.1 --port 8766 --no-cache-prompt --cache-ram 0 --no-cache-idle-slots --offline
python outputs/behavioral-experiment/cache_audit.py
python outputs/behavioral-experiment/run_behavior.py
python outputs/behavioral-experiment/analyze_behavior.py
```

The runner writes `results/`; preserve reference observations or run in a copied project. Every prompt, response, decoding setting, target, choice, duration, and token count is retained. Research logs intentionally contain synthetic targets and are outside the deletion contract. Prompt caching is disabled; no physical KV cleanup is claimed. Inference runs only at localhost and uses no inference-provider credentials.

## Limits

One small quantized model at temperature zero; oracle lineage; serialized JSON reference adapter; brief fixed corpus excerpts; synthetic preferences; fixed arm order; two questions can share a LoCoMo conversation. Episode bootstrap intervals are descriptive conditional intervals, not a population or conversation-independent estimate. No semantic embedding inversion, real asynchronous transaction proof, provider backup/log audit, full-agent benchmark, or accepted publication is claimed.

## Completed exploratory robustness check

After the primary run, `run_robustness.py` executes the separately recorded `robustness-protocol.json`: 48 route calls with labels swapped only in the evidence. This check was designed after early primary outputs and is exploratory. All 24 episodes are retained. Run it after the primary runner; its summary and manifest are stored separately. The final model total is 792 calls. `results/final-validation.json` independently verifies every evidence swap, preserved private code and task, source/protocol hashes and completeness. The field named `primary_code_unchanged` in the exploratory summary originally checks task identity; the final validator separately checks the actual private code as well.
