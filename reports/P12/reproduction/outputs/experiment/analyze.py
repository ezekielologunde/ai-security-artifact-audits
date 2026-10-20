"""Merge shards, audit outcome integrity, and derive tables from recorded trials."""
import argparse,collections,csv,hashlib,json,math,pathlib,statistics
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
R=ROOT/'experiment/results';P=ROOT/'paper';P.mkdir(exist_ok=True)
def wilson(x,n,z=1.959963984540054):
    p=x/n;den=1+z*z/n;c=(p+z*z/(2*n))/den;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,c-h),min(1,c+h)]
def export_csv(path,rows):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
    global R
    parser=argparse.ArgumentParser();parser.add_argument('--results',type=pathlib.Path,default=R)
    R=parser.parse_args().results
    rows=[];manifests=[];episodes=[]
    folders=sorted(R.glob('shard-*')) or [R]
    for folder in folders:
        manifest=json.loads((folder/'run-manifest.json').read_text());assert 'run_finished_unix' in manifest,'Incomplete shard '+str(folder)
        part=[json.loads(x) for x in (folder/'trials.jsonl').read_text().splitlines() if x.strip()]
        assert len(part)==manifest['n_trials'];rows+=part;manifests.append(manifest);episodes+=json.loads((folder/'episode-manifest.json').read_text())
    assert len(episodes)==140 and len(rows)==15680
    identifiers=[(x['episode_id'],x['backend'],x['arm'],x['event']) for x in rows]
    assert len(identifiers)==len(set(identifiers))
    assert len({x['protocol_sha256'] for x in manifests})==1
    assert all(x['code_sha256']==manifests[0]['code_sha256'] for x in manifests)
    for name,expected in manifests[0]['code_sha256'].items():
        assert hashlib.sha256((ROOT/'experiment'/name).read_bytes()).hexdigest()==expected,'Code changed during run: '+name
    (R/'trials.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows),encoding='utf-8')
    (R/'run-manifests.json').write_text(json.dumps(manifests,indent=2),encoding='utf-8')
    (R/'episode-manifest.json').write_text(json.dumps(episodes,indent=2),encoding='utf-8')
    groups=collections.defaultdict(list)
    for row in rows:groups[(row['backend'],row['arm'],row['event'])].append(row)
    cells=[]
    for (backend,arm,event),values in sorted(groups.items()):
        n=len(values);recovery=sum(x['record_recovery'] for x in values)
        cells.append({'backend':backend,'arm':arm,'event':event,'n':n,'record_recovery_count':recovery,'record_recovery_rate':recovery/n,'byte_recovery_count':sum(x['persisted_byte_recovery'] for x in values),'retrieval_recovery_count':sum(x['retrieval_recovery_at3'] for x in values),'pre_acquired_count':sum(x['pre_acquired'] for x in values),'control_preserved_count':sum(x['foil_preserved'] for x in values),'ranking_unchanged_count':sum(x['background_ranking_unchanged'] for x in values),'background_unchanged_count':sum(x['background_records_unchanged'] for x in values),'delete_ms_median':statistics.median(x['delete_ms'] for x in values),'delete_ms_p95':float(np.percentile([x['delete_ms'] for x in values],95)),'event_ms_median':statistics.median(x['event_ms'] for x in values),'boundary':values[0]['boundary_case']})
    export_csv(R/'cell-results.csv',cells)
    main=[x for x in rows if not x['boundary_case']]
    worst=collections.defaultdict(list)
    for x in main:worst[(x['backend'],x['arm'],x['episode_id'])].append(x)
    per_episode=[{'backend':key[0],'arm':key[1],'episode_id':key[2],'any_event_recovery':any(x['record_recovery'] for x in values),'any_event_byte_recovery':any(x['persisted_byte_recovery'] for x in values)} for key,values in sorted(worst.items())]
    export_csv(R/'episode-results.csv',per_episode)
    arm_summary=[]
    for backend in ['sqlite_wal','json_files']:
        for arm in ['native_source_delete','dependency_purge','full_overlay','without_commit_guard','without_restore_guard','without_lineage_purge']:
            v=[x for x in main if x['backend']==backend and x['arm']==arm];e=[x for x in per_episode if x['backend']==backend and x['arm']==arm]
            arm_summary.append({'backend':backend,'arm':arm,'n_trials':len(v),'n_episodes':len(e),'pooled_recovery_count':sum(x['record_recovery'] for x in v),'pooled_recovery_rate':sum(x['record_recovery'] for x in v)/len(v),'worst_event_episodes':sum(x['any_event_recovery'] for x in e),'delete_ms_median':statistics.median(x['delete_ms'] for x in v),'delete_ms_p95':float(np.percentile([x['delete_ms'] for x in v],95)),'control_preservation_rate':sum(x['foil_preserved'] for x in v)/len(v),'background_unchanged_rate':sum(x['background_records_unchanged'] for x in v)/len(v),'ranking_unchanged_rate':sum(x['background_ranking_unchanged'] for x in v)/len(v)})
    export_csv(R/'arm-results.csv',arm_summary)
    # Semantic cross-backend consistency independent of timing and byte layout.
    pair=collections.defaultdict(dict)
    fields=['record_recovery','layers','foil_preserved','background_records_unchanged','background_ranking_unchanged','retrieval_recovery_at3']
    for x in rows:pair[(x['episode_id'],x['arm'],x['event'])][x['backend']]=x
    mismatches=[]
    for key,v in pair.items():
        for field in fields:
            if v['sqlite_wal'][field]!=v['json_files'][field]:mismatches.append({'trial':key,'field':field})
    full=[x for x in main if x['arm']=='full_overlay']
    boundary=[x for x in rows if x['boundary_case']]
    eligible=[x for x in full if x['gold_session_recall_after_at3'] is not None]
    unique_utility={ (x['backend'],x['episode_id']):x for x in full if x['event']=='immediate' and x['gold_session_recall_after_at3'] is not None}
    summary={'n_episodes':len(episodes),'n_trials':len(rows),'managed_trials':len(main),'boundary_trials':len(boundary),'datasets':dict(collections.Counter(x['dataset'] for x in episodes)),'protocol_sha256':manifests[0]['protocol_sha256'],'all_pre_acquired':all(x['pre_acquired'] for x in rows),'full_overlay':{'managed_trials':len(full),'record_recoveries':sum(x['record_recovery'] for x in full),'byte_recoveries':sum(x['persisted_byte_recovery'] for x in full),'retrieval_recoveries':sum(x['retrieval_recovery_at3'] for x in full),'foil_preserved':sum(x['foil_preserved'] for x in full),'background_unchanged':sum(x['background_records_unchanged'] for x in full),'ranking_unchanged':sum(x['background_ranking_unchanged'] for x in full),'mean_gold_session_recall_at3':statistics.mean(x['gold_session_recall_after_at3'] for x in unique_utility.values()),'evidence_bearing_unique_backend_episodes':len(unique_utility)},'boundary_record_recoveries':sum(x['record_recovery'] for x in boundary),'fixture_recoverability_rate':sum(x['replay_fixture_recoverable'] for x in rows)/len(rows),'cross_backend_semantic_mismatches':mismatches,'reference_zero_failure_one_sided95_upper_per140_iid':1-0.05**(1/140),'statistical_caution':'The last bound assumes iid episodes and is not a calibrated real-world risk bound; trials are deterministic contract tests with repeated episode/event pairs.'}
    # Pairwise bootstrap over episode-level worst-event contrasts; degenerate
    # intervals are reported as finite-case robustness, not population certainty.
    rng=np.random.default_rng(20261004);contrasts=[]
    for backend in ['sqlite_wal','json_files']:
        epids=sorted({x['episode_id'] for x in per_episode})
        vals={(x['arm'],x['episode_id']):int(x['any_event_recovery']) for x in per_episode if x['backend']==backend}
        diff=np.array([vals[('full_overlay',e)]-vals[('dependency_purge',e)] for e in epids])
        samples=diff[rng.integers(0,len(diff),size=(10000,len(diff)))].mean(axis=1)
        contrasts.append({'backend':backend,'contrast':'full minus dependency worst-event','n_episodes':len(diff),'difference':float(diff.mean()),'bootstrap95_percentile':np.percentile(samples,[2.5,97.5]).tolist(),'caution':'Descriptive finite-stress-set bootstrap; all identical episode contrasts make it degenerate. Not proof of universal safety.'})
    summary['paired_contrasts']=contrasts
    (R/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    validation={'expected_trial_count':len(rows)==15680,'unique_trial_keys':len(identifiers)==len(set(identifiers)),'code_hashes_match':True,'protocol_hashes_match':True,'pre_acquisition_all':summary['all_pre_acquired'],'semantic_backend_agreement':not mismatches,'full_overlay_active_record_absence':summary['full_overlay']['record_recoveries']==0,'full_overlay_active_byte_absence':summary['full_overlay']['byte_recoveries']==0,'negative_controls_detect_failures':summary['boundary_record_recoveries']==len(boundary),'replay_fixtures_reported_as_recoverable':summary['fixture_recoverability_rate']==1,'result_scope':'Managed active artifacts; replay fixtures remain recoverable; no model behavior evaluated.'}
    (R/'validation.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2));print('VALIDATION',json.dumps(validation))

if __name__=='__main__':main()
