# AI Security Artifact Audits — Preliminary Technical Reports

Ezekiel Ologunde · Collection version 21 · 22 November 2026

Eleven bounded, reproducible audit notes, plus three separately identified existing studies in offboarding, memory deletion and model provenance. These reports have **not undergone independent peer review** and are not accepted ACM publications. ACM-style formatting does not imply ACM publication or endorsement. Claims apply to the pinned artifacts and controlled conditions described in each report; field-wide novelty is not established. The first four reports were released on 19 October; the scoring-helper audit was added on 20 October.

| Report | Evidence and scope |
|---|---|
| [Shadow AI dataset label leakage](reports/P03/shadow_ai_dataset_audit.pdf) | Two fresh generator runs; a retained feature alias exposes all 43 injected labels. This is not enterprise detector accuracy. |
| [Task–tool matching transfer](reports/P06/task_tool_transfer_audit.pdf) | Catalog-aware lexical baseline on ASTRA and processed TOUCAN; transfer errors and unresolved names remain visible. This is not a new authorization mechanism. |
| [Cross-model correctness join](reports/P11-P19/model_identity_join_audit.pdf) | Recounted published tables and controlled evidence of a join dropping model identity. No effect on unreleased correctness data is estimated. |
| [RAG chunk identity and revocation](reports/P23/rag_identity_revocation_audit.pdf) | Eight controlled ID-reuse cases expose stale indexes despite valid signatures. No production incidence, cryptographic break, or attacker access is established. |
| [HelpBench scoring-helper audit](reports/P04/helpbench_scoring_audit.pdf) | All 450 overall expert scores reproduce. Two negative helpers lose 19/439 and 39/450 defined numeric endpoints. Conditional aggregation is an expert-sample illustration, not a reconstruction of published model rankings. Public-source revision pins Google/helpseeking and adds a separate [four-condition follow-up replay](reports/P04/public_source_followup.zip); original results and all 25 reproduction files remain unchanged. |
| [Memory deletion and reachable-cache remanence](reports/P12/memory_deletion_controlled_study.pdf) | Existing 15-page controlled study. Earlier release validation reanalyzed 15,680 recorded storage trials and 792 recorded model calls and reproduced the separate 96-case cache audit. The literature-only revision preserves all reproduction bytes; no new experiment runs. |
| [Model-provenance consistency overlay](reports/P02/model_consistency_preliminary_study.pdf) | Seven-page preliminary study; literature-only revision adds ReleaseSeal and knowyourai and qualifies novelty. Original 36-case results and all 14 reproduction files unchanged; natural accuracy remains unmeasured. The controlled 8/11 result does not establish natural accuracy. |
| [Agent offboarding correspondence study](reports/P01/offboarding_controlled_study.pdf) | Existing seven-page study. Fresh validation reran 720 fixture cases and matched 1,440 verdicts; separate raw-state readback checked existing 80-case process-recovery evidence. Pinned-origin restoration reconstructs 722 reference files before verification. |
| [AgentDefense-Bench entry-point audit](reports/AgentDefense-audit/agentdefense_entrypoint_audit.pdf) | Documented 640-record tier-1 path misinterprets labels; paired mock decisions stay unchanged. Seven exports replay separately. No published-score effect or temporal authority defense is established. |
| [SABench replay correspondence](reports/SABench-correspondence/sabench_replay_correspondence.pdf) | Direct and runtime-normalized replay of 2,211 released traces; thirteen normalized calls and nine changed classifications. Reuses upstream logic and recovers the main reported counts. Four-command clean replay; no new inference or defense-efficacy claim. |
| [Generated Rego oracle semantics](reports/P22-Rego-oracles/rego_oracle_semantics_audit.pdf) | Four conditional per-request witnesses across two repositories; explicit-contract assertions reject those outcomes. All 1,404 native commands and 56 aggregate fields reproduce from a clean package. Known language hazard and mutation operator; no confirmed semantic escape from an originally passing full suite or deployment efficacy claim. |
| [LinEra interrupted compaction](reports/LinEra-compaction/linera_compaction_availability_audit.pdf) | Retained objects become unreadable at one core-store interruption boundary; a journal comparator preserves reads in tested cases. No cryptographic break or physical erasure claim. |
| [Lightfoot transaction boundary](reports/Lightfoot-transaction/lightfoot_transaction_boundary_audit.pdf) | Two deferred-save storage mismatches; no retired text or final-ranked retired IDs in 16 controlled native query observations. Deterministic embeddings; no learned-model or disclosure claim. |
| [RAC compensation adapter replication](reports/RAC-adapter-replication/rac_adapter_replication.pdf) | Replicates known core returned-error behavior and extends it to the unchanged native adapter. Four explicit-error bookkeeping cases, three through that adapter; a status guard reports failure without restoring state. All 21 upstream tests and 16 authored conditions reproduce. |

Each report folder contains its PDF, Overleaf source ZIP, and an unpacked reproduction directory with protocols, results, acquisition scripts and source manifests. Read its local README and limitations before running anything. No model API call, cloud deployment or vulnerable upstream program is required by this release. Some acquisition steps require Internet access; larger original datasets and upstream source must be reacquired under their own terms.

## Reproduction and attribution

The preserved reproduction READMEs describe the original private preparation state and local tool paths. This root README and RELEASE_MANIFEST.json describe the public release. Original measurement files are preserved; publication copies identify manuscript availability or literature updates. A standard installed `acmart` class is required to rebuild TeX; the generated third-party class is deliberately not bundled.

The SABench correspondence supplement includes its pinned synthetic upstream tasks/traces under CC BY 4.0 and code under MIT, with explicit attribution. Other raw upstream datasets, downloaded paper copies, private working folders, and independent-review answer keys are excluded. Upstream notices inside reproduction directories apply only to their identified material. Authored reports are licensed under CC BY 4.0 and authored code under MIT, as selected by the author on 21 November 2026. See RIGHTS.md and the licence notices; third-party material retains its own terms. This does not replace or restrict upstream licences.

External peer review is not a prerequisite for these preprints. Please distinguish a reproducible artifact-specific observation from a general claim about model or system safety. Publication here is a public technical-report release, not an external preprint-server submission or peer-reviewed acceptance.

The P12 supplement preserves recorded prompts containing corpus-derived public excerpts. Their LongMemEval MIT and LoCoMo CC BY-NC 4.0 terms remain applicable; corpus JSON payloads and model/runtime binaries are excluded. Its historical manuscript generators are archival hash evidence only; rebuild its current named paper from its Overleaf source. Read its dedicated reproduction README before execution.

The P02 report has a controlled-only public supplement. Its complete natural-cohort evidence and comparator archive remain private; neither its public commands nor the GitHub release supply independent natural labels. Its publication copy updates availability/reproduction wording while preserving scientific outcomes.

The P01 package includes 1,020 authored inert SQLite reference files, original verifier notices and task-prose templates. Its restore step fetches the pinned AgentTrap ledger from origin and checks reconstructed original hashes; the source ledger and copied task descriptions are excluded. Readback checks of stored framework evidence are distinct from freshly executing those extensions. Its canonical source repository remains private.

## Separate engineering supplement

[Loader-context CLI extension](supplements/P02-loader-context/README.md) adds lexical context and an explicit selected remote-code flag. The new controlled diagnostic now abstains when that flag is false. Eighteen tests, 180 original-case comparisons and four discovery replays pass, with seven pinned compact files reacquired. General README call/target binding remains incomplete. This is not a paper revision or independent natural validation; all published studies and frozen reproduction directories remain unchanged.

## Authored evidence-attribution sensitivity study

[Separate 72-case P02 sensitivity study](supplements/P02-binding-sensitivity/README.md) reports both sides of a controlled tradeoff: default mode fires on 18 constructed enabled routes and 12 negative routes; strict mode fires on 6 enabled and zero negative routes, missing 12 enabled routes. All 144 outputs reproduce after clean dataset regeneration. These counts are not natural precision/recall, runtime security or evidence of a new algorithm. The earlier six-page paper and its zero-false-positive result remain scoped to the original 36 cases; all existing PDFs and frozen reproduction directories are unchanged.

## Authored licensing update

Version 16 applies the author-selected CC BY 4.0 report licence and MIT code licence to authored material. All ten report PDFs, source archives, reproduction files and technical supplements retain their previous bytes. Preserved embedded preparation notices are historical; RIGHTS.md supplies the current authored licensing decision. This update adds no experiment, manuscript, independent review or external submission. Local LinEra/Lightfoot notes and the separate P12 arXiv draft are excluded.

## Rego generated-oracle audit addition

Version 17 adds the five-page P22 empirical audit, Overleaf source, authored replay tooling and aggregate expectations. The raw anonymous artifact and OPA runtime are reacquired under their own terms and verified by hash; they are not redistributed. All ten earlier reports and their reproduction files retain their previous bytes. The new report is a technical preprint release on GitHub; no external preprint-server submission has been made.

## Lifecycle preprint additions

Version 18 adds the unchanged three-page LinEra and Lightfoot preprints, Overleaf sources and licensed replay archives. Publication checks verify all 16 and 41 listed archive members respectively and retain the recorded clean-replay evidence; no new experiment is claimed. The selected upstream source is MIT licensed with notices preserved. All eleven prior reports and their frozen reproduction files retain their bytes. These are public GitHub preprints; no external preprint-server submission has occurred.

## RAC replication-and-extension addition

Version 19 adds the four-page RAC adapter replication note, Overleaf source and 65-member replay archive. The exact core behavior has prior practitioner evidence; the report claims only a bounded native-adapter extension and comparison. All 13 earlier report PDFs and frozen reproduction files retain their bytes. No new experiment was required to prepare the manuscript, and no external preprint-server submission has occurred.

## Provenance-study literature revision

Version 20 updates only P02 publication files and root release metadata. The seven-page paper adds direct comparators and chronology; its abstract, scientific sections, results and conclusion remain unchanged. All 14 P02 reproduction files, the separate P02 engineering supplements and all other 13 reports retain their bytes. No new experiment or external preprint-server submission occurred for this revision. LITERATURE_REVISION.json records the before/after identities and protected-source checks.
