"""Explicitly post-hoc namespace repair; primary frozen results stay unchanged."""
import copy,hashlib,json
from pathlib import Path
from lexical_baseline import Matcher,metrics,server_key
ROOT=Path(__file__).resolve().parent
primary=json.loads((ROOT/'results/lexical-v2/summary.json').read_text())
output={'status':'exploratory post-hoc sensitivity, designed after primary results and unknown-case inspection',
    'rule':'Strip server:: only when its prefix normalizes to the separately supplied server identity; do not alter other tool names.',
    'calibration':'Keep each representation primary threshold unchanged; recompute only previously indeterminate scores.',
    'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'variants':{}}
for variant,record in primary['variants'].items():
    model=Matcher(variant);rows=[json.loads(x) for x in (ROOT/f'results/lexical-v2/{variant}_predictions.jsonl').read_text().splitlines()]
    amended=copy.deepcopy(rows);repairs=[]
    for r in amended:
        if r['score'] is not None:continue
        folder={1:'01_tool',2:'02_tools',3:'03_tools'}[r['tools_per_task']]
        raw=json.loads((ROOT/f'data/benchmark/data/{folder}/{r["source"]}/{r["split"]}.json').read_text())
        visible=copy.deepcopy(raw[r['row']]['input'])
        names=[]
        for name,server in zip(visible['tools'],visible['mcp_servers']):
            prefix,sep,suffix=name.partition('::')
            names.append(suffix if sep and server_key(prefix)==server_key(server) else name)
        visible['tools']=names;r['score']=model.score(visible,r['source'])
        repairs.append({'source':r['source'],'split':r['split'],'row':r['row'],'new_score':r['score']})
    test={}
    for group in record['test']:
        source,n=group.rsplit('_',1)
        selected=[r for r in amended if r['source']==source and r['split']=='test' and r['tools_per_task']==int(n)]
        test[group]=metrics(selected,record['calibrated_threshold'])
    output['variants'][variant]={'repairs':repairs,'threshold':record['calibrated_threshold'],'test':test}
(ROOT/'results/namespace_sensitivity.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
print(json.dumps({v:{'repaired_cases':len(r['repairs']),'TOUCAN_2':r['test']['TOUCAN_2']} for v,r in output['variants'].items()},indent=2))
