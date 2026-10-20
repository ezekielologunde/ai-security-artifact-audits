"""Conditional skip-None aggregation illustration on released expert records only."""
import hashlib,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent
if __name__=='__main__':
    path=ROOT/'results/helpbench_endpoint_records.jsonl';rows=[json.loads(line) for line in path.read_text().splitlines()]
    endpoints={}
    for name in ['negative_factual','negative_delivery']:
        selected=[r for r in rows if r['endpoint']==name]
        original=[r['original']['score'] for r in selected if r['original']['score'] is not None]
        reference=[r['reference'] for r in selected if r['reference'] is not None]
        endpoints[name]={'source_numeric_denominator':len(original),'all_applicable_reference_denominator':len(reference),
          'source_skip_None_mean':statistics.mean(original),'reference_all_applicable_mean':statistics.mean(reference),
          'source_omitted_numeric_one_count':sum(r['original']['score'] is None and r['reference']==1 for r in selected)}
    out={'primary_endpoint_records_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'scope':'conditional skip-None consumer on released expert samples only','endpoints':endpoints,'authors_full_model_aggregates_reconstructed':False,'new_model_ranking':False}
    (ROOT/'results/helpbench_conditional_aggregate.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))
