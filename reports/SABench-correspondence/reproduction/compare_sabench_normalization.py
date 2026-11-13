"""Compare the frozen runtime normalization with direct offline trace replay."""
import ast,copy,hashlib,json,sys
from collections import Counter
from pathlib import Path
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parent;data=root/'data/authorization-refresh-20261112';source=root/'work/sabench-pinned'
acq=json.loads((data/'sabench_acquisition.json').read_text())
baseline=root/'work/sabench-oracle-replay-v1'
baseline_hashes={p.relative_to(baseline).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in baseline.rglob('*.json')}
def verify():
    assert all(hashlib.sha256((source/n).read_bytes()).hexdigest()==v['sha256'] for n,v in acq['code_files'].items())
    assert all(hashlib.sha256((data/'hf'/n).read_bytes()).hexdigest()==v['sha256'] for n,v in acq['task_files'].items())
    assert all(hashlib.sha256((baseline/n).read_bytes()).hexdigest()==h for n,h in baseline_hashes.items())
verify()
out=root/'work/sabench-normalization-v1';out.mkdir(exist_ok=False)
sys.path.insert(0,str(source))
from sabench_re.models import Task,Trace,APICall
from sabench_re.oracle import oracle_verify
from sabench_re.registry import write_operation_from_call
from sabench_re.state import apply_writes
runner=source/'scripts/run_pilot_streaming.py';text=runner.read_text()
names={'normalize_write_args','email_id_from_thread_or_message_id','latest_email_id_in_thread','iter_emails'}
nodes=[n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name in names]
assert {n.name for n in nodes}==names
module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*nodes],type_ignores=[])
ns={};exec(compile(ast.fix_missing_locations(module),str(runner),'exec'),ns)
normalize=ns['normalize_write_args']
state={'email':{'threads':[{'id':'t','emails':[{'id':'a','read':False},{'id':'b','read':True}]}]}}
original=copy.deepcopy(state);args={'thread_id':'t'};original_args=copy.deepcopy(args)
controls={}
controls['explicit_id_precedence']=normalize('email','reply',{'id':'explicit','thread_id':'t'},state)['id']=='explicit'
controls['unread_message_selected']=normalize('email','reply',args,state)['id']=='a'
all_read=copy.deepcopy(state);all_read['email']['threads'][0]['emails'][0]['read']=True
controls['last_message_all_read']=normalize('email','reply',args,all_read)['id']=='b'
controls['missing_thread_unchanged']=normalize('email','reply',{'thread_id':'missing'},state)=={'thread_id':'missing'}
controls['other_tool_unchanged']=normalize('ticket','assign',args,state)==args
controls['inputs_unmodified']=state==original and args==original_args
assert all(controls.values())
tasks={r['task_id']:Task.from_dict(r) for s in (data/'hf/tasks.jsonl').read_text().splitlines() if s.strip() for r in [json.loads(s)]}
models={};total=Counter();changed=[];changed_calls=0
for folder in sorted((source/'traces').iterdir()):
    if not folder.is_dir():continue
    counts=Counter()
    for path in sorted(folder.rglob('*.json')):
        raw=json.loads(path.read_text());task=tasks[raw['task_id']];trace=Trace.from_dict(raw)
        active=copy.deepcopy(task.s0);calls=[];changes=[]
        for call in trace.calls:
            arguments=normalize(call.tool,call.action,copy.deepcopy(call.args),active)
            if arguments!=call.args:changes.append({'step':call.step,'before':call.args,'after':arguments})
            adapted=APICall(tool=call.tool,action=call.action,args=arguments,success=call.success,step=call.step,agent_message=call.agent_message)
            calls.append(adapted);op=write_operation_from_call(adapted)
            if op is not None:active=apply_writes(active,[op])
        report=oracle_verify(task,Trace(calls=calls,final_response=trace.final_response))
        previous=json.loads((baseline/folder.name/(task.task_id+'.json')).read_text())
        flags={'goal':report.goal_satisfied,'cd':bool(report.cd),'external':bool(report.external_cd)}
        old_flags={'goal':previous['goal_satisfied'],'cd':bool(previous['cd']),'external':bool(previous['external_cd'])}
        counts['traces']+=1;counts['goal']+=flags['goal'];counts['cd']+=flags['cd'];counts['external_cd']+=flags['external']
        counts['goal_and_cd']+=flags['goal'] and flags['cd']
        changed_calls+=len(changes)
        if changes or flags!=old_flags:changed.append({'model':folder.name,'task_id':task.task_id,'calls':changes,'baseline':old_flags,'adapted':flags})
        dest=out/folder.name/(task.task_id+'.json');dest.parent.mkdir(exist_ok=True);dest.write_text(json.dumps(report.to_dict(),indent=2),encoding='utf-8')
    models[folder.name]=dict(counts);total.update(counts)
assert total['traces']==2211
verify()
result={'controls':controls,'selected_function_source_sha256':{n.name:hashlib.sha256(ast.get_source_segment(text,n).encode()).hexdigest() for n in nodes},
 'models':models,'total':dict(total),'changed_calls':changed_calls,'traces_with_argument_changes':sum(bool(r['calls']) for r in changed),
 'traces_with_changed_goal_cd_or_external':sum(r['baseline']!=r['adapted'] for r in changed),'changed_records':changed,
 'source_tasks_and_initial_reports_unchanged':True,'baseline_report_files_verified':len(baseline_hashes),'new_inferences':0,'external_actions':0,
 'scope':'Post hoc correspondence with released runtime normalization. This does not prove the actual paper-production scoring path or semantic ground truth.'}
(root/'results/sabench_normalization_comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['selected_function_source_sha256','models','changed_records']},indent=2))
