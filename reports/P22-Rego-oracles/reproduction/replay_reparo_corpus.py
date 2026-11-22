"""Native corpus replay with a fresh Linux staging lifetime and per-command isolation."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from contextlib import nullcontext

ROOT=Path(__file__).resolve().parent
EXPECTED_OPA='35e3b352e715e80624ead6c89930d8585f6f7d94cdc409eb2a9fe36620dcccba'

def linux_main(root,work_name='reparo-corpus-replay-v1',stream_results=False):
    root=Path(root)
    work=root/'work'/work_name
    stage=Path('/tmp')/(work_name+'-20261121')
    stage.mkdir(mode=0o700)
    shutil.copytree(work/'inputs',stage/'inputs')
    shutil.copyfile(root/'tools/opa-v1.22.4/opa_linux_amd64_static',stage/'opa')
    os.chmod(stage/'opa',0o700)
    assert hashlib.sha256((stage/'opa').read_bytes()).hexdigest()==EXPECTED_OPA
    tasks=json.loads((work/'tasks.json').read_text())
    prefix=['bwrap','--unshare-all','--die-with-parent','--new-session','--cap-drop','ALL','--ro-bind',str(stage/'opa'),'/opa','--ro-bind',str(stage/'inputs'),'/inputs','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--clearenv','--setenv','HOME','/tmp','--chdir','/inputs','--','/opa']
    version=subprocess.run(prefix+['version'],capture_output=True,text=True,timeout=15)
    assert version.returncode==0,version.stderr
    (work/'runtime-version.txt').write_text(version.stdout)
    def run(task):
        start=time.monotonic()
        try:
            p=subprocess.run(prefix+task['args'],input=task.get('stdin'),capture_output=True,text=True,timeout=15)
            result=dict(**task,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,elapsed_seconds=time.monotonic()-start)
            try:result['parsed']=json.loads(p.stdout)
            except json.JSONDecodeError:pass
        except subprocess.TimeoutExpired as exc:
            result=dict(**task,exit_code=None,timeout=True,stdout=(exc.stdout or b'').decode(errors='replace') if isinstance(exc.stdout,bytes) else exc.stdout,stderr=(exc.stderr or b'').decode(errors='replace') if isinstance(exc.stderr,bytes) else exc.stderr,elapsed_seconds=time.monotonic()-start)
        return result
    with (nullcontext(sys.stdout) if stream_results else (work/'native-results.jsonl').open('x',encoding='utf-8')) as stream:
        with ThreadPoolExecutor(max_workers=2 if stream_results else 4) as pool:
            pending={pool.submit(run,t):t for t in tasks}
            for i,future in enumerate(as_completed(pending),1):
                stream.write(json.dumps(future.result())+'\n');stream.flush()
                pending.pop(future)
                if i%50==0 or i==len(tasks):print(json.dumps({'progress':True,'completed_commands':i,'total':len(tasks)}),flush=True)
    return

def windows_main():
    source=ROOT/'data/reparo-archive-20261121/selected/Final Policy with Test oracle/rego'
    work=ROOT/'work/reparo-corpus-replay-v2'
    work.mkdir(exist_ok=False)
    acquisition=json.loads((ROOT/'results/reparo_archive_acquisition_20261121.json').read_text())
    prefix='Final Policy with Test oracle/rego/'
    expected={r['path'].split(prefix,1)[1]:r['sha256'] for r in acquisition['files'] if prefix in r['path']}
    actual={p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
    assert actual==expected and len(actual)==850
    shutil.copytree(source,work/'inputs')
    policies=sorted(source.glob('*/*/final_policy.rego'))
    assert len(policies)==200
    suites=[];missing=[];csv_summary=[];tasks=[]
    for policy in policies:
        rel=policy.relative_to(source).as_posix()
        identity=rel.rsplit('/',1)[0]
        tasks.extend([dict(kind='check',identity=identity,args=['check','/inputs/'+rel]),dict(kind='parse-policy',identity=identity,args=['parse','--format','json','/inputs/'+rel])])
        for oracle in ('gpt-5.4','glm-5.2'):
            tests=policy.parent/('final_rendered_tests_'+oracle+'.rego')
            saved=policy.parent/('final_test_case_results_'+oracle+'.csv')
            key=identity+'/'+oracle
            if not tests.exists() or not saved.exists():
                missing.append(dict(identity=key,tests_present=tests.exists(),csv_present=saved.exists()))
                continue
            suites.append(key)
            test_rel=tests.relative_to(source).as_posix()
            tasks.extend([dict(kind='parse-tests',identity=key,args=['parse','--format','json','/inputs/'+test_rel]),dict(kind='test',identity=key,args=['test','--format','json','--verbose','--timeout','10s','/inputs/'+rel,'/inputs/'+test_rel])])
            with saved.open(encoding='utf-8-sig',newline='') as f:
                rows=list(csv.DictReader(f))
            csv_summary.append(dict(identity=key,rows=rows,path=saved.relative_to(source).as_posix()))
    assert len(suites)==325 and len(missing)==75
    inventory=dict(date='2026-11-21',policies=200,suites=325,possible_suites=400,missing=missing,source_hashes=actual,saved_csv=csv_summary,tasks=len(tasks))
    (work/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n',encoding='utf-8')
    (work/'tasks.json').write_text(json.dumps(tasks),encoding='utf-8')
    print(json.dumps({'stage':'prepared','policies':200,'suites':325,'missing_suites':75,'commands':len(tasks)}),flush=True)
    def wslpath(path):return '/mnt/'+path.drive[0].lower()+'/'+path.as_posix().split(':/',1)[1]
    command=['wsl.exe','-d','Ubuntu','--','python3',wslpath(Path(__file__).resolve()),'--linux-root',wslpath(ROOT)]
    command.append('reparo-corpus-replay-v2')
    records=work/'records';records.mkdir()
    with (work/'driver-stderr.txt').open('w',encoding='utf-8') as error_file:
        proc=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=error_file,text=True,encoding='utf-8')
        count=0
        for line in proc.stdout:
            row=json.loads(line)
            if row.get('progress'):
                print(json.dumps(row),flush=True);continue
            name=hashlib.sha256((row['kind']+'\0'+row['identity']).encode()).hexdigest()+'.json.gz'
            (records/name).write_bytes(gzip.compress(json.dumps(row).encode(),compresslevel=6,mtime=0));count+=1
        assert proc.wait()==0,(work/'driver-stderr.txt').read_text()
    assert count==1050

    after={p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
    assert actual==after
    receipt=dict(date='2026-11-21',protocol_sha256=hashlib.sha256((ROOT/'REPARO_CORPUS_REPLAY_PROTOCOL_20261121.json').read_bytes()).hexdigest(),policies=200,suites=325,missing_suites=75,commands=len(tasks),source_inputs_unchanged=True,raw_results='work/reparo-corpus-replay-v2/records/*.json.gz',inventory='work/reparo-corpus-replay-v2/inventory.json',new_model_calls=0,scope='Pinned modern runtime replay, not confirmed original paper runtime or authorization-intent validation')
    (ROOT/'results/reparo_corpus_replay_20261121.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2),flush=True)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--linux-root':linux_main(sys.argv[2],sys.argv[3] if len(sys.argv)>3 else 'reparo-corpus-replay-v1',len(sys.argv)>3)
    else:windows_main()
