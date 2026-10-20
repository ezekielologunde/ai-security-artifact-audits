"""Fetch the two experiment inputs and accompanying upstream license/card files."""
import hashlib,json,pathlib,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'download-manifest.json').read_text())
for item in manifest:
    name=item['path']
    selected=name.startswith('datasets/locomo/') or (name.startswith('datasets/longmemeval/') and 's_cleaned' not in name)
    if not selected or item.get('status')!='downloaded':continue
    dest=ROOT/name
    if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest()==item['sha256']:
        print('Verified',name);continue
    dest.parent.mkdir(parents=True,exist_ok=True)
    request=urllib.request.Request(item['url'],headers={'User-Agent':'research-reproduction/1.0'})
    with urllib.request.urlopen(request,timeout=120) as response:data=response.read()
    assert hashlib.sha256(data).hexdigest()==item['sha256'],'Downloaded hash mismatch: '+name
    dest.write_bytes(data);print('Downloaded and verified',name)
