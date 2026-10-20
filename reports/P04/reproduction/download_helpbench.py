"""Acquire author-linked compact HelpBench files; no Reddit collection or model calls."""
import json
from pathlib import Path
import source_io as io
ROOT=Path(__file__).resolve().parent;io.ROOT=ROOT
FILES=['README.md','LICENSE','datasets/helpbench.jsonl','datasets/helpbench_expert_rater.jsonl','scripts/autorater.py','scripts/scoring.py','tests/test_scoring.py','tests/sample_scored_rubric.json','tests/sample_rubric_minimal_criteria.json','tests/sample_rubric.json']
if __name__=='__main__':
    pinned_path=ROOT/'data/helpbench_manifest.json'
    pinned=json.loads(pinned_path.read_text()) if pinned_path.exists() else None
    expected={r['path']:r['sha256'] for r in pinned['receipts']} if pinned else None
    records=[];errors=[]
    for name in FILES:
        try:
            records.append(io.fetch('https://anonymous.4open.science/api/repo/helpseeking-3829/file/'+name,ROOT/'data/helpbench/files'/name,20_000_000))
        except Exception as exc:errors.append({'file':name,'error':str(exc)})
    result={'author_link':'https://arxiv.org/html/2606.24819v1','repository':'https://anonymous.4open.science/r/helpseeking-3829/',
      'source_full_commit_not_exposed':True,'content_pinned_by_SHA256':True,'displayed_anonymization_date':'2026-05-06','snapshot_publication_date_not_recorded':True,
      'receipts':records,'errors':errors,'large_Reddit_link_collection_downloaded':False,'source_executed':False}
    actual={r['path']:r['sha256'] for r in records}
    mismatches=[name for name in sorted(set(expected or {})|set(actual)) if expected is not None and expected.get(name)!=actual.get(name)]
    result['pinned_manifest_preserved']=pinned is not None
    result['pinned_content_mismatches']=mismatches
    if pinned is None and not errors:pinned_path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    else:(ROOT/'data/helpbench_acquisition_receipts.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'files':len(records),'bytes':sum(r['bytes'] for r in records),'errors':errors,'pinned_content_mismatches':mismatches,'pinned_manifest_preserved':pinned is not None},indent=2))
    if errors or mismatches:raise SystemExit('Acquisition differs from the pinned artifact; expected manifest was not overwritten.')
