"""Acquire author-linked compact HelpBench files; no Reddit collection or model calls."""
import json
from pathlib import Path
import source_io as io
ROOT=Path(__file__).resolve().parent;io.ROOT=ROOT
FILES=['README.md','LICENSE','datasets/helpbench.jsonl','datasets/helpbench_expert_rater.jsonl','scripts/autorater.py','scripts/scoring.py','tests/test_scoring.py','tests/sample_scored_rubric.json','tests/sample_rubric_minimal_criteria.json','tests/sample_rubric.json']
if __name__=='__main__':
    records=[];errors=[]
    for name in FILES:
        try:
            records.append(io.fetch('https://anonymous.4open.science/api/repo/helpseeking-3829/file/'+name,ROOT/'data/helpbench/files'/name,20_000_000))
        except Exception as exc:errors.append({'file':name,'error':str(exc)})
    result={'author_link':'https://arxiv.org/html/2606.24819v1','repository':'https://anonymous.4open.science/r/helpseeking-3829/',
      'source_full_commit_not_exposed':True,'content_pinned_by_SHA256':True,'displayed_anonymization_date':'2026-05-06','snapshot_publication_date_not_recorded':True,
      'receipts':records,'errors':errors,'large_Reddit_link_collection_downloaded':False,'source_executed':False}
    (ROOT/'data/helpbench_manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({'files':len(records),'bytes':sum(r['bytes'] for r in records),'errors':errors},indent=2))
