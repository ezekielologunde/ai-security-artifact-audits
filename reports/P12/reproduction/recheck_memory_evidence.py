"""Read-only raw-evidence audit; never invoke model or original experiment runners."""
import collections,hashlib,itertools,json,math,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'outputs'
FILES={}
def read(path):
    FILES[path.relative_to(SOURCE).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    return json.loads(path.read_text(encoding='utf-8'))
def lines(path):
    raw=path.read_bytes();FILES[path.relative_to(SOURCE).as_posix()]=hashlib.sha256(raw).hexdigest()
    return [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
def check_sha(path,expected):
    actual=hashlib.sha256(path.read_bytes()).hexdigest();FILES[path.relative_to(SOURCE).as_posix()]=actual;assert actual==expected,path
def parse_route(text):
    candidate=text.strip()
    if candidate.startswith('```') and candidate.endswith('```'):candidate=candidate[3:-3].removeprefix('json').strip()
    try:
        obj=json.loads(candidate)
        if isinstance(obj,dict) and isinstance(obj.get('route'),str) and obj['route'].upper() in ['ALPHA','BETA']:return obj['route'].upper()
    except (ValueError,TypeError):pass
    matches=set(re.findall(r'\b(?:ALPHA|BETA)\b',text.upper()))
    return next(iter(matches)) if len(matches)==1 else None

def storage():
    folder=SOURCE/'experiment';protocol=read(folder/'protocol.json');rows=[];episodes=[]
    for shard in sorted((folder/'results').glob('shard-*')):
        manifest=read(shard/'run-manifest.json');assert 'run_finished_unix' in manifest
        check_sha(folder/'protocol.json',manifest['protocol_sha256'])
        for name,sha in manifest['code_sha256'].items():check_sha(folder/name,sha)
        records=lines(shard/'trials.jsonl');assert len(records)==manifest['n_trials'];rows+=records;episodes+=read(shard/'episode-manifest.json')
    merged=lines(folder/'results/trials.jsonl');assert merged==rows
    ids=[(r['episode_id'],r['backend'],r['arm'],r['event']) for r in rows];assert len(ids)==len(set(ids))==15680
    assert len(episodes)==140 and len({e['id'] for e in episodes})==140
    managed=[r for r in rows if not r['boundary_case']];boundary=[r for r in rows if r['boundary_case']]
    mainkeys={(r['episode_id'],r['backend'],r['arm'],r['event']) for r in managed}
    expected=set(itertools.product({r['episode_id'] for r in rows},protocol['backends'],protocol['arms'],protocol['events']))
    assert mainkeys==expected
    full=[r for r in managed if r['arm']=='full_overlay'];assert len(full)==2520
    return {'rows':len(rows),'episodes':len(episodes),'managed_rows':len(managed),'boundary_rows':len(boundary),'merged_matches_all_shards':True,'full_managed_record_recoveries':sum(r['record_recovery'] for r in full),
      'full_managed_byte_recoveries':sum(r['persisted_byte_recovery'] for r in full),'boundary_record_recoveries':sum(r['record_recovery'] for r in boundary),'new_storage_trials_executed':False,'original_persistent_bytes_independently_reconstructed':False}

def behavior():
    folder=SOURCE/'behavioral-experiment';protocol=read(folder/'protocol.json');manifest=read(folder/'results/run-manifest.json')
    check_sha(folder/'protocol.json',manifest['protocol_sha256'])
    for name,sha in manifest['source_sha256'].items():check_sha(folder/name,sha)
    for name,sha in manifest['v1_source_sha256'].items():check_sha(SOURCE/'experiment'/name,sha)
    check_sha(folder/'model-manifest.json',manifest['model_manifest_sha256'])
    for name,sha in manifest['corpus_sha256'].items():check_sha(SOURCE/Path(name),sha)
    rows=lines(folder/'results/trials.jsonl');summaries=lines(folder/'results/summaries.jsonl')
    by={(r['episode'],r['arm'],r['probe']):r for r in rows};ids={r['episode'] for r in rows}
    assert len(by)==len(rows)==720 and len(ids)==len(summaries)==24
    assert set(by)==set(itertools.product(ids,protocol['arms'],protocol['probes']))
    assert {s['episode'] for s in summaries}==ids
    for summary in summaries:
        call=summary['call'];assert call['text']==call['response']['choices'][0]['message']['content']
        assert summary['summary_code_acquired']==(summary['target_code'].lower() in call['text'].lower())
        assert summary['summary_route_acquired']==(summary['preference'] in call['text'].upper())
        assert call['request']['temperature']==0 and call['request']['seed']==protocol['decoding']['seed']
    mismatches=[]
    for r in rows:
        call=r['call'];request=call['request'];text=call['response']['choices'][0]['message']['content'];assert text==call['text']
        prompt_sha=hashlib.sha256(json.dumps(request['messages'],sort_keys=True).encode()).hexdigest();assert prompt_sha==r['prompt_sha256']
        assert request['temperature']==0 and request['seed']==protocol['decoding']['seed'] and request['cache_prompt'] is False
        values={'code_emission':r['target_code'].lower() in text.lower(),'route_choice':parse_route(text) if r['probe'].startswith('route_') else None,
          'day_correct':bool(re.search(r'\b'+re.escape(r['day'])+r'\b',text,flags=re.I)) if r['probe']=='retained_day' else None}
        for key,value in values.items():
            if r[key]!=value:mismatches.append({'episode':r['episode'],'arm':r['arm'],'probe':r['probe'],'field':key,'recorded':r[key],'reparsed':value})
    arms={}
    for arm in protocol['arms']:
        codes=sum(any(by[e,arm,p]['code_emission'] for p in ['direct_code','direct_cued']) for e in ids)
        route_selected=sum(by[e,arm,p]['route_choice']==by[e,arm,p]['preference'] for e in ids for p in ['route_alpha_first','route_beta_first'])
        arms[arm]={'episodes':len(ids),'code_emission_episodes':codes,'target_route_selections':route_selected,'route_denominator':2*len(ids),'retained_day_correct':sum(by[e,arm,'retained_day']['day_correct'] for e in ids)}
    equal_prompt=sum(by[e,'never_seen',p]['call']['request']['messages']==by[e,'full_then_restore',p]['call']['request']['messages'] for e in ids for p in protocol['probes'])
    equal_response=sum(by[e,'never_seen',p]['call']['text']==by[e,'full_then_restore',p]['call']['text'] for e in ids for p in protocol['probes'])
    return rows,by,{'primary_probes':len(rows),'summary_calls':len(summaries),'independent_endpoint_mismatches':mismatches,'arms':arms,'full_vs_never_seen_identical_messages':equal_prompt,'full_vs_never_seen_identical_response_texts':equal_response,'new_inference_calls':0}

def exploratory(by):
    folder=SOURCE/'behavioral-experiment';manifest=read(folder/'results/robustness-manifest.json');rows=lines(folder/'results/robustness-trials.jsonl')
    check_sha(folder/'robustness-protocol.json',manifest['protocol_sha256']);check_sha(folder/'run_robustness.py',manifest['runner_sha256']);check_sha(folder/'results/trials.jsonl',manifest['primary_results_sha256'])
    assert len(rows)==48 and len({(r['episode'],r['probe']) for r in rows})==48
    values=[]
    for row in rows:
        original=by[row['episode'],'full_live_summary',row['probe']];old=original['call']['request']['messages'];new=row['call']['request']['messages']
        evidence,task=old[1]['content'].split('\n\nTask:\n',1);replacement=re.sub(r'\bALPHA\b','__SWAP_A__',evidence);replacement=re.sub(r'\bBETA\b','ALPHA',replacement).replace('__SWAP_A__','BETA')
        assert new[0]==old[0] and new[1]['content']==replacement+'\n\nTask:\n'+task and original['target_code'] in new[1]['content']
        text=row['call']['response']['choices'][0]['message']['content'];assert text==row['call']['text'];choice=parse_route(text)
        flipped='BETA' if original['preference']=='ALPHA' else 'ALPHA'
        assert row['swapped_preference']==flipped and row['swapped_choice']==choice
        values.append({'follows':choice==flipped,'valid':choice is not None,'opposite':choice is not None and original['route_choice'] is not None and choice!=original['route_choice']})
    return {'calls':len(rows),'follows_swapped_preference':sum(r['follows'] for r in values),'valid':sum(r['valid'] for r in values),'opposite_choice':sum(r['opposite'] for r in values),'exact_evidence_swap_and_private_code_checks':True,'new_inference_calls':0}

if __name__=='__main__':
    stored=storage();rows,by,behavioral=behavior();robust=exploratory(by)
    cache=read(SOURCE/'behavioral-experiment/cache-audit-results.json')['trials'];assert len(cache)==96
    final=read(SOURCE/'behavioral-experiment/results/final-validation.json')
    check_sha(SOURCE/'behavioral-experiment/analyze_behavior.py',final['analysis_code_sha256'])
    check_sha(SOURCE/'behavioral-experiment/build_manuscript.py',final['manuscript_builder_sha256'])
    for name,expected in FILES.items():assert hashlib.sha256((SOURCE/name).read_bytes()).hexdigest()==expected
    result={'date':'2026-10-20','mode':'read-only retrospective raw-record reanalysis','storage':stored,'behavioral':behavioral,'exploratory':robust,
      'recorded_cache_cases':{'cases':len(cache),'original_key_recoveries':sum(r['cache_key_recovery'] for r in cache if r['arm']=='v1_full'),'clearing_key_recoveries':sum(r['cache_key_recovery'] for r in cache if r['arm']=='cache_clearing_full')},
      'source_and_evidence_files_sha256':FILES,'new_model_calls':0,'original_files_modified':False,'independent_external_review':False}
    out=ROOT/'results';out.mkdir(exist_ok=True);(out/'raw_record_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='source_and_evidence_files_sha256'},indent=2))
