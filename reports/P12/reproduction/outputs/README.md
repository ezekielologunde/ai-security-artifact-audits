# Completed secure-memory-deletion study

The final manuscript is `secure-memory-deletion-paper.pdf` (14 pages). Upload `overleaf-acm-paper.zip` to Overleaf. `validated-experiment.zip` contains the project-layout code, measured data inputs with upstream licenses, original storage shards, model-response logs, analysis, protocols and validation reports. Model weights and portable executables are excluded; the pinned downloader verifies them independently.

The original study completed 15,680 storage trials over 140 corpus-grounded episodes and two reference backends. The full overlay prevented active recovery in 2,520 managed trials; one-time purge failed after six of nine schedules. Authority rollback and adapter bypass restored targets in all 560 boundary cases. Retained replay fixtures remain recoverable.

The extension completed 792 actual local-model inferences: 24 summaries, 720 primary probes, and 48 explicitly exploratory evidence-swap probes. In 24 episodes, full guarded restore emitted no target code and matched never-seen prompts/responses in 120/120 comparisons. This equality follows from evidence construction and is not model-unlearning proof. Caller-retained summaries emitted the code in 8/24 episodes and yielded 89.6% target-route selection, compared with 50.0% in never-seen. Retained-day accuracy was 19/24 for full restore and never-seen, versus 24/24 for sham deletion. All outcomes and acquisition failures are retained.

The separate cache audit completed 96 cases. The original overlay left reachable plaintext memoizer keys in 48/48 cases despite clean persistent files; the cache-clearing subclass removed those reachable keys in 48/48 matched cases. This is reference removal, not physical heap zeroization.

Start with `novelty-update.md` for research questions and gaps, `research-conclusions.md` for hypothesis outcomes, `experiment/README.md` for the preserved storage study, `behavioral-experiment/README.md` for the extension, and `paper/README.md` for Overleaf. The earlier research briefs and pilot are historical preparation and are superseded by the final evidence.

The manuscript is anonymous and is a completed bounded research draft, not an accepted publication or a deletion certificate. One small quantized model, oracle scope labels, deterministic schedules and reference adapters limit generalization. LongMemEval's declared MIT and LoCoMo's CC BY-NC 4.0 terms remain distinct; the Qwen model card declares Apache 2.0. No inference provider receives the data.
