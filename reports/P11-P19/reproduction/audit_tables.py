"""Independently check public table coverage with stdlib; preserve unknown outcomes."""
import collections,csv,hashlib,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def read(path):
    with path.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def key(row):return row['task_id'],row['perturbation_type']
if __name__=='__main__':
    receipts=json.loads((ROOT/'data/trace_tables_manifest.json').read_text())
    for receipt in receipts:assert hashlib.sha256((ROOT/receipt['path']).read_bytes()).hexdigest()==receipt['sha256']
    result={'source_hashes_verified':len(receipts),'models':{},'independent_correctness_labels_available':False,
            'new_model_runs':0,'no_correctness_imputation':True}
    all_manifest=collections.Counter();all_tasks=set();combined_pairs=[]
    for model in ['gpt','llama','qwen']:
        folder=ROOT/'data/trace-tables/data'/('analysis_val_'+model)
        runs=read(folder/'runs_flat.csv');tokens=read(folder/'token_usage.csv')
        run_counts=collections.Counter(key(r) for r in runs);token_counts=collections.Counter(key(r) for r in tokens)
        shared=set(run_counts)&set(token_counts)
        mapping={key(r):r for r in runs}
        pairs=[(t,mapping[key(t)]) for t in tokens if key(t) in mapping and run_counts[key(t)]==1 and token_counts[key(t)]==1]
        for token,run in pairs:
            if float(token['baseline_tokens'])>0:combined_pairs.append((model,float(token['perturbed_tokens'])/float(token['baseline_tokens']),run['manifestation_type']))
        counts=collections.Counter(r['manifestation_type'] for r in runs);all_manifest.update(counts);all_tasks.update(r['task_id'] for r in runs)
        result['models'][model]={'trace_rows':len(runs),'token_rows':len(tokens),'trace_unique_keys':len(run_counts),'token_unique_keys':len(token_counts),
          'duplicate_trace_keys':[list(k) for k,v in run_counts.items() if v>1],'duplicate_token_keys':[list(k) for k,v in token_counts.items() if v>1],
          'matched_keys':len(shared),'token_only_keys':[list(k) for k in sorted(set(token_counts)-set(run_counts))],
          'trace_only_keys':[list(k) for k in sorted(set(run_counts)-set(token_counts))],'manifestation_counts':dict(counts),
          'independent_correctness_fields':sorted({k for r in runs for k in r if k in ['is_correct','baseline_correct','perturbed_correct','reference_answer']})}
    total=sum(all_manifest.values())
    result['pooled']={'trace_rows':total,'unique_task_ids':len(all_tasks),'manifestation_counts':dict(all_manifest),
        'manifestation_pct':{k:100*v/total for k,v in sorted(all_manifest.items())},'matched_positive_baseline_token_rows':len(combined_pairs),
        'median_token_multiplier_matched_only':statistics.median(p[1] for p in combined_pairs)}
    out=ROOT/'results';out.mkdir(exist_ok=True)
    (out/'table_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'verified':len(receipts),'pooled':result['pooled'],'coverage':{k:{x:v[x] for x in ['trace_rows','token_rows','matched_keys','duplicate_trace_keys','duplicate_token_keys']} for k,v in result['models'].items()}},indent=2))
