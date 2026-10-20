"""Fetch the pinned task ledger, then reconstruct exact reference bytes locally."""
import hashlib,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent
manifest=json.loads((ROOT/'REFERENCE_HYDRATION_MANIFEST.json').read_text())
ledger=ROOT/'datasets/upstream/agenttrap/hf_dataset/data/tasks.jsonl'
if ledger.exists():data=ledger.read_bytes()
else:
    url='https://huggingface.co/datasets/zhmzm/AgentTrap/resolve/'+manifest['task_ledger_revision']+'/data/tasks.jsonl'
    request=urllib.request.Request(url,headers={'User-Agent':'offboarding-reference-reproduction/1.0'})
    with urllib.request.urlopen(request,timeout=90) as response:data=response.read(5_000_001)
assert len(data)<=5_000_000 and hashlib.sha256(data).hexdigest()==manifest['task_ledger_sha256'],'Task ledger mismatch; no unverified bytes written'
tasks={int(r['case_id']):r for r in map(json.loads,data.decode('utf-8').splitlines())};assert len(tasks)==141
ledger.parent.mkdir(parents=True,exist_ok=True)
if not ledger.exists():ledger.write_bytes(data)
restored=0
for row in manifest['reference_files']:
    template=(ROOT/row['template']).resolve();target=(ROOT/row['path']).resolve()
    assert template.is_relative_to(ROOT.resolve()) and target.is_relative_to(ROOT.resolve())
    raw=template.read_bytes();assert hashlib.sha256(raw).hexdigest()==row['template_sha256']
    text=raw.decode('utf-8')
    for ident,rule in row['restorations'].items():
        token=json.dumps(rule['placeholder']);assert token in text
        text=text.replace(token,json.dumps(tasks[int(ident)]['brief_plan'],ensure_ascii=rule['json_ensure_ascii']))
    result=text.encode('utf-8')
    assert len(result)==row['original_bytes'] and hashlib.sha256(result).hexdigest()==row['original_sha256'],row['path']
    if target.exists():assert target.read_bytes()==result,'Existing reference differs; refused overwrite: '+row['path']
    else:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(result)
    restored+=1
print(json.dumps({'task_records_hash_verified':141,'reference_files_restored_or_verified':restored,'original_reference_bytes_reconstructed':True,'attack_helpers_downloaded_or_executed':False}))
