"""Pin the author contamination-analysis artifact without running agent workflows."""
import json
from pathlib import Path
import source_io as io
ROOT=Path(__file__).resolve().parent;io.ROOT=ROOT/'trace-artifact'
io.REPOS=['anna-mazhar/trace-level-contamination-mas']
if __name__=='__main__':
    io.main()
    row=json.loads((io.ROOT/'data/source_manifest.json').read_text())[0]
    candidates=[f for f in row['files'] if f['path'].endswith(('.csv','.json','.jsonl','.parquet','.md','.py'))]
    (ROOT/'data/trace_artifact_inventory.json').write_text(json.dumps({'revision':row['revision'],'files':candidates},indent=2),encoding='utf-8')
    print('Candidate files',len(candidates),'total bytes',sum(f.get('size',0) for f in candidates))
    for f in candidates[:65]:print(f['path'],f.get('size'))
