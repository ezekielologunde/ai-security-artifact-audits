import hashlib,json,pathlib,re,time
from run_behavior import call,route
HERE=pathlib.Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    out=HERE/'results'
    primary=[json.loads(x) for x in (out/'trials.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(primary)==720
    original=[r for r in primary if r['arm']=='full_live_summary' and r['probe'].startswith('route_')]
    assert len(original)==48
    manifest={'protocol_sha256':sha(HERE/'robustness-protocol.json'),'runner_sha256':sha(pathlib.Path(__file__)),'primary_results_sha256':sha(out/'trials.jsonl'),'started_unix':time.time(),'status':'post-pilot exploratory robustness check'}
    results=[]
    with (out/'robustness-trials.jsonl').open('w',encoding='utf-8') as f:
        for i,row in enumerate(original):
            messages=json.loads(json.dumps(row['call']['request']['messages']))
            evidence,task=messages[1]['content'].split('\n\nTask:\n',1)
            evidence=re.sub(r'\b(ALPHA|BETA)\b',lambda m:'BETA' if m[0]=='ALPHA' else 'ALPHA',evidence)
            messages[1]['content']=evidence+'\n\nTask:\n'+task
            response=call(messages,48);choice=route(response['text'])
            flipped='BETA' if row['preference']=='ALPHA' else 'ALPHA'
            old_tokens=row['call']['response']['usage']['prompt_tokens'];new_tokens=response['response']['usage']['prompt_tokens']
            result={'episode':row['episode'],'probe':row['probe'],'original_preference':row['preference'],'swapped_preference':flipped,'original_choice':row['route_choice'],'swapped_choice':choice,'follows_swapped_preference':choice==flipped,'opposite_choice':row['route_choice'] is not None and choice is not None and choice!=row['route_choice'],'valid':choice is not None,'prompt_tokens_difference':new_tokens-old_tokens,'call':response}
            results.append(result);f.write(json.dumps(result)+'\n');f.flush()
            if (i+1)%8==0:print(f'{i+1}/48 robustness probes',flush=True)
    manifest.update({'finished_unix':time.time(),'calls':48});(out/'robustness-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    summary={'status':'exploratory, designed after early primary results','calls':48,'episodes':24,'follows_swapped_preference_n':sum(r['follows_swapped_preference'] for r in results),'opposite_choice_n':sum(r['opposite_choice'] for r in results),'valid_n':sum(r['valid'] for r in results),'same_prompt_token_count_n':sum(r['prompt_tokens_difference']==0 for r in results),'prompt_tokens_difference_range':[min(r['prompt_tokens_difference'] for r in results),max(r['prompt_tokens_difference'] for r in results)],'primary_code_unchanged':all(r['call']['request']['messages'][1]['content'].split('\n\nTask:\n')[1]==o['call']['request']['messages'][1]['content'].split('\n\nTask:\n')[1] for r,o in zip(results,original)),'no_episode_excluded':True}
    (out/'robustness-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
