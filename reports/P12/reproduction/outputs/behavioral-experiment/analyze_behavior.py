import collections,csv,hashlib,json,pathlib,random,statistics
HERE=pathlib.Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    out=HERE/'results';rows=[json.loads(s) for s in (out/'trials.jsonl').read_text(encoding='utf-8').splitlines()]
    summaries=[json.loads(s) for s in (out/'summaries.jsonl').read_text(encoding='utf-8').splitlines()]
    protocol=json.loads((HERE/'protocol.json').read_text());manifest=json.loads((out/'run-manifest.json').read_text())
    ids=sorted({r['episode'] for r in rows});by={(r['episode'],r['arm'],r['probe']):r for r in rows}
    assert len(rows)==len(by)==720 and len(ids)==len(summaries)==24
    assert manifest['protocol_sha256']==sha(HERE/'protocol.json')
    for name,h in manifest['source_sha256'].items():assert sha(HERE/name)==h
    for e in ids:
        for a in protocol['arms']:
            assert all((e,a,p) in by for p in protocol['probes'])
    cells={};episode=[]
    for arm in protocol['arms']:
        values=[]
        for e in ids:
            choices=[by[e,arm,p]['route_choice'] for p in ['route_alpha_first','route_beta_first']]
            pref=by[e,arm,'direct_code']['preference']
            item={'episode':e,'arm':arm,'target_route_rate':sum(c==pref for c in choices)/2,'valid_route_rate':sum(c is not None for c in choices)/2,'code_any':any(by[e,arm,p]['code_emission'] for p in ['direct_code','direct_cued']),'day_correct':by[e,arm,'retained_day']['day_correct'],'active_code_recovery':by[e,arm,'direct_code']['active_code_recovery'],'caller_context_code':by[e,arm,'direct_code']['caller_context_code']}
            episode.append(item);values.append(item)
        cells[arm]={'n_episodes':24,'code_any_n':sum(v['code_any'] for v in values),'target_route_rate':statistics.mean(v['target_route_rate'] for v in values),'valid_route_rate':statistics.mean(v['valid_route_rate'] for v in values),'day_correct_n':sum(v['day_correct'] for v in values),'active_code_n':sum(v['active_code_recovery'] for v in values),'caller_context_code_n':sum(v['caller_context_code'] for v in values)}
    index={(v['episode'],v['arm']):v for v in episode};contrasts={}
    for arm in protocol['arms']:
        diffs=[index[e,arm]['target_route_rate']-index[e,'never_seen']['target_route_rate'] for e in ids]
        rng=random.Random(20261006);draws=sorted(sum(rng.choice(diffs) for _ in diffs)/24 for _ in range(10000))
        contrasts[arm]={'paired_difference':statistics.mean(diffs),'episode_bootstrap_95_percentile':[draws[249],draws[9749]],'interpretation':'descriptive conditional contrast; failure to reject is not equivalence'}
    equal_prompts=sum(by[e,'never_seen',p]['prompt_sha256']==by[e,'full_then_restore',p]['prompt_sha256'] for e in ids for p in protocol['probes'])
    equal_text=sum(by[e,'never_seen',p]['call']['text']==by[e,'full_then_restore',p]['call']['text'] for e in ids for p in protocol['probes'])
    summary={'episodes':24,'summary_calls':24,'probe_calls':720,'total_inferences':744,'model':'Qwen2.5-1.5B-Instruct Q4_K_M','temperature':0,'summary_code_acquired_n':sum(s['summary_code_acquired'] for s in summaries),'summary_route_label_present_n':sum(s['summary_route_acquired'] for s in summaries),'arms':cells,'route_contrasts_vs_never_seen':contrasts,'full_vs_never_seen':{'identical_prompt_n':equal_prompts,'identical_response_n':equal_text,'n':120,'construction_check_only':True},'max_prompt_tokens':max(r['call']['response']['usage']['prompt_tokens'] for r in rows),'truncated_response_n':sum(r['call']['response']['choices'][0]['finish_reason']=='length' for r in rows),'cached_prompt_tokens_n':sum(r['call']['response']['usage']['prompt_tokens_details']['cached_tokens'] for r in rows),'elapsed_seconds':manifest['finished_unix']-manifest['started_unix']}
    assert equal_prompts==120
    assert not any(by[e,'full_then_restore','direct_code']['active_code_recovery'] for e in ids)
    with (out/'arm-results.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['arm']+list(next(iter(cells.values()))));w.writeheader()
        for a,c in cells.items():w.writerow({'arm':a,**c})
    with (out/'episode-results.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(episode[0]));w.writeheader();w.writerows(episode)
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    validation={'status':'pass','complete_unique_design':True,'source_hashes_match_frozen_manifest':True,'unchanged_protocol':True,'no_excluded_episodes':True,'all_prompts_and_responses_recorded':True,'full_prompt_matches_clean_world':equal_prompts==120,'not_a_universal_erasure_claim':True,'result_sha256':sha(out/'trials.jsonl')}
    (out/'validation.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
