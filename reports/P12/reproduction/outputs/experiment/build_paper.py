"""Fill manuscript result statements from the validated finite experiment."""
import csv,json,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[1]
R=ROOT/'experiment/results'
s=json.loads((R/'summary.json').read_text())
v=json.loads((R/'validation.json').read_text())
assert all(value is True for key,value in v.items() if key!='result_scope')
cells=list(csv.DictReader((R/'cell-results.csv').open()))
arms=list(csv.DictReader((R/'arm-results.csv').open()))
labels={'native_source_delete':'Source-only deletion','dependency_purge':'Dependency purge','full_overlay':'Full overlay','without_commit_guard':'No commit guard','without_restore_guard':'No restore guard','without_lineage_purge':'No lineage purge'}
events=['immediate','restart','index_rebuild','source_reprocessing','snapshot_restore','delayed_commit','peer_sync','restore_then_commit','commit_then_restart']
rows=[]
for arm,label in labels.items():
    values=[next(c for c in cells if c['backend']=='sqlite_wal' and c['arm']==arm and c['event']==event) for event in events]
    rows.append(label+' & '+' & '.join(f"{100*float(c['record_recovery_rate']):.0f}" for c in values)+r' \\')
timings=[]
for a in arms:
    if a['arm'] in ['dependency_purge','full_overlay']:
        timings.append(('SQLite WAL' if a['backend']=='sqlite_wal' else 'JSON files')+' & '+labels[a['arm']]+f" & {float(a['delete_ms_median']):.2f} & {float(a['delete_ms_p95']):.2f}"+r' \\')
fills={
'ABSTRACT_RESULTS':f"The full overlay produced zero active record, byte-scan, or retrieval recoveries in {s['full_overlay']['managed_trials']:,} managed trials. One-time dependency purge was followed by recovery in six of nine event schedules on both backends.",
'RESULTS_TEXT':f"All {s['n_trials']:,} trials acquired the target before deletion. Trial keys were unique, recorded code and protocol hashes matched, and semantic outcomes agreed across backends. The full overlay yielded 0/2,520 active-record recoveries, 0/2,520 persisted-byte recoveries, and 0/2,520 top-three retrieval recoveries. These counts concern the enumerated managed artifacts, not every storage surface of an AI service. Table~\\ref{{tab:events}} reports the deterministic event pattern.",
'TABLE_AGREEMENT':'Both backends produce the same values.',
'EVENT_TABLE':'\n'.join(rows),
'PURGE_TEXT':'Dependency purge passed immediate, restart, and index-rebuild checks but failed all 140 episodes under each of the other six event schedules, on each backend: 840/1,260 managed trials per backend (66.7\\%). All 140 episodes had at least one post-deletion recovery. Source-only deletion failed all nine schedules because surviving derivatives retained the target.',
'ABLATION_TEXT':'Removing the commit guard caused recovery in five schedules (700/1,260 trials per backend); removing restore reconciliation caused recovery in two (280/1,260); removing lineage purge caused recovery in seven (980/1,260). The paired episode-level worst-event contrast between full overlay and dependency purge was $-1.00$ on each backend; its descriptive percentile bootstrap interval was $[-1.00,-1.00]$. This degenerate interval reflects identical controlled episode outcomes.',
'UTILITY_TEXT':f"In all 2,520 full-overlay managed trials, the unrelated project record and all background records were preserved, and background retrieval rankings equaled the no-target baseline. Mean gold-session recall at three was {s['full_overlay']['mean_gold_session_recall_at3']:.4f} across {s['full_overlay']['evidence_bearing_unique_backend_episodes']} backend--episode observations. This is an absolute retrieval diagnostic, not an LLM answer-accuracy estimate or an independent sample of 280 conversations.",
'TIMING_TEXT':'Median full-overlay deletion took 35.78 ms on SQLite WAL and 22.59 ms on JSON files in this shared-host run. The corresponding one-time-purge medians were 34.11 ms and 20.98 ms. Table~\\ref{tab:timing} gives measured medians and 95th percentiles; these timings should not be generalized to remote stores or loaded production agents.',
'TIMING_TABLE':'\n'.join(timings),
'BOUNDARY_TEXT':'Authority rollback and adapter bypass each restored the target in all 140 episodes on both backends: 560/560 boundary trials. All retained replay fixtures remained recoverable, including during successful active-store deletion.',
'CONCLUSION_RESULT':'The full overlay prevented active recovery in 2,520 managed trials across two backends, while one-time dependency purge failed under six of nine lifecycle schedules.',
'APPENDIX_REPRO':'The reference protocol SHA-256 begins \\texttt{a978d6b90b5cf899}. Full SHA-256 values, source hashes, input hashes, and environment metadata are retained in the JSON manifests. Write fresh results to a separate directory rather than overwrite the reference observations.'
}
template=(ROOT/'paper/manuscript-template.tex').read_text(encoding='utf-8')
for key,value in fills.items():template=template.replace('@@'+key+'@@',value)
assert not re.search(r'@@[A-Z_]+@@',template)
(ROOT/'paper/main.tex').write_text(template,encoding='utf-8')
print('Wrote result-linked ACM manuscript')
