"""Check the documented CLI on changed cases and deterministic controls."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parent;source=root/'work/sabench-pinned'
comparison=json.loads((root/'results/sabench_normalization_comparison.json').read_text())
changes=[r for r in comparison['changed_records'] if r['baseline']!=r['adapted']]
assert len(changes)==9
tasks={t['task_id']:t for s in (root/'data/authorization-refresh-20261112/hf/tasks.jsonl').read_text().splitlines() if s.strip() for t in [json.loads(s)]}
controls=[]
for model in ['gpt-5.4','claude-opus-4.6','qwen-3.5-plus']:
    controls.append({'model':model,'task_id':sorted(tasks)[0]})
out=root/'work/sabench-cli-check-v1';out.mkdir(exist_ok=False)
env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';env['PYTHONUTF8']='1'
records=[]
for case in changes+controls:
    model,tid=case['model'],case['task_id'];taskfile=out/(tid+'.json')
    taskfile.write_text(json.dumps(tasks[tid]),encoding='utf-8')
    matches=list((source/'traces'/model).rglob(tid+'.json'));assert len(matches)==1
    command=[sys.executable,str(source/'scripts/oracle_verify.py'),str(taskfile),str(matches[0])]
    proc=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',env=env,timeout=30)
    assert proc.returncode==0,(command,proc.stderr)
    actual=json.loads(proc.stdout)
    baseline=json.loads((root/'work/sabench-oracle-replay-v1'/model/(tid+'.json')).read_text())
    assert actual==baseline
    (out/(model+'__'+tid+'.json')).write_text(proc.stdout,encoding='utf-8')
    records.append({'model':model,'task_id':tid,'changed_case':case in changes,'exit_code':proc.returncode,'full_report_matches_direct_replay':True})
result={'cases':records,'changed_cases_checked':9,'unchanged_controls_checked':3,'cli_matches_initial_direct_replay':True,'new_inferences':0,'scope':'Independent subprocess/entry-point check; not independent human semantic validation.'}
(root/'results/sabench_cli_check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))
