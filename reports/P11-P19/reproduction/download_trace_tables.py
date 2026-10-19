"""Download source analysis tables and method code as inert material, then profile columns."""
import csv,json,urllib.parse
from pathlib import Path
import source_io as io
ROOT=Path(__file__).resolve().parent;io.ROOT=ROOT
if __name__=='__main__':
    source=json.loads((ROOT/'trace-artifact/data/source_manifest.json').read_text())[0]
    selected=[f for f in source['files'] if f['path'].endswith('.csv') or f['path'].startswith(('scripts/paper_stats','reference/'))]
    receipts=[];profile=[]
    for f in selected:
        if f.get('size',0)>2_000_000:continue
        name=f['path'];path=ROOT/'data/trace-tables'/name
        receipts.append(io.fetch(f'https://raw.githubusercontent.com/{source["repository"]}/{source["revision"]}/{urllib.parse.quote(name,safe="/")}',path))
        if path.suffix=='.csv':
            with path.open(encoding='utf-8',newline='') as handle:
                reader=csv.DictReader(handle);rows=list(reader)
                profile.append({'file':name,'rows':len(rows),'columns':reader.fieldnames,'unique_tasks':len({r['task_id'] for r in rows}) if rows and 'task_id' in rows[0] else None})
    (ROOT/'data/trace_tables_manifest.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
    (ROOT/'data/trace_table_profiles.json').write_text(json.dumps(profile,indent=2),encoding='utf-8')
    print(json.dumps(profile,indent=2))
