"""Pin primary authorization papers and expose artifact links for inspection."""
import hashlib,json,re,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'data';OUT.mkdir(exist_ok=True)
records=[]
for ident in ['2510.26702','2512.11147','2609.00267']:
    url='https://arxiv.org/html/'+ident;path=OUT/(ident+'.html')
    if not path.exists():
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'AISecurityResearch/0.1'}),timeout=40) as r:
            data=r.read(5_000_001)
        if len(data)>5_000_000:raise ValueError('bounded source limit exceeded')
        path.write_bytes(data)
    data=path.read_bytes();text=data.decode('utf-8',errors='replace')
    links=sorted(set(re.findall(r'https://(?:github.com|huggingface.co)/[^\s"<>]+',text)))
    versions=sorted(set(re.findall(r'arXiv:'+re.escape(ident)+r'v\d+',text)))
    records.append({'paper':ident,'url':url,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'versions':versions,
        'path':path.relative_to(ROOT).as_posix(),'artifact_candidates':links,
        'retrieved_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
(OUT/'source_manifest.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
print(json.dumps([{'paper':r['paper'],'versions':r['versions'],'links':r['artifact_candidates'][:18]} for r in records],indent=2))
