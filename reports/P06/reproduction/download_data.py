"""Acquire compact ASTRA/processed-TOUCAN splits and catalogs, no author code execution."""
import base64,hashlib,importlib.util,json,urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parent
helper=ROOT/'source_io.py'
spec=importlib.util.spec_from_file_location('source_helper',helper)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.ROOT=ROOT
manifest=json.loads((ROOT/'author_artifacts/data/source_manifest.json').read_text())
record=next(r for r in manifest if r['repository']=='outshift-open/ASTRA');sha=record['revision']
selected=[f for f in record['files'] if f['path'].endswith('.json') and (f['path'].endswith(('/test.json','/validation.json')) or f['path'].startswith('data/mcp_servers/'))]
total=sum(f.get('size',0) for f in selected)
if total>15_000_000:raise ValueError('planned compact source bound exceeded')
receipts=[];errors=[]
for f in selected:
    name=f['path'];url=f'https://raw.githubusercontent.com/outshift-open/ASTRA/{sha}/{urllib.parse.quote(name,safe="/")}'
    try:receipts.append(module.fetch(url,ROOT/'data/benchmark'/name,limit=4_000_000))
    except Exception as exc:
        # Some Unicode filenames fail on the raw-content route. Git blob identity
        # avoids filename normalization while preserving exact bytes.
        api=f'https://api.github.com/repos/outshift-open/ASTRA/git/blobs/{f["sha"]}'
        record=module.fetch(api,ROOT/'data/blob_responses'/(f['sha']+'.json'))
        obj=json.loads((ROOT/record['path']).read_text());payload=base64.b64decode(obj['content'])
        actual=hashlib.sha1(b'blob '+str(len(payload)).encode()+b'\0'+payload).hexdigest()
        assert actual==f['sha']
        path=ROOT/'data/benchmark'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(payload)
        receipt={'path':path.relative_to(ROOT).as_posix(),'url':api,'resolved_url':api,'bytes':len(payload),
                 'sha256':hashlib.sha256(payload).hexdigest(),'source_response':record['path'],
                 'transform':'base64 decode Git blob response; verified Git blob SHA-1','raw_route_error':str(exc)}
        path.with_name(path.name+'.receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
        receipts.append(receipt);print('RECOVERED BY BLOB',name,flush=True)
(ROOT/'data/benchmark_manifest.json').write_text(json.dumps({'repository':'outshift-open/ASTRA','revision':sha,
    'upstream_license':record.get('license_metadata'),'selected_bytes':total,'receipts':receipts,
    'errors':errors,'scope':'ASTRA validation/tests, processed TOUCAN tests and original tool catalogs; no model responses or real access-token traces.'},indent=2),encoding='utf-8')
print('Downloaded',len(receipts),'JSON artifacts;',total,'bytes')
for name in ['data/01_tool/ASTRA/validation.json','data/01_tool/ASTRA/test.json','data/01_tool/TOUCAN/test.json']:
    value=json.loads((ROOT/'data/benchmark'/name).read_text())
    print(name,'type',type(value).__name__,'length',len(value))
    first=value[0] if isinstance(value,list) else next(iter(value.items()))
    print('Schema example:',json.dumps(first,ensure_ascii=True)[:2000])
