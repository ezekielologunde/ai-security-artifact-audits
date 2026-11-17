"""Measure released key overlap without assigning any correctness labels."""
from collections import Counter, defaultdict
import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def read(path):
    with path.open(encoding='utf-8',newline='') as f:
        return list(csv.DictReader(f))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tables-only',action='store_true',help='Skip current-release metadata; use only pinned acquired tables.')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    receipts=json.loads((ROOT/'data/trace_tables_manifest.json').read_text(encoding='utf-8'))
    for row in receipts:
        assert sha(ROOT/row['path'])==row['sha256']
    populations={}
    for kind,filename in [('trace','runs_flat.csv'),('token','token_usage.csv')]:
        keys=defaultdict(set)
        model_keys={}
        all_rows=[]
        for model in ['gpt','llama','qwen']:
            rows=read(ROOT/f'data/trace-tables/data/analysis_val_{model}/{filename}')
            complete=[(model,r['task_id'],r['perturbation_type']) for r in rows]
            assert len(complete)==len(set(complete))
            model_keys[model]={(r['task_id'],r['perturbation_type']) for r in rows}
            all_rows.extend(complete)
            for _,task,perturbation in complete:
                keys[(task,perturbation)].add(model)
        reduced=[(task,perturbation) for _,task,perturbation in all_rows]
        multiplicities=Counter(reduced)
        assert all(len(keys[key])==n for key,n in multiplicities.items())
        expected=sum(n*n for n in multiplicities.values())
        nested=sum(a==b for a in reduced for b in reduced)
        assert expected==nested
        populations[kind]={'released_rows':len(all_rows),'complete_unique_keys':len(set(all_rows)),
            'reduced_unique_keys':len(keys),
            'reduced_key_model_multiplicity':dict(Counter(len(models) for models in keys.values())),
            'rows_with_shared_reduced_keys':sum(n for n in multiplicities.values() if n>1),
            'pairwise_shared_reduced_keys':{f'{a}/{b}':len(model_keys[a]&model_keys[b])
                                         for a,b in itertools.combinations(model_keys,2)},
            'hypothetical_one_outcome_per_complete_key':{
                'reduced_key_join_rows':expected,'complete_key_join_rows':len(all_rows),
                'additional_rows':expected-len(all_rows),
                'assumption_is_diagnostic_not_actual_correctness_data':True},
            'key_membership':[{'task_id':key[0],'perturbation_type':key[1],'models':sorted(models)}
                              for key,models in sorted(keys.items())]}
    review=ROOT/'data/release-review-20261117'
    release_check={}
    if not args.tables_only:
        head=json.loads((review/'head.json').read_text(encoding='utf-8'))
        tree=json.loads((review/'tree.json').read_text(encoding='utf-8'))
        releases=json.loads((review/'releases.json').read_text(encoding='utf-8'))
        assert head['sha']=='a6aaf30ccdb15d774ac8bad136e52491db3e2a4a'
        assert head['commit']['tree']['sha']==tree['sha'] and not tree.get('truncated')
        release_check={'current_tree_blobs':sum(x['type']=='blob' for x in tree['tree']),
                       'github_releases_count':len(releases),
                       'retrieval_sha256':{p.name:sha(p) for p in [review/'head.json',review/'tree.json',review/'releases.json']}}
    assert all(sha(ROOT/r['path'])==r['sha256'] for r in receipts)
    result={'date':'2026-11-17','source_revision':'a6aaf30ccdb15d774ac8bad136e52491db3e2a4a','inputs_reverified':len(receipts),
            'populations':populations, 'current_release_check_repeated':not args.tables_only,
            **release_check, 'new_correctness_records_acquired':False,
            'correctness_labels_generated':0,'model_calls':0,'author_contacted':False,
            'published_outcome_effect_established':False}
    target=args.output or ROOT/'results/released_key_overlap_20261117.json'
    if args.output:
        assert not target.exists(), 'Preserve earlier replay output.'
    target.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({name:{k:v for k,v in pop.items() if k!='key_membership'}
                      for name,pop in populations.items()},indent=2))

if __name__=='__main__':
    main()
