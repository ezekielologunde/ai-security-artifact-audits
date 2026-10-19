"""Describe public schemas and split units without tuning on test predictions."""
import collections,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
summaries=[]
for p in sorted((ROOT/'data/benchmark/data').glob('*/*/*.json')):
    if p.name not in {'test.json','validation.json'}:continue
    rows=json.loads(p.read_text());tags=collections.Counter(r.get('match_tag') for r in rows)
    inputs=[r['input'] for r in rows]
    servers=sorted({s for x in inputs for s in x['mcp_servers']})
    summaries.append({'file':p.relative_to(ROOT).as_posix(),'rows':len(rows),'tags':dict(tags),
        'unique_tasks':len({x['task'] for x in inputs}),'servers':servers,
        'tool_counts':dict(collections.Counter(len(x['tools']) for x in inputs))})
(ROOT/'data/split_profile.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
print(json.dumps([{k:r[k] for k in ['file','rows','tags','unique_tasks','tool_counts']} for r in summaries],indent=2))
for p in [(ROOT/'data/benchmark/data/mcp_servers/ASTRA/paper_search.json'),next((ROOT/'data/benchmark/data/mcp_servers/TOUCAN').glob('United States Weather.json'))]:
    value=json.loads(p.read_text());print('CATALOG',p.name,json.dumps(value,ensure_ascii=True)[:2000])
