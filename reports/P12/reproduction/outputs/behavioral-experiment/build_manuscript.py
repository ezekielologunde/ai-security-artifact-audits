"""Compose the final manuscript from preserved v1 source and measured v2 results."""
import json,pathlib,re
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parent
def replace_once(text,old,new):
    assert text.count(old)==1,old[:120]
    return text.replace(old,new)
def main():
    s=json.loads((HERE/'results/summary.json').read_text());arms=s['arms'];contr=s['route_contrasts_vs_never_seen']
    robustness=json.loads((HERE/'results/robustness-summary.json').read_text())
    text=(ROOT/'paper/storage-contract-v1.tex').read_text(encoding='utf-8')
    text=replace_once(text,'These are deterministic storage-contract results, not measurements of language-model forgetting or deployment-wide erasure. The contribution is an executable, auditable evaluation of revocation durability and its assumptions, together with a portable reference implementation.',
      'A separate 24-episode extension executes 744 primary local-model inferences, including model-written summaries and paired direct/behavioral probes, followed by 48 exploratory evidence-swap probes. An additional cache audit finds reachable target-text memoizer keys in all 48 original-overlay cases despite clean active files; explicit cache clearing removes those keys in all 48 matched cases. Together these measurements distinguish durable active-use revocation, reachable process residue, and caller-retained evidence. They do not establish deployment-wide or physical erasure.')
    text=replace_once(text,'Only the first three are measured here. No language model is executed, no model weights are changed, and no semantic embedding inversion is attempted.',
      'The first study measures active artifacts and retained copies. A second study executes a local model with generated summaries and probes for explicit emission and route influence; a separate process-cache audit extends forensic coverage. Model weights are fixed and semantic embedding inversion is not attempted.')
    text=replace_once(text,'The result is an initial systems study that can later be extended to production memory frameworks and actual LLM decisions.',
      'The result is a bounded systems study with a small local-model extension; integration with production memory frameworks remains outside its validation.')
    text=replace_once(text,'Because full methods were unavailable during this pass and our experiment executes no LLM, we neither reproduce nor compare numerical behavioral effects.',
      'Because full methods were unavailable during this pass, we do not reproduce MemScope or compare its numerical effects with our independently specified local-model experiment.')
    text=replace_once(text,'\\caption{Result fields and their boundaries.}','\\caption{Storage-study result fields and their boundaries. Behavioral and cache outcomes are reported separately in Section~7.}')
    text=replace_once(text,'It does not claim field-wide priority or independent replication of a deployed framework.',
      'The extension additionally measures reachable memoizer keys and actual generated responses under six paired evidence conditions. It does not claim field-wide priority or independent replication of a deployed framework.')
    text=replace_once(text,'\\subsection{Novelty boundary}',r'''\subsection{Execution state, structural forgetting, and deployed APIs}
Yao et al.~\cite{yao2026} already reconstruct agent execution state through provenance-guided sanitized replay and compare behavioral outcomes with a clean counterfactual. Their result covers reconstructible runtime state under explicit assumptions, rather than model parameters or committed side effects. We therefore claim neither the first behavioral deletion audit nor the first provenance-based runtime cleanup. Our different operational emphasis is persistent revocation authority, stale admission, and snapshot resurrection; we do not reproduce their KV reconstruction.

Washio~\cite{washio2026} proposes structural forgetting through multiple gating and revocation mechanisms. Only the indexed abstract/excerpt was accessible, so a full-method comparison is not asserted. Gaggar~\cite{memgov2026} evaluates policy-governed lifecycle management on a synthetic enterprise workload. That study already includes deletion completeness; we emphasize separately inspectable transitions and boundaries rather than treating a completeness percentage as universal erasure.

Lee's Temvera artifact~\cite{temvera2026} distinguishes deletion requested in prose from native API deletion and inspects residual stores. Its source explicitly cautions against comparing a typed purge with an English instruction. Our source-only reference control is likewise deliberately weak: it cannot support a claim that a vendor's native API fails. The one-time dependency-purge arm provides our meaningful cleanup comparator.

\subsection{Novelty boundary}''')
    text=replace_once(text,'The reviewed literature establishes the need to examine derivatives and control-plane operations.',
      'The reviewed literature already establishes cross-layer cleanup, behavioral controls, and governed lifecycles. The remaining question here is the behavior of a specified persistent-store contract and its uncovered copy boundaries, rather than a demonstrated absence of such ideas in prior work.')
    for old,new in [
      ('Each injected project source has three deterministic copies:','In the storage study, each injected project source has three deterministic copies:'),
      ('\\section{Experimental Design}','\\section{Storage-Contract Experimental Design}'),
      ('\\section{Results}','\\section{Storage-Contract Results}')]:text=replace_once(text,old,new)
    labels={'never_seen':'Never seen','sham_delete':'Sham deletion','source_only':'Source only','purge_then_restore':'Purge + restore','full_then_restore':'Full + restore','full_live_summary':'Full + live summary'}
    lines=[]
    for a in labels:
        v=arms[a];lines.append(f"{labels[a]} & {v['code_any_n']}/24 & {v['target_route_rate']:.3f} & {v['valid_route_rate']:.3f} & {v['day_correct_n']}/24 \\\\")
    contrasts=[]
    for a in ['source_only','purge_then_restore','full_then_restore','full_live_summary']:
        c=contr[a];lo,hi=c['episode_bootstrap_95_percentile'];contrasts.append(f"{labels[a]} & {c['paired_difference']:+.3f} & [{lo:+.3f}, {hi:+.3f}] \\\\")
    extension=r'''\section{Behavioral and Reachable-Cache Extension}
\subsection{Question, hypotheses, and fixed protocol}
We ask a second question: \emph{Does absence from managed persistent storage imply absence from reachable process caches or absence of influence when a caller retains a model-written summary?} The protocol records H5: derivatives and one-time purge followed by restore permit greater target-route selection than never-seen; H6: full restore with fresh caller context reproduces clean-world supplied evidence; H7: unmanaged live summaries can preserve influence despite clean storage; and H8: the original memoizer retains reachable plaintext keys until explicitly cleared.

This extension is a separate experiment, preserving all original code and trial results. Its 24 episodes comprise the first two selected LongMemEval examples per six question types and 12 fixed hash-ranked LoCoMo examples. A fixed 1,500-character excerpt of the first background record supplies distractor context. These are corpus-grounded synthetic tasks, not official benchmark QA scores. The corpus does not supply the artificial secret or preference.

Each episode has a unique reproducible 24-hex code, a balanced seed-shuffled ALPHA/BETA preference, and an independent Project Y meeting day. One actual model-generated summary receives X and Y facts; that summary inherits both scopes and is reused unchanged across paired arms. No episode is excluded for failed acquisition. The independent Y source is retained when the mixed-scope summary is removed.

\subsection{Model, evidence conditions, and probes}
Inference uses official Qwen2.5-1.5B-Instruct Q4\_K\_M~\cite{qwenmodel}, pinned at revision \texttt{91cad51170dc3469}, with llama.cpp release b11425, one local CPU serving slot, 4,096 context tokens, eight threads, temperature zero, and seed 20261006. Prompt caching and RAM prompt-cache retention are disabled. This configuration does not establish physical KV erasure. The 24 summary calls allow 160 output tokens; 720 probe calls allow 48. The manifest records full model/runtime hashes, decoding settings, source/input hashes, and all requests and responses.

The never-seen arm receives only background and Y. Sham deletion removes a neutral Z record while X remains; it is an operation control, not a length-matched neutral-content control. Source-only removes X but retains its model-written summary. Purge-plus-restore reintroduces a pre-deletion snapshot after one-time scope cleanup. Full-plus-restore filters that snapshot against current revocation and supplies fresh caller context. Full-plus-live-summary leaves the managed store clean but supplies the old summary as earlier conversation evidence. Managed operations use the JSON adapter and the cache-clearing subclass; inference receives all current records directly, so this extension is not a learned-embedding retrieval test.

Two direct probes request the code, one explicitly allowing notes. Two route probes reverse option order. They ask for the recorded preference, or the first option if none is recorded, and never require the model to state the code. A fifth probe checks the retained Y day. Route parsing accepts a valid JSON label or a unique unambiguous ALPHA/BETA label; malformed/ambiguous answers count as non-target choices and their rate is separately reported. Direct emission is a lower-bound exact-string measure. The primary endpoint is each episode's mean target-choice indicator across both route orders, paired with never-seen. Percentile intervals resample 24 episode clusters 10,000 times with a fixed seed; they are descriptive conditional intervals, not a population guarantee.

\subsection{Generated-response results}
'''
    extension+=f"All {s['total_inferences']} primary planned inferences completed. The generated summary retained the exact code in {s['summary_code_acquired_n']}/24 episodes; the preferred route label appeared in {s['summary_route_label_present_n']}/24 summaries. Label presence alone does not establish correct preference semantics. Table~\\ref{{tab:behavior}} reports every episode, including acquisition failures. Full-plus-restore and never-seen each answered the retained day correctly in {arms['never_seen']['day_correct_n']}/24 episodes, versus {arms['sham_delete']['day_correct_n']}/24 for sham deletion. Thus matching the clean world does not preserve the contaminated state's higher generated-answer utility: retaining the independent Y source is weaker than preserving every answer. There were {s['truncated_response_n']} length-truncated probe responses, and the largest probe prompt had {s['max_prompt_tokens']} tokens.\n\n"
    extension+=r'''\begin{table}[t]
\caption{Actual model responses over 24 episodes per arm. Code is emission on either direct probe; target and valid route rates average both option orders; day is retained Y accuracy.}
\label{tab:behavior}
\centering
\begin{tabular}{lrrrr}
\toprule
Evidence condition & Code & Target route & Valid route & Day \\
\midrule
'''+ '\n'.join(lines)+r'''
\bottomrule
\end{tabular}
\end{table}
\begin{table}[t]
\caption{Target-route differences relative to never-seen, with episode-cluster percentile intervals. Option-order trials are not independent samples.}
\label{tab:behaviorcontrast}
\centering
\begin{tabular}{lrr}
\toprule
Evidence condition & Paired difference & Descriptive 95\% interval \\
\midrule
'''+ '\n'.join(contrasts)+r'''
\bottomrule
\end{tabular}
\end{table}
'''
    extension+=f"Full-plus-restore and never-seen supplied identical prompts in {s['full_vs_never_seen']['identical_prompt_n']}/120 comparisons and produced identical response text in {s['full_vs_never_seen']['identical_response_n']}/120. Prompt equality follows from the chosen evidence construction. It is a reproducibility check, not independent evidence of counterfactual trajectory reconstruction, distributional equivalence, or model-weight forgetting. Full-plus-live-summary contained no active target record in any episode, but caller-supplied target code remained in {arms['full_live_summary']['caller_context_code_n']}/24 episodes. That boundary condition measures whether old evidence supplied outside the managed adapter can influence responses.\n\n"
    extension+=r'''\subsection{Exploratory evidence-swap robustness check}
After inspecting early primary-run outputs, we specified an additional check using all 24 episodes, without exclusions. In each of the two full-plus-live-summary route prompts, we swap whole-word ALPHA/BETA labels only in the evidence; the task's option order, private code, and unrelated facts stay unchanged. This is an explicitly post-pilot exploratory intervention, not an additional preregistered hypothesis test. It asks whether choices track evidence content rather than merely the presence of a longer note.

'''
    extension+=f"Across 48 additional inferences, the model selected the swapped preference in {robustness['follows_swapped_preference_n']}/48 cases, changed to the opposite route in {robustness['opposite_choice_n']}/48, and produced a valid route in {robustness['valid_n']}/48. Prompt token counts were identical in {robustness['same_prompt_token_count_n']}/48; the observed difference range was [{robustness['prompt_tokens_difference_range'][0]}, {robustness['prompt_tokens_difference_range'][1]}]. These responses test sensitivity to supplied evidence, not hidden-state erasure. The total model workload is 792 inferences, with primary and exploratory observations stored separately.\n\n"
    extension+=r'''\subsection{Reachable memoization-key remanence}
The storage runner memoizes \texttt{vector(text)} with \texttt{functools.lru\_cache}. Although cached values are numerical vectors, its keys retain the input strings. In a separate CPython-specific audit, we inspect directly reachable cache dictionaries with \texttt{gc.get\_referents}; we do not scan arbitrary heap pages. Across 24 synthetic cases on each of two adapters, all 48 original full-overlay deletions leave a target-containing reachable key despite zero active-file matches. A subclass calling \texttt{vector.cache\_clear()} after deletion removes such keys in all 48 paired cases. All 96 cases preserve the unrelated record and have clean active-file scans.

This result corrects an important coverage ambiguity: the original persistent-file result remains true, but cannot describe all process copies. Clearing references is not physical zeroization, and other holders may retain the same string. The cache fix clears unrelated memoized vectors too, creating a potential recomputation cost; the persistent background records remain unchanged. We make no performance claim for this extension.

'''
    text=replace_once(text,'\\section{Discussion}',extension+'\\section{Discussion}')
    text=replace_once(text,'A follow-up LLM experiment should use independently authored semantic preferences, never-exposed and length-matched sham worlds, repeated generation, and separate forensic evidence. Its endpoint should be measured rather than inferred from literal preference removal.',
      'The extension directly measures route selection and never-seen behavior, but uses only one greedy model, synthetic preferences, and an operation sham. Independently authored semantic preferences, length-matched shams, stochastic probes, and retained-correlate tests remain necessary for stronger behavioral generalization.')
    text=replace_once(text,'The derivative layers are deterministic records; the checkpoint is not a model-weight checkpoint or KV cache.',
      'The first study uses deterministic derivatives; its checkpoint is not a model-weight checkpoint or KV cache. The second uses generated summaries and actual responses, but does not reproduce a full autonomous agent trajectory.')
    text=replace_once(text,'The numerical-vector cache used to accelerate repeated computation is not subjected to a neural inversion audit.',
      'The separate memoizer audit establishes plaintext-key reachability in the original implementation and reference removal after clearing, not heap erasure or neural inversion. The local inference server and operating system may retain physical buffers outside this contract.')
    text=replace_once(text,'This study does not conduct a behavioral equivalence or generated-answer noninferiority test.',
      'The 24-episode extension has two route orders within episode, shared LoCoMo conversations, and one greedy quantized model. Its conditional bootstrap does not resolve between-conversation dependence. There is no powered behavioral equivalence or generated-answer noninferiority test; identical full/clean prompts cannot supply such evidence.')
    text=replace_once(text,'No user conversations are sent to an inference provider during this study.',
      'The extension sends downloaded public background excerpts and synthetic targets only to a local inference server; no inference provider receives them. Its model card declares Apache 2.0.')
    text=replace_once(text,'The next research step is to reproduce the protocol in real agent-memory frameworks and extend measurement to LLM behavior and semantic inference; the present storage outcomes cannot substitute for those measurements.',
      'The separate model-response extension adds behavioral measurements, while the cache audit demonstrates reachable process residue missed by active-file scans. Complete deletion requires an explicit policy for each copy and future admission path. Native-framework integration, multiple model families, stochastic behavioral audits, realistic concurrent transactions, and semantic inference remain needed before general deployment claims.')
    abstract='''Deleting a memory record does not ensure that an agent cannot recover or reuse its contents. We evaluate a project-scope revocation overlay combining materialized lineage, an independently current authority, commit validation, and restore reconciliation. A controlled study uses 140 corpus-grounded episodes, two persistent reference backends, six configurations, and 15,680 lifecycle and boundary trials. The full overlay yields zero active-record, persisted-file, or retrieval recoveries in 2,520 managed trials; one-time dependency purge fails after six of nine event schedules. Authority rollback and interception bypass defeat the overlay, and retained replay copies remain recoverable. A separate 24-episode experiment executes 744 primary local-model inferences plus 48 exploratory evidence-swap probes. Guarded restoration with fresh caller context matches the never-seen control by evidence construction, whereas caller-retained summaries preserve behavioral influence despite clean managed storage. A process-cache audit finds target-containing memoization keys in all 48 original-overlay cases; explicit cache clearing removes those reachable keys in all 48 matched cases. These results distinguish durable active-use revocation, recoverable process copies, and supplied-context influence. They do not establish model-weight forgetting, physical zeroization, or deployment-wide erasure. The contribution is an auditable bounded systems study, with explicit failure assumptions and reproducible artifacts.'''
    text=re.sub(r'(?<=\\begin\{abstract\})[\s\S]*?(?=\\end\{abstract\})',lambda _: '\n'+abstract+'\n',text,count=1)
    text=replace_once(text,'\\begin{thebibliography}{12}','\\begin{thebibliography}{17}')
    refs=r'''\bibitem{yao2026} Chao Yao, Yangbo Wei, Zhen Huang, Junhong Qian, Chenle Chen, Shaoqiang Lu, Chen Wu, and Lei He. 2026. Forgetting Without Restarting: Execution-State Unlearning for Stateful LLM Agents. arXiv:2609.04875v1. \url{https://arxiv.org/abs/2609.04875}.
\bibitem{washio2026} Wataru Washio. 2026. Structural Forgetting in AI Memory Systems: A Two-Phase Framework Unifying Index Blocking, Output Gating, Selective Power Gating, and Key Revocation. Preprint; indexed abstract/excerpt consulted. \url{https://philpapers.org/rec/WASSFI}.
\bibitem{memgov2026} Harish Gaggar. 2026. MemGov: Policy-Governed Memory Lifecycle Management for Enterprise LLM Agents. \emph{Journal of Intelligent Decision Making and Information Science} 3(11s), 2199--2214. \url{https://jidmis.org/index.php/jidmis/article/view/3221}.
\bibitem{temvera2026} Suan Lee. 2026. Temporal Fields Are Not Temporal Correctness: Measuring Bitemporal and Deletion Semantics in Deployed Agent Memory. Research manuscript and Temvera artifact; repository revision \texttt{29a0fb66e4049698}. Publication acceptance not independently established. \url{https://github.com/suanlab/temvera}.
\bibitem{qwenmodel} Qwen Team. 2024. Qwen2.5-1.5B-Instruct-GGUF. Official model card and Apache-2.0 licensed model; pinned revision \texttt{91cad51170dc3469}. \url{https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF}.
'''
    text=replace_once(text,'\\end{thebibliography}',refs+'\\end{thebibliography}')
    text=replace_once(text,'\\section{Interpreting the Recorded Outcomes}',r'''\section{Extension Reproduction}
Fetch the pinned model/runtime using the extension's acquisition script, start its localhost server with the recorded arguments, and run the cache audit, behavioral runner, and analyzer. The model weights are deliberately excluded from the ZIP because they are independently downloadable and hash-verified. Research prompts and responses intentionally retain synthetic targets outside the deletion contract. Original results are preserved in the storage-study artifact; do not overwrite reference observations when reproducing.

\begin{verbatim}
python behavioral-experiment/acquire_llm.py
python behavioral-experiment/cache_audit.py
python behavioral-experiment/run_behavior.py
python behavioral-experiment/analyze_behavior.py
python behavioral-experiment/run_robustness.py
\end{verbatim}
The acquisition script expects this project layout, with the supplied corpora in the outputs data directory. Full server startup instructions and checksums are in the companion README and manifests.

\section{Interpreting the Recorded Outcomes}''')
    (ROOT/'paper/main.tex').write_text(text,encoding='utf-8')
    print('Wrote final manuscript from preserved v1 source and measured v2 summary.')
if __name__=='__main__':main()
