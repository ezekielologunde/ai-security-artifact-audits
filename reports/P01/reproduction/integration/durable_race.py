"""Controlled durable-checkpoint admission race, separate from framework-v1."""
import argparse, hashlib, importlib.metadata, json, os, sqlite3, threading
from pathlib import Path
from datetime import datetime, timezone
from typing import TypedDict
os.environ['LANGSMITH_TRACING']='false'
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

class State(TypedDict):
    canary: str

def counts(path):
    with sqlite3.connect(f'file:{path.as_posix()}?mode=ro',uri=True) as db:
        return {root:db.execute('SELECT COUNT(*) FROM checkpoints WHERE thread_id=?',(root,)).fetchone()[0] for root in ('A','B')}

def case(folder, guard):
    folder.mkdir(); path=folder/'checkpoints.sqlite'; backup=folder/'backup.sqlite'
    lock=threading.Lock(); checked=threading.Event(); release=threading.Event()
    active=True; errors=[]; config=lambda root:{'configurable':{'thread_id':root}}
    with SqliteSaver.from_conn_string(str(path)) as saver:
        builder=StateGraph(State);builder.add_node('echo',lambda state:state)
        builder.add_edge(START,'echo');builder.add_edge('echo',END)
        graph=builder.compile(checkpointer=saver)
        for root in ('A','B'): graph.invoke({'canary':f'controlled-{root}'},config(root))
        before=counts(path); assert before['A']>0 and before['B']>0
        with sqlite3.connect(path) as source, sqlite3.connect(backup) as target: source.backup(target)
        def late():
            try:
                with lock: admitted=active
                assert admitted; checked.set()
                if not release.wait(10): raise TimeoutError('release barrier')
                if guard:
                    # Hold lifecycle lock through invocation and all checkpoint writes.
                    with lock:
                        if active: graph.invoke({'canary':'late-A'},config('A'))
                else: graph.invoke({'canary':'late-A'},config('A'))
            except BaseException as exc: errors.append(repr(exc)); checked.set()
        worker=threading.Thread(target=late);worker.start()
        try:
            assert checked.wait(10) and not errors
            with lock:
                active=False; saver.delete_thread('A')
            after_delete=counts(path); assert after_delete['A']==0 and after_delete['B']==before['B']
        finally: release.set();worker.join(timeout=10)
        assert not worker.is_alive() and not errors,errors
        after_late=counts(path)
        assert (after_late['A']==0)==guard
        assert after_late['B']==before['B']
    reopened=counts(path); snapshot=counts(backup)
    assert reopened==after_late and snapshot==before
    return {'commit_guard':guard,'before':before,'after_delete':after_delete,'after_late':after_late,
            'fresh_connection':reopened,'retained_backup':snapshot,
            'checkpoint_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest()}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--name',required=True);parser.add_argument('--repeats',type=int,default=5);args=parser.parse_args()
    if Path(args.name).name!=args.name or args.name in ('.','..') or args.repeats<1: parser.error('New directory name and positive repeat count required')
    out=Path(__file__).resolve().parent/'results'/args.name;out.mkdir(parents=True,exist_ok=False)
    protocol={'frozen_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'repeats':args.repeats,'packages':{p:importlib.metadata.version(p) for p in ('langgraph','langgraph-checkpoint-sqlite')},'limits':['Local trusted authority flag','Thread barriers force one selected interleaving','No LLM or provider','No physical erasure; retained backup is intentionally observable','No effects or closure certificates measured']}
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2))
    rows=[]
    for repeat in range(args.repeats):
        for guard in (False,True):
            ident=f'r{repeat}-guard{int(guard)}';rows.append({'run_id':ident,**case(out/ident,guard)})
    summary={'runs':len(rows),'weak_gate_recreated':sum(r['after_late']['A']>0 for r in rows if not r['commit_guard']),'guarded_recreated':sum(r['after_late']['A']>0 for r in rows if r['commit_guard']),'retained_backups_with_A':sum(r['retained_backup']['A']>0 for r in rows),'independent_B_preserved':all(r['fresh_connection']['B']==r['before']['B'] for r in rows),'assertions_passed':True}
    (out/'records.json').write_text(json.dumps(rows,indent=2));(out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
if __name__=='__main__': main()
