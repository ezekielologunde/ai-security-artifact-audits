"""Run the frozen v1 reference-store experiment with real persistent storage."""
import argparse, collections, copy, hashlib, json, pathlib, platform, sys, time
from overlay import SQLiteStore,JSONStore,Authority,Overlay,artifact,rank,vector,audit_bytes

ROOT=pathlib.Path(__file__).resolve().parents[1]
CODE=pathlib.Path(__file__).resolve().parent
def digest(text):return hashlib.sha256(text.encode()).hexdigest()
def backgrounds():
    data=json.loads((ROOT/'datasets/longmemeval/longmemeval_oracle.json').read_text(encoding='utf-8'))
    grouped=collections.defaultdict(list)
    for q in data:grouped[q['question_type']].append(q)
    chosen=[]
    for kind,rows in sorted(grouped.items()):
        for row in sorted(rows,key=lambda x:digest('study-v1:'+x['question_id']))[:20]:
            docs=[];gold=[]
            for sid,session in zip(row['haystack_session_ids'],row['haystack_sessions']):
                rid='bg_'+digest(row['question_id']+':'+sid)[:20]
                text='\n'.join(t['role']+': '+t['content'] for t in session)
                docs.append(artifact(rid,'raw',text,['background']))
                if sid in row['answer_session_ids']:gold.append(rid)
            chosen.append({'id':'lme_'+row['question_id'],'dataset':'LongMemEval','group':kind,'question':row['question'],'documents':docs,'gold_ids':gold})
    locomo=json.loads((ROOT/'datasets/locomo/data/locomo10.json').read_text(encoding='utf-8'))
    for i,conv in enumerate(locomo):
        eligible=[(j,q) for j,q in enumerate(conv['qa']) if q.get('evidence') and q.get('answer')]
        for j,q in sorted(eligible,key=lambda jq:digest(f'locomo-study-v1:{i}:{jq[0]}'))[:2]:
            docs=[];gold=[]
            for sk,session in conv['conversation'].items():
                if isinstance(session,list) and sk.startswith('session_'):
                    rid='bg_'+digest(f'locomo:{i}:{j}:{sk}')[:20]
                    text='\n'.join(t.get('speaker','')+': '+t.get('text','') for t in session)
                    docs.append(artifact(rid,'raw',text,['background']))
                    if any(t.get('dia_id') in q['evidence'] for t in session):gold.append(rid)
            chosen.append({'id':f'locomo_{i}_{j}','dataset':'LoCoMo','group':f'conversation_{i}','question':q['question'],'documents':docs,'gold_ids':gold})
    return chosen

def retrieval(index,query,k=3):
    v=vector(query)
    scored=[(sum(a*b for a,b in zip(v,row['vector'])),row['id'],row['content']) for row in index]
    return sorted(scored,key=lambda x:(-x[0],x[1]))[:k]

def trial(ep,store_cls,arm,event,work):
    trialpath=work/store_cls.name
    store=store_cls(trialpath);store.replace([]);store.compact()
    authority=Authority(work/(store_cls.name+'_authority.json'));authority._write({})
    overlay=Overlay(store,authority,arm)
    scope='project_'+digest(ep['id'])[:20];source_id='source_'+scope
    canary='CANARY_'+digest('controlled-source-v1:'+ep['id'])[:24]
    preference='route-A' if int(digest(ep['id']),16)%2 else 'route-B'
    target=artifact(source_id,'raw',f'Project X private test code is {canary}. Project X prefers {preference}.',[scope])
    target_copies=[target]+[artifact(layer+'_'+scope,layer,f'{layer} of Project X: private test code {canary}; Project X prefers {preference}.',[scope],[source_id]) for layer in ['summary','cache','checkpoint']]
    foil=artifact('unrelated_control','raw','Project Y approved meeting day is Thursday.',['project_y'])
    base=copy.deepcopy(ep['documents'])+[foil]
    initial=base+target_copies
    store.replace(initial);overlay.rebuild_index();store.compact()
    fixture={'records':copy.deepcopy(initial),'queued':copy.deepcopy(target),'original':copy.deepcopy(target),'peer':copy.deepcopy(target)}
    replay_path=work/'fault_replay_fixture.json';replay_path.write_text(json.dumps(fixture),encoding='utf-8')
    baseline_rank=rank(base,ep['question'],3)
    pre_acquired=any(canary in r['content'] for r in store.records()) and any(canary in x[2] for x in retrieval(overlay.index(),'Project X private test code',3))
    t=time.perf_counter();overlay.delete(scope,source_id);delete_ms=(time.perf_counter()-t)*1000
    immediate_marker=any(canary in r['content'] for r in store.records())
    accepted=None
    t=time.perf_counter()
    if event=='restart':overlay.restart()
    elif event=='index_rebuild':overlay.rebuild_index()
    elif event=='source_reprocessing':
        new=copy.deepcopy(fixture['original']);new['id']='reprocessed_'+scope;accepted=overlay.commit(new)
    elif event=='snapshot_restore':overlay.restore(fixture['records'])
    elif event=='delayed_commit':accepted=overlay.commit(fixture['queued'])
    elif event=='peer_sync':
        new=copy.deepcopy(fixture['peer']);new['id']='peer_'+scope;accepted=overlay.commit(new)
    elif event=='restore_then_commit':overlay.restore(fixture['records']);accepted=overlay.commit(fixture['queued'])
    elif event=='commit_then_restart':accepted=overlay.commit(fixture['queued']);overlay.restart()
    elif event=='authority_rollback':authority._write({});overlay.restore(fixture['records'])
    elif event=='adapter_bypass':accepted=overlay.commit(fixture['queued'],bypass=True)
    elif event!='immediate':raise ValueError(event)
    event_ms=(time.perf_counter()-t)*1000
    records=store.records();index=overlay.index()
    layers={layer:any(canary in r['content'] for r in records if r['layer']==layer) for layer in ['raw','summary','cache','checkpoint']}
    layers['index_payload']=any(canary in x['content'] for x in index)
    raw_files=audit_bytes(store,canary)
    after_rank=rank(records,ep['question'],3)
    retrieval_marker=any(canary in x[2] for x in retrieval(index,'Project X private test code',3))
    gold=set(ep['gold_ids'])
    gold_before=len(gold.intersection(baseline_rank))/len(gold) if gold else None
    gold_after=len(gold.intersection(after_rank))/len(gold) if gold else None
    result={'episode_id':ep['id'],'dataset':ep['dataset'],'group':ep['group'],'backend':store_cls.name,'arm':arm,'event':event,'boundary_case':event in ('authority_rollback','adapter_bypass'),'pre_acquired':pre_acquired,'immediate_record_residue':immediate_marker,'record_recovery':any(layers.values()),'persisted_byte_recovery':bool(raw_files),'retrieval_recovery_at3':retrieval_marker,'layers':layers,'marker_files':raw_files,'preference_literal_residue':any(f'Project X prefers {preference}' in r['content'] for r in records),'foil_preserved':any(r['id']=='unrelated_control' and 'Thursday' in r['content'] for r in records),'background_records_unchanged':all(next((x for x in records if x['id']==r['id']),None)==r for r in ep['documents']),'background_ranking_unchanged':baseline_rank==after_rank,'gold_session_recall_before_at3':gold_before,'gold_session_recall_after_at3':gold_after,'delete_ms':delete_ms,'event_ms':event_ms,'active_bytes':sum(p.stat().st_size for p in store.files()),'replay_fixture_recoverable':canary.encode() in replay_path.read_bytes(),'write_accepted':accepted}
    store.close();return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=pathlib.Path,default=ROOT/'experiment'/'results');parser.add_argument('--scratch',type=pathlib.Path,default=ROOT.parents[0]/'work'/'experiment-runtime');parser.add_argument('--limit',type=int,default=None);parser.add_argument('--shard-index',type=int,default=0);parser.add_argument('--shards',type=int,default=1);args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True);args.scratch.mkdir(parents=True,exist_ok=True)
    protocol=json.loads((CODE/'protocol.json').read_text());episodes=backgrounds()
    if args.limit:episodes=episodes[:args.limit]
    episodes=[ep for i,ep in enumerate(episodes) if i%args.shards==args.shard_index]
    (args.out/'episode-manifest.json').write_text(json.dumps([{k:v for k,v in e.items() if k not in ('documents','question')} for e in episodes],indent=2),encoding='utf-8')
    metadata={'protocol_sha256':hashlib.sha256((CODE/'protocol.json').read_bytes()).hexdigest(),'code_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in CODE.glob('*.py')},'python':sys.version,'platform':platform.platform(),'sqlite_version':__import__('sqlite3').sqlite_version,'clock':time.get_clock_info('perf_counter')._asdict() if hasattr(time.get_clock_info('perf_counter'),'_asdict') else str(time.get_clock_info('perf_counter')),'data_sha256':{name:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for name,path in [('longmemeval','datasets/longmemeval/longmemeval_oracle.json'),('locomo','datasets/locomo/data/locomo10.json')]},'n_episodes':len(episodes),'run_started_unix':time.time(),'model_inference':False}
    (args.out/'run-manifest.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    count=0;t=time.perf_counter()
    with (args.out/'trials.jsonl').open('w',encoding='utf-8') as f:
        for n,ep in enumerate(episodes):
            for backend in [SQLiteStore,JSONStore]:
                for arm in protocol['arms']:
                    for event in protocol['events']:
                        row=trial(ep,backend,arm,event,args.scratch);f.write(json.dumps(row)+'\n');count+=1
                for event in protocol['boundary_events']:
                    row=trial(ep,backend,'full_overlay',event,args.scratch);f.write(json.dumps(row)+'\n');count+=1
            f.flush()
            if n%10==0:print(f'{n+1}/{len(episodes)} episodes; {count} trials; {time.perf_counter()-t:.1f}s',flush=True)
    metadata['n_trials']=count;metadata['elapsed_seconds']=time.perf_counter()-t;metadata['run_finished_unix']=time.time()
    (args.out/'run-manifest.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(json.dumps({'episodes':len(episodes),'trials':count,'elapsed_seconds':metadata['elapsed_seconds']}),flush=True)

if __name__=='__main__':main()
