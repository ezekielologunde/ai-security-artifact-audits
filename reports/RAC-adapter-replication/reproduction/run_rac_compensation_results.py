"""Measure native compensation bookkeeping and independently read inert fixture state."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import platform
import sqlite3
import sys

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'data/rac-qualification-20261121'
EXTRA=ROOT/'data/rac-adapter-followup-20261121'
STATUS_AWARE='--reject-error-results' in sys.argv
WORK=ROOT/('work/rac-compensation-results-status-aware-v1' if STATUS_AWARE else 'work/rac-compensation-results-v1')
WORK.mkdir(parents=True,exist_ok=False)
sys.dont_write_bytecode=True
sys.path[:0]=[str(Path(os.environ.get('RAC_RUNTIME_PATH',str(ROOT/'tools/rac-runtime')))),str(SOURCE/'src')]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
acquisition=json.loads((SOURCE/'acquisition.json').read_text())
extra=json.loads((EXTRA/'acquisition.json').read_text())
for row in acquisition['files']:assert sha(SOURCE/row['path'])==row['sha256']
for row in extra['files']:assert sha(EXTRA/row['local_file'])==row['sha256']
spec=importlib.util.spec_from_file_location('rac_native_adapter',EXTRA/'langchain_adapters.py')
native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
from react_agent_compensation.core.recovery_manager import RecoveryManager
from react_agent_compensation.core.protocols import SimpleActionResult
from react_agent_compensation.core.errors.explicit import ExplicitStatusStrategy
from react_agent_compensation.core.extraction.passthrough import PassthroughStrategy
import pydantic

MODES=['core-success','core-explicit-error','core-raised-exception','native-success',
       'native-raised-before-change','native-partial-change-then-raise',
       'native-missing-tool','native-success-returning-noop']
detector=ExplicitStatusStrategy()
def observe(path):
    with sqlite3.connect('file:'+path.as_posix()+'?mode=ro',uri=True) as db:
        rows=db.execute('select id,active from sessions order by id').fetchall()
        artifacts=db.execute('select session_id,body from artifacts order by session_id').fetchall()
    return dict(sessions=[dict(id=i,active=bool(a)) for i,a in rows],
                active_sessions=sum(bool(a) for _,a in rows),artifact_rows=len(artifacts),
                artifact_contents=[body for _,body in artifacts])

cases=[]
for mode in MODES:
    path=WORK/(mode+'.db')
    with sqlite3.connect(path) as db:
        db.executescript('create table sessions(id text primary key, active integer); create table artifacts(session_id text,body text);')
    calls=[];invocations=[]
    class Tool:
        def __init__(self,name):self.name=name
        def invoke(self,params):
            invocations.append(dict(name=self.name,params=params))
            if self.name=='create_session':
                with sqlite3.connect(path) as db:
                    db.execute('insert into sessions values(?,?)',('s1',1))
                    db.execute('insert into artifacts values(?,?)',('s1','SYNTHETIC_RESIDUAL_ARTIFACT'))
                return {'session_id':'s1'}
            assert params=={'session_id':'s1'},params
            if mode in ('core-raised-exception','native-raised-before-change'):
                raise RuntimeError('AUTHORED_COMPENSATION_FAILURE_BEFORE_CHANGE')
            if mode=='native-success-returning-noop':
                return {'message':'success claimed without changing fixture state'}
            with sqlite3.connect(path) as db:
                db.execute('update sessions set active=0 where id=?',('s1',))
            if mode=='native-partial-change-then-raise':
                raise RuntimeError('AUTHORED_COMPENSATION_FAILURE_AFTER_SESSION_CHANGE')
            with sqlite3.connect(path) as db:
                db.execute('delete from artifacts where session_id=?',('s1',))
            return {'revoked':True,'artifact_removed':True}
    tools={'create_session':Tool('create_session'),'remove_session':Tool('remove_session')}
    if mode=='native-missing-tool':del tools['remove_session']
    class DirectExecutor:
        def execute(self,name,params):
            if name=='remove_session' and mode=='core-explicit-error':
                return SimpleActionResult(content='AUTHORED_EXPLICIT_ERROR',status='error',name=name)
            return SimpleActionResult(content=tools[name].invoke(params),status='success',name=name)
    delegate=native.LangChainToolExecutor(tools) if mode.startswith('native-') else DirectExecutor()
    class ObservedExecutor:
        def execute(self,name,params):
            try:
                result=delegate.execute(name,params)
                calls.append(dict(name=name,params=params,result_type=type(result).__name__,
                                  status=result.status,content=result.content,
                                  explicit_status_is_error=detector.is_error(result)))
                if STATUS_AWARE and name=='remove_session' and detector.is_error(result) is True:
                    raise RuntimeError('AUTHORED_STATUS_GUARD: '+str(result.content))
                return result
            except Exception as exc:
                calls.append(dict(name=name,params=params,exception=type(exc).__name__,message=str(exc)))
                raise
    executor=ObservedExecutor()
    manager=RecoveryManager(compensation_pairs={'create_session':'remove_session'},
        action_executor=executor,extraction_strategy=PassthroughStrategy(),
        error_strategy=detector,infer_dependencies=False,enable_tool_alternatives=False)
    record=manager.record_action('create_session',{})
    forward=executor.execute('create_session',{})
    assert forward.status=='success'
    manager.mark_completed(record.id,result=forward.content)
    before=observe(path)
    assert before['active_sessions']==1 and before['artifact_rows']==1
    try:
        result=manager.rollback()
        outcome=dict(kind='return',success=result.success,compensated=list(result.compensated),
                     failed=list(result.failed),message=result.message)
    except Exception as exc:
        outcome=dict(kind='exception',exception=type(exc).__name__,message=str(exc))
    after=observe(path)
    final=manager.log.get(record.id)
    compensation_calls=[c for c in calls if c['name']=='remove_session']
    error_return=any(c.get('explicit_status_is_error') is True for c in compensation_calls)
    residue=bool(after['active_sessions'] or after['artifact_rows'])
    cases.append(dict(condition=mode,record_id=record.id,before=before,after=after,
        executor_calls=calls,actual_tool_invocations=invocations,rollback=outcome,
        final_record_status=final.status.value,explicit_error_returned=error_return,
        compensation_bookkeeping_despite_error=error_return and outcome.get('success') is True and final.status.value.upper()=='COMPENSATED',
        fixture_residue_remains=residue,
        success_claim_with_residue=outcome.get('success') is True and residue))
assert len(cases)==8
for c in cases:
    if c['condition'] in ('core-success','native-success'):
        assert c['after']['active_sessions']==0 and c['after']['artifact_rows']==0
for row in acquisition['files']:assert sha(SOURCE/row['path'])==row['sha256']
for row in extra['files']:assert sha(EXTRA/row['local_file'])==row['sha256']
summary=dict(cases=8,explicit_error_bookkeeping_mismatches=sum(c['compensation_bookkeeping_despite_error'] for c in cases),
             success_claim_with_fixture_residue=sum(c['success_claim_with_residue'] for c in cases),
             success_returning_noop_is_semantic_limit_control=True,
             acquired_sources_unchanged=True,new_model_calls=0)
receipt=dict(date='2026-11-21',pin=acquisition['pin'],protocol_sha256=sha(ROOT/'RAC_COMPENSATION_RESULT_PROTOCOL_20261121.json'),
    harness_sha256=sha(Path(__file__)),python=platform.python_version(),pydantic=pydantic.__version__,
    loaded_adapter_sha256=sha(EXTRA/'langchain_adapters.py'),summary=summary,cases=cases,
    scope='Unchanged native core and adapter, authored local invoke-compatible tools and SQLite fixture state; not full LangChain integration, natural credential efficacy, crash recovery, production exploit or population prevalence.')
receipt['authored_status_guard_enabled']=STATUS_AWARE
output='rac_compensation_status_guard_20261121.json' if STATUS_AWARE else 'rac_compensation_results_20261121.json'
(ROOT/'results'/output).write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(summary,indent=2))
for c in cases:print(json.dumps({k:c[k] for k in ('condition','rollback','final_record_status','after','explicit_error_returned')}))
