import hashlib,json,pathlib,urllib.request,zipfile,time
ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs'/'behavioral-experiment';OUT.mkdir(parents=True,exist_ok=True)
WORK=ROOT/'work'/'llm';WORK.mkdir(parents=True,exist_ok=True)
def getjson(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'memory-deletion-research'}),timeout=60))
def download(url,path,expected=None):
    if not path.exists():
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'memory-deletion-research'}),timeout=120) as response,path.with_suffix(path.suffix+'.partial').open('wb') as f:
            while block:=response.read(1024*1024):f.write(block)
        path.with_suffix(path.suffix+'.partial').replace(path)
    h=hashlib.sha256(path.read_bytes()).hexdigest()
    if expected and h!=expected:raise ValueError('SHA256 mismatch: '+str(path))
    print(path.name,path.stat().st_size,h,flush=True)
    return {'url':url,'filename':path.name,'bytes':path.stat().st_size,'sha256':h,'expected_sha256':expected}
release=getjson('https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/b11425')
asset=next(a for a in release['assets'] if a['name']=='llama-b11425-bin-win-cpu-x64.zip')
runtime=download(asset['browser_download_url'],WORK/asset['name'],asset['digest'].split(':')[1])
with zipfile.ZipFile(WORK/asset['name']) as z:z.extractall(WORK/'runtime')
repo='Qwen/Qwen2.5-1.5B-Instruct-GGUF';rev='91cad51170dc346986eccefdc2dd33a9da36ead9'
tree=getjson(f'https://huggingface.co/api/models/{repo}/tree/{rev}?recursive=true')
entry=next(e for e in tree if e['path']=='qwen2.5-1.5b-instruct-q4_k_m.gguf')
model=download(f'https://huggingface.co/{repo}/resolve/{rev}/{entry["path"]}',WORK/entry['path'],entry['lfs']['oid'])
license=download(f'https://huggingface.co/{repo}/resolve/{rev}/LICENSE',OUT/'MODEL-LICENSE.txt')
card=download(f'https://huggingface.co/{repo}/resolve/{rev}/README.md',OUT/'MODEL-CARD.md')
manifest={'model_repository':repo,'model_revision':rev,'quantization':'Q4_K_M','runtime_tag':'b11425','runtime_commit':release['target_commitish'],'downloads':[runtime,model,license,card],'acquired_unix':time.time()}
(OUT/'model-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
