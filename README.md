# AI Security Artifact Audits — Preliminary Technical Reports

Ezekiel Ologunde · Collection version 7 · 21 October 2026

Six bounded, reproducible audit notes, plus three separately identified existing studies in offboarding, memory deletion and model provenance. These reports have **not undergone independent peer review** and are not accepted ACM publications. ACM-style formatting does not imply ACM publication or endorsement. Claims apply to the pinned artifacts and controlled conditions described in each report; field-wide novelty is not established. The first four reports were released on 19 October; the scoring-helper audit was added on 20 October.

| Report | Evidence and scope |
|---|---|
| [Shadow AI dataset label leakage](reports/P03/shadow_ai_dataset_audit.pdf) | Two fresh generator runs; a retained feature alias exposes all 43 injected labels. This is not enterprise detector accuracy. |
| [Task–tool matching transfer](reports/P06/task_tool_transfer_audit.pdf) | Catalog-aware lexical baseline on ASTRA and processed TOUCAN; transfer errors and unresolved names remain visible. This is not a new authorization mechanism. |
| [Cross-model correctness join](reports/P11-P19/model_identity_join_audit.pdf) | Recounted published tables and controlled evidence of a join dropping model identity. No effect on unreleased correctness data is estimated. |
| [RAG chunk identity and revocation](reports/P23/rag_identity_revocation_audit.pdf) | Eight controlled ID-reuse cases expose stale indexes despite valid signatures. No production incidence, cryptographic break, or attacker access is established. |
| [HelpBench scoring-helper audit](reports/P04/helpbench_scoring_audit.pdf) | All 450 overall expert scores reproduce. Two negative helpers lose 19/439 and 39/450 defined numeric endpoints. Conditional aggregation is an expert-sample illustration, not a reconstruction of published model rankings. |
| [Memory deletion and reachable-cache remanence](reports/P12/memory_deletion_controlled_study.pdf) | Existing 14-page controlled study. Release validation reanalyzed 15,680 recorded storage trials and 792 recorded model calls; it freshly reproduced the separate 96-case cache audit. No new model inference or full storage rerun. |
| [Model-provenance consistency overlay](reports/P02/model_consistency_preliminary_study.pdf) | Existing six-page preliminary study. Public supplement reproduces 36 developer-authored cases and seven tests; natural evidence and independent annotations are excluded. The controlled 8/11 result does not establish natural accuracy. |
| [Agent offboarding correspondence study](reports/P01/offboarding_controlled_study.pdf) | Existing seven-page study. Fresh validation reran 720 fixture cases and matched 1,440 verdicts; separate raw-state readback checked existing 80-case process-recovery evidence. Pinned-origin restoration reconstructs 722 reference files before verification. |
| [AgentDefense-Bench entry-point audit](reports/AgentDefense-audit/agentdefense_entrypoint_audit.pdf) | Documented 640-record tier-1 path misinterprets labels; paired mock decisions stay unchanged. Seven exports replay separately. No published-score effect or temporal authority defense is established. |

Each report folder contains its PDF, Overleaf source ZIP, and an unpacked reproduction directory with protocols, results, acquisition scripts and source manifests. Read its local README and limitations before running anything. No model API call, cloud deployment or vulnerable upstream program is required by this release. Some acquisition steps require Internet access; larger original datasets and upstream source must be reacquired under their own terms.

## Reproduction and attribution

The preserved reproduction READMEs describe the original private preparation state and local tool paths. This root README and RELEASE_MANIFEST.json describe the public release. Original measurement files are preserved; publication copies identify manuscript availability or literature updates. A standard installed `acmart` class is required to rebuild TeX; the generated third-party class is deliberately not bundled.

Raw upstream datasets, downloaded paper copies, private working folders, and independent-review answer keys are excluded. Upstream notices inside reproduction directories apply only to their identified material. No blanket reuse licence is assigned to the authored reports or code in this release; contact the author before reuse beyond applicable rights. This does not replace or restrict upstream licences.

Independent review remains pending. Please distinguish a reproducible artifact-specific observation from a general claim about model or system safety. Publication here is a public technical-report release, not an external preprint-server submission or peer-reviewed acceptance.

The P12 supplement preserves recorded prompts containing corpus-derived public excerpts. Their LongMemEval MIT and LoCoMo CC BY-NC 4.0 terms remain applicable; corpus JSON payloads and model/runtime binaries are excluded. Its historical manuscript generators are archival hash evidence only; rebuild its current named paper from its Overleaf source. Read its dedicated reproduction README before execution.

The P02 report has a controlled-only public supplement. Its complete natural-cohort evidence and comparator archive remain private; neither its public commands nor the GitHub release supply independent natural labels. Its publication copy updates availability/reproduction wording while preserving scientific outcomes.

The P01 package includes 1,020 authored inert SQLite reference files, original verifier notices and task-prose templates. Its restore step fetches the pinned AgentTrap ledger from origin and checks reconstructed original hashes; the source ledger and copied task descriptions are excluded. Readback checks of stored framework evidence are distinct from freshly executing those extensions. Its canonical source repository remains private.
