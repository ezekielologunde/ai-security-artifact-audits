"""Replay all released traces with the reviewed, unmodified local oracle."""
import hashlib,json,sys
from collections import Counter
from pathlib import Path
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parent;data=root/'data/authorization-refresh-20261112';source=root/'work/sabench-pinned'
acq=json.loads((data/'sabench_acquisition.json').read_text())
def verify():
    assert all(hashlib.sha256((source/n).read_bytes()).hexdigest()==r['sha256'] for n,r in acq['code_files'].items())
    assert all(hashlib.sha256((data/'hf'/n).read_bytes()).hexdigest()==r['sha256'] for n,r in acq['task_files'].items())
verify()
(root/'results').mkdir(exist_ok=True)
out=root/'work/sabench-oracle-replay-v1';out.mkdir(exist_ok=False)
sys.path.insert(0,str(source))
from sabench_re.models import Task,Trace
from sabench_re.oracle import oracle_verify
tasks={r['task_id']:Task.from_dict(r) for s in (data/'hf/tasks.jsonl').read_text().splitlines() if s.strip() for r in [json.loads(s)]}
assert len(tasks)==201
models={};total=Counter();per_trace=[]
for folder in sorted((source/'traces').iterdir()):
    if not folder.is_dir():continue
    counts=Counter();ids=set()
    for p in sorted(folder.rglob('*.json')):
        raw=json.loads(p.read_text());tid=raw['task_id'];assert tid not in ids and tid in tasks;ids.add(tid)
        report=oracle_verify(tasks[tid],Trace.from_dict(raw));record=report.to_dict()
        counts['traces']+=1;counts['goal']+=int(report.goal_satisfied);counts['cd']+=int(bool(report.cd))
        counts['goal_and_cd']+=int(report.goal_satisfied and bool(report.cd))
        counts['ab_tasks']+=int(tasks[tid].is_ambiguous)
        counts['ab_cd']+=int(tasks[tid].is_ambiguous and bool(report.cd))
        counts['non_ab_cd']+=int(not tasks[tid].is_ambiguous and bool(report.cd))
        counts['external_cd']+=int(bool(report.external_cd))
        dest=out/folder.name/(tid+'.json');dest.parent.mkdir(exist_ok=True);dest.write_text(json.dumps(record,indent=2),encoding='utf-8')
        per_trace.append({'model':folder.name,'task_id':tid,'goal':report.goal_satisfied,'cd':bool(report.cd),'severity':report.severity})
    assert ids==set(tasks)
    models[folder.name]=dict(counts);total.update(counts)
assert len(models)==11 and total['traces']==2211
verify()
result={'code_revision':acq['code_revision'],'task_revision':acq['task_revision'],'models':models,'total':dict(total),
 'rates':{'cd':total['cd']/total['traces'],'goal':total['goal']/total['traces'],'cd_given_goal':total['goal_and_cd']/total['goal'],'ab_cd':total['ab_cd']/total['ab_tasks'],'non_ab_cd':total['non_ab_cd']/(total['traces']-total['ab_tasks'])},
 'all_acquired_reference_hashes_unchanged':True,'new_model_calls':0,'live_tool_calls':0,'scope':'Author-defined contract replay on released traces; not independent model or semantic ground-truth validation.'}
(root/'results/sabench_oracle_replay.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
(out/'per_trace_summary.json').write_text(json.dumps(per_trace,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
