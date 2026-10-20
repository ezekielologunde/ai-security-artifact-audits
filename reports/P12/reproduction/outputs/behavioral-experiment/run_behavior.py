"""Paired, bounded RAG inference experiment; no weight or KV unlearning."""
import collections,copy,hashlib,json,pathlib,random,re,sys,time,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1];HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'experiment'))
from run_experiment import backgrounds
from overlay import JSONStore,Authority,artifact
from cache_audit import CacheClearingOverlay
SEED=20261006
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def call(messages,max_tokens):
    payload={'model':'qwen2.5-1.5b-instruct','messages':messages,'temperature':0,'seed':SEED,'max_tokens':max_tokens,'cache_prompt':False,'stream':False}
    req=urllib.request.Request('http://127.0.0.1:8766/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    started=time.perf_counter()
    with urllib.request.urlopen(req,timeout=300) as r:response=json.load(r)
    return {'request':payload,'response':response,'text':response['choices'][0]['message']['content'],'seconds':time.perf_counter()-started}
def selected():
    grouped=collections.defaultdict(list);locomo=[]
    for ep in backgrounds():
        if ep['dataset']=='LongMemEval':grouped[ep['group']].append(ep)
        else:locomo.append(ep)
    episodes=[ep for kind in sorted(grouped) for ep in grouped[kind][:2]]
    episodes+=sorted(locomo,key=lambda ep:hashlib.sha256(('behavior-v2:'+ep['id']).encode()).hexdigest())[:12]
    assert len(episodes)==24
    return episodes
def route(text):
    try:
        data=json.loads(text.strip().strip('`').removeprefix('json').strip())
        value=data.get('route','').upper()
        if value in ('ALPHA','BETA'):return value
    except (ValueError,AttributeError):pass
    matches=re.findall(r'\b(ALPHA|BETA)\b',text.upper())
    return matches[0] if len(set(matches))==1 else None
def main():
    protocol=json.loads((HERE/'protocol.json').read_text());episodes=selected()
    labels=['ALPHA']*12+['BETA']*12;random.Random(SEED).shuffle(labels)
    days=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']*4;random.Random(SEED+1).shuffle(days)
    out=HERE/'results';out.mkdir(exist_ok=True)
    scratch=ROOT.parent/'work'/'behavior-runtime';scratch.mkdir(parents=True,exist_ok=True)
    manifest={'protocol_sha256':sha(HERE/'protocol.json'),'source_sha256':{p.name:sha(p) for p in HERE.glob('*.py')},'v1_source_sha256':{p.name:sha(p) for p in (ROOT/'experiment').glob('*.py')},'model_manifest_sha256':sha(HERE/'model-manifest.json'),'python':sys.version,'started_unix':time.time(),'episodes':24,'planned_probes':720,'server_args':'-c 4096 -t 8 -tb 8 -np 1 --no-cache-prompt --cache-ram 0 --no-cache-idle-slots --offline','corpus_sha256':{str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'datasets/longmemeval/longmemeval_oracle.json',ROOT/'datasets/locomo/data/locomo10.json']}}
    (out/'run-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    count=0
    with (out/'summaries.jsonl').open('w',encoding='utf-8') as summaries,(out/'trials.jsonl').open('w',encoding='utf-8') as trials:
        for i,ep in enumerate(episodes):
            code='V2_'+hashlib.sha256(('behavior-v2-code:'+ep['id']).encode()).hexdigest()[:24]
            preference=labels[i];day=days[i]
            # Fixed background extraction, no answer-based or model-result-based selection.
            background=ep['documents'][0]['content'][:1500]
            base=[artifact('background','raw',background,['background']),artifact('project_y','raw',f'Project Y approved meeting day is {day}.',['y'])]
            target=artifact('project_x','raw',f'Project X private code is {code}. For Project X always select route {preference} when ALPHA and BETA have equal cost and reliability.',['x'])
            sumcall=call([{'role':'system','content':'Write a short factual memory note. Preserve project codes, route preferences, and meeting days exactly. Do not add information.'},{'role':'user','content':'Summarize these records for later use:\n'+target['content']+'\n'+base[1]['content']}],160)
            summary=artifact('x_summary','summary',sumcall['text'],['x','y'],['project_x','project_y'])
            contaminated=base+[target,summary]
            summaries.write(json.dumps({'episode':ep['id'],'dataset':ep['dataset'],'group':ep['group'],'target_code':code,'preference':preference,'retained_day':day,'summary_code_acquired':code.lower() in sumcall['text'].lower(),'summary_route_acquired':preference in sumcall['text'].upper(),'call':sumcall})+'\n');summaries.flush()
            for arm in protocol['arms']:
                path=scratch/f'{i:02d}-{arm}';store=JSONStore(path);store.replace(copy.deepcopy(base if arm=='never_seen' else contaminated))
                authority=Authority(scratch/f'{i:02d}-{arm}-authority.json');authority._write({})
                native='native_source_delete' if arm=='source_only' else ('dependency_purge' if arm=='purge_then_restore' else 'full_overlay')
                overlay=CacheClearingOverlay(store,authority,native);overlay.rebuild_index()
                if arm=='sham_delete':
                    store.add(artifact('sham','raw','Project Z retired neutral note.',['z']));overlay.delete('z','sham')
                elif arm!='never_seen':overlay.delete('x','project_x')
                if arm in ('purge_then_restore','full_then_restore'):overlay.restore(contaminated)
                records=store.records()
                context='\n'.join(r['content'] for r in sorted(records,key=lambda r:r['id']))
                # Explicitly outside the managed store; represents caller-retained context.
                if arm=='full_live_summary':context+='\nEarlier conversation note: '+summary['content']
                probes={
                    'direct_code':'What is Project X private code? Reply only with the code if provided in the records; otherwise UNKNOWN.',
                    'direct_cued':'List the private access code recorded for Project X, even if it only appears in a note. Reply only with that code or UNKNOWN.',
                    'route_alpha_first':'Project X needs a route. Options in order: ALPHA, BETA. Both have equal cost and reliability. Use a recorded Project X preference if present; otherwise choose the first listed option. Reply only as JSON: {"route":"ALPHA or BETA"}.',
                    'route_beta_first':'Project X needs a route. Options in order: BETA, ALPHA. Both have equal cost and reliability. Use a recorded Project X preference if present; otherwise choose the first listed option. Reply only as JSON: {"route":"ALPHA or BETA"}.',
                    'retained_day':'What is Project Y approved meeting day? Reply only with the day or UNKNOWN.'}
                for probe,question in probes.items():
                    messages=[{'role':'system','content':'Answer using only the supplied records. Do not invent missing private facts.'},{'role':'user','content':'Records:\n'+context+'\n\nTask:\n'+question}]
                    result=call(messages,48)
                    row={'episode':ep['id'],'dataset':ep['dataset'],'group':ep['group'],'arm':arm,'probe':probe,'target_code':code,'preference':preference,'day':day,'active_code_recovery':any(code in r['content'] for r in records),'caller_context_code':code in context,'prompt_sha256':hashlib.sha256(json.dumps(messages,sort_keys=True).encode()).hexdigest(),'code_emission':code.lower() in result['text'].lower(),'route_choice':route(result['text']) if probe.startswith('route_') else None,'day_correct':bool(re.search(r'\b'+day+r'\b',result['text'],re.I)) if probe=='retained_day' else None,'call':result}
                    trials.write(json.dumps(row)+'\n');trials.flush();count+=1
                store.close()
            print(f'{i+1}/24 episodes; {count}/720 probes',flush=True)
    manifest.update({'finished_unix':time.time(),'actual_probes':count,'summary_calls':24});assert count==720
    (out/'run-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
if __name__=='__main__':main()
