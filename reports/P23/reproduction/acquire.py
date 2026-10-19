"""Pin the closest source-revocation artifact and bounded primary reading copies."""
import json,urllib.parse
from pathlib import Path
import source_io as io
ROOT=Path(__file__).resolve().parent;io.ROOT=ROOT
io.REPOS=['CristhianKapelinski/sbseg2026-ragtrap']
if __name__=='__main__':
    io.main()
    source=json.loads((ROOT/'data/source_manifest.json').read_text())[0]
    selected=[f for f in source['files'] if f['path'].startswith(('src/','tests/')) and f['path'].endswith('.py')]
    selected += [f for f in source['files'] if f['path'] in ['DOCUMENTATION.md','CITATION.cff','uv.lock']]
    receipts=[]
    for f in selected:
        if f.get('size',0)>2_000_000:continue
        name=f['path'];receipts.append(io.fetch(f'https://raw.githubusercontent.com/{source["repository"]}/{source["revision"]}/{urllib.parse.quote(name,safe="/")}',ROOT/'data/source-code'/name))
    (ROOT/'data/code_manifest.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
    io.fetch('https://arxiv.org/html/2606.15903v2',ROOT/'data/reading/forgeteval-v2.html',6_000_000)
    print('Source revision',source['revision'],'code/document files',len(receipts))
