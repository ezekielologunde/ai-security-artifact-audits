# Research positioning update — 6 October 2026

The field already studies external-memory deletion, derived-state residue, counterfactual behavior, control-plane enforcement, structural forgetting, and deletion completeness. A broad claim that AI memory deletion or a deletion overlay is new is unsupported. The research contribution is a bounded, reproducible systems experiment with explicit failure controls and a second behavioral/cache experiment.

## Closest additional work

| Primary source | What was inspected | Overlap and remaining question |
|---|---|---|
| [Yao et al., Forgetting Without Restarting](https://arxiv.org/html/2609.04875v1), arXiv:2609.04875v1 | Full HTML, including runtime assumptions, experiments, and limitations | Already combines provenance, sanitized replay, execution-state cleanup, counterfactual controls, and behavioral extraction. We cannot claim those ideas. Our persistent-store protocol tests independently current revocation authority, old-writer admission, snapshot resurrection, authority rollback, and interception bypass; we do not reproduce their KV reconstruction. |
| [Washio, Structural Forgetting](https://philpapers.org/rec/WASSFI) | Indexed abstract and excerpt; direct full-PDF access failed | Already frames reachability and reconstructability across layers, index/output gating, and key revocation. Full-method comparison remains incomplete. Our implementation does not claim crypto-erasure or energy savings. |
| [Gaggar, MemGov](https://jidmis.org/index.php/jidmis/article/download/3221/1415) | Full 16-page PDF | Already evaluates governed memory lifecycle and deletion on a synthetic enterprise workload. Its PDF specifies decoding settings but does not name the exact LLM/embedding version or provide a dataset/code download link that we found. Our contribution emphasizes reproducible, separately scored event/layer outcomes rather than a single completeness percentage. This is not independent replication of MemGov. |
| [Lee, Temvera manuscript and artifact](https://github.com/suanlab/temvera) | README and paper source pinned at `29a0fb66e40496981e74880f8687a26e17bd8c30` | Already inspects residual stores and distinguishes native API deletion from deletion requested in prose. This is a strong caution against treating our intentionally weak source-delete control as a vendor API. The paper reports a small seeded deletion history; our study stresses persistent scope revocation over a specified lifecycle grid. Repository venue labels describe artifact preparation, not verified acceptance. |

The earlier evidence review remains useful, but its pre-experiment status and tentative high-novelty language are superseded by this update and the final manuscript. Search coverage is a targeted review, not a registered systematic literature review or proof of priority.

## Final research question and gap

**RQ1:** Under controlled pre-deletion snapshot replay and delayed-write interleavings, does independently current project-scope revocation reduce active recoverability compared with one-time dependency purge while preserving unrelated records?

**RQ2:** Does absence from managed persistent storage imply absence from reachable process caches or absence of behavioral influence when a caller retains a model-authored summary?

**Gap addressed:** The engineering need to distinguish deletion acknowledgment, durable active-use revocation, reachable residual copies, and model responses through independently inspectable outcomes. Existing work covers many of these ideas; this study supplies a concrete cross-adapter challenge grid, an actual memoizer-remanence finding in its own implementation, and a bounded model-response extension. It does not establish that no previous paper combines them.

## Hypotheses and evidence boundaries

H1–H4 are the frozen storage-protocol hypotheses: one-time purge can fail after lifecycle transitions; full revocation lowers recovery; removing each guard exposes its corresponding failure; unrelated content is preserved. H5–H8 are frozen in the companion behavioral/cache protocol: derived/restored evidence can influence route choice; fresh-context full restore reproduces clean-world supplied evidence; unmanaged live summaries can preserve influence; explicit memoizer cleanup removes reachable target keys.

The behavioral protocol includes both direct emission and counterbalanced route probes, a never-seen world, a neutral-operation sham, acquisition checks, and unrelated-day accuracy. The sham is **not length matched**. All episodes, including failed acquisition and malformed outputs, are retained. The one-model greedy experiment cannot establish distributional forgetting; identical clean/full prompts are a construction check. The cache audit establishes removal of reachable memoizer keys, not physical heap zeroization.

## Dataset decision

The original public LongMemEval oracle and LoCoMo files are already downloaded, inspected, license-separated, and hashed. They remain appropriate background sources for this controlled experiment. The extension selects 12 episodes from each and uses fixed background excerpts; it does not report official QA benchmark accuracy. ToolSandbox and AgentDojo appear in Yao et al.'s study, but this experiment contains no tool-world replay, so downloading them without using their task contract would not strengthen validation. MemGov's synthetic corpus was not independently obtained. Large unused exploratory corpora are excluded from the final reproducibility bundle.

The local inference model is the official Qwen2.5-1.5B-Instruct Q4_K_M release. Its model revision, expected and observed SHA-256, runtime release/commit, license, and acquisition URLs are recorded separately. No inference provider receives the corpus or synthetic targets.

## What completion means

The deliverable is a completed, auditable research study and ACM-style manuscript based on its recorded experiments. It is not an accepted journal article or a universal deletion certificate. Stronger deployment claims require native-framework integration, multiple model families and stochastic probes, realistic asynchronous transactions, lineage-error tests, semantic embedding audits, and registered backup/log policies.
