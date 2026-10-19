"""Run the reviewed, pinned synthetic generator in fresh local copies."""
import hashlib, importlib.metadata, json, os, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    source=ROOT/'data/sources/Deepa-15__shadowai-enterprise-dataset/files'
    receipts=list(source.rglob('*.receipt.json'))
    for path in receipts:
        r=json.loads(path.read_text());assert hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()==r['sha256']
    env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUTF8='1')
    runs=[]
    for number in [1,2]:
        dest=ROOT/'work'/f'generator-run-{number}'
        if (dest/'RUN_COMPLETE.json').exists():
            runs.append(json.loads((dest/'RUN_COMPLETE.json').read_text()));continue
        if dest.exists():raise ValueError(f'Partial run preserved; inspect before retrying: {dest}')
        dest.mkdir(parents=True)
        for path in source.rglob('*'):
            if path.is_file() and not path.name.endswith('.receipt.json'):
                relative=path.relative_to(source);target=dest/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
        with (dest/'stdout.log').open('w',encoding='utf-8') as stdout,(dest/'stderr.log').open('w',encoding='utf-8') as stderr:
            result=subprocess.run([sys.executable,'main.py'],cwd=dest,env=env,stdout=stdout,stderr=stderr,timeout=240)
        files=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((dest/'outputs').glob('*')) if p.is_file()]
        row={'run':number,'exit_code':result.returncode,'files':files}
        (dest/'RUN_COMPLETE.json').write_text(json.dumps(row,indent=2),encoding='utf-8');runs.append(row)
        print('generator run',number,'exit',result.returncode,'outputs',len(files),flush=True)
        if result.returncode:break
    (ROOT/'results/generator_runs.json').write_text(json.dumps({'runs':runs,'python':sys.version,
        'dependencies':{k:importlib.metadata.version(k) for k in ['numpy','pandas','Faker']}},indent=2),encoding='utf-8')

if __name__=='__main__':main()
