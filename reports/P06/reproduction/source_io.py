"""Inventory public author sources and acquire bounded, revision-pinned evidence."""
import concurrent.futures as cf, hashlib, json, time, urllib.parse, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPOS=['Deepa-15/shadowai-enterprise-dataset','Trusera/ai-bom','cisco-ai-defense/aibom','perfecxion-ai/ai-agent-scanner']

def fetch(url,path,limit=4_000_000):
    path.parent.mkdir(parents=True,exist_ok=True)
    receipt=path.with_name(path.name+'.receipt.json')
    if path.exists() and receipt.exists():
        r=json.loads(receipt.read_text());assert hashlib.sha256(path.read_bytes()).hexdigest()==r['sha256'];return r
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'AISecurityResearch/0.1'}),timeout=40) as response:
        data=response.read(limit+1);resolved=response.geturl()
    if len(data)>limit:raise ValueError('bounded acquisition limit exceeded')
    path.write_bytes(data)
    r={'url':url,'resolved_url':resolved,'path':path.relative_to(ROOT).as_posix(),'bytes':len(data),
       'sha256':hashlib.sha256(data).hexdigest(),'retrieved_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    receipt.write_text(json.dumps(r,indent=2),encoding='utf-8');return r

def main():
    index=[]
    saved=ROOT/'data/source_manifest.json'
    pinned={r['repository']:r['revision'] for r in json.loads(saved.read_text())} if saved.exists() else {}
    for repo in REPOS:
        slug=repo.replace('/','__');folder=ROOT/'data/sources'/slug
        fetch(f'https://api.github.com/repos/{repo}',folder/'repository.json')
        meta=json.loads((folder/'repository.json').read_text())
        ref=pinned.get(repo,meta['default_branch'])
        fetch(f'https://api.github.com/repos/{repo}/commits/{ref}',folder/'commit.json')
        sha=json.loads((folder/'commit.json').read_text())['sha']
        fetch(f'https://api.github.com/repos/{repo}/git/trees/{sha}?recursive=1',folder/'tree.json')
        tree=json.loads((folder/'tree.json').read_text()); files=[f for f in tree.get('tree',[]) if f['type']=='blob']
        selected=[f for f in files if f['path'].lower() in ['readme.md','license','license.md','license.txt','pyproject.toml','requirements.txt']]
        if repo.startswith('Deepa-15/'):
            selected += [f for f in files if f['path'].endswith('.py') or (f['path'].startswith('config/') and f['path'].endswith('.json'))]
        selected=list({f['path']:f for f in selected}.values())
        errors=[];receipts=[]
        with cf.ThreadPoolExecutor(max_workers=5) as pool:
            futures={pool.submit(fetch,f'https://raw.githubusercontent.com/{repo}/{sha}/{urllib.parse.quote(f["path"],safe="/")}',folder/'files'/f['path']):f for f in selected if f.get('size',0)<4_000_000}
            for future in cf.as_completed(futures):
                try:receipts.append(future.result())
                except Exception as exc:errors.append({'file':futures[future]['path'],'error':str(exc)})
        row={'repository':repo,'revision':sha,'license_metadata':meta.get('license'),'files':files,'selected_receipts':receipts,'errors':errors}
        index.append(row);print(repo,sha,len(receipts),'files',len(errors),'errors',flush=True)
    (ROOT/'data/source_manifest.json').write_text(json.dumps(index,indent=2),encoding='utf-8')

if __name__=='__main__':main()
