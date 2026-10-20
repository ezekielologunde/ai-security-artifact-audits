"""Controlled local sink: real SQLite transactions, files and worker processes.

This is a research fixture, not production IAM. Tokens are synthetic identifiers.
No imported skill code, real credentials, provider APIs, or LLMs are executed.
"""
import json,sqlite3,time
from contextlib import contextmanager
from pathlib import Path

ARMS=('administrative','process_stop','credential_revoke','tool_hook','sink_overlay','blanket_deny')

@contextmanager
def connection(run_dir):
    c=sqlite3.connect(Path(run_dir)/'runtime.sqlite',timeout=10)
    c.row_factory=sqlite3.Row
    try:
        with c:yield c
    finally:c.close()

def initialize(run_dir,case,arm):
    p=Path(run_dir);p.mkdir(parents=True,exist_ok=False)
    with connection(p) as c:
        c.executescript('''
        CREATE TABLE roots(id TEXT PRIMARY KEY,epoch INTEGER,cut INTEGER,issuer_blocked INTEGER);
        CREATE TABLE tokens(id TEXT PRIMARY KEY,root TEXT,valid INTEGER);
        CREATE TABLE config(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE requests(seq INTEGER PRIMARY KEY AUTOINCREMENT,phase TEXT,root TEXT,epoch INTEGER,route TEXT,auth_mode TEXT,allowed INTEGER,reason TEXT,admission_ns INTEGER);
        CREATE TABLE effects(seq INTEGER PRIMARY KEY AUTOINCREMENT,request_seq INTEGER,root TEXT,payload TEXT);
        CREATE TABLE jobs(id TEXT PRIMARY KEY,root TEXT,state TEXT);
        INSERT INTO roots VALUES('A',1,0,0),('B',1,0,0);
        INSERT INTO tokens VALUES('token-A','A',1),('token-B','B',1);
        INSERT INTO jobs VALUES('original-job','A','QUEUED');
        ''')
        c.executemany('INSERT INTO config VALUES(?,?)',[('arm',arm),('controller_stopped','0'),('administrative_retired','0')])
    artifact={'root':'A','active':True,'kind':case['artifact_kind'],'fixture_canary':'SYNTHETIC-OFFBOARDING-CANARY','source_case_id':case['source_case_id']}
    (p/'residual.json').write_text(json.dumps(artifact),encoding='utf-8')
    (p/'case.json').write_text(json.dumps(case),encoding='utf-8')

def retire(run_dir,case,arm):
    with connection(run_dir) as c:
        c.execute("UPDATE config SET value='1' WHERE key='administrative_retired'")
        if arm in ('process_stop','sink_overlay','blanket_deny'):
            c.execute("UPDATE config SET value='1' WHERE key='controller_stopped'")
        if arm in ('credential_revoke','sink_overlay','blanket_deny'):
            c.execute("UPDATE tokens SET valid=0 WHERE root='A'")
            c.execute("UPDATE roots SET issuer_blocked=1 WHERE id='A'")
        if arm in ('sink_overlay','blanket_deny'):
            c.execute("UPDATE roots SET epoch=epoch+1,cut=1,issuer_blocked=1 WHERE id='A'")
            c.execute("UPDATE jobs SET state='CANCELLED' WHERE root='A'")
    if arm in ('sink_overlay','blanket_deny') and not case['failed_cleanup']:
        p=Path(run_dir)/'residual.json';obj=json.loads(p.read_text(encoding='utf-8'))
        obj['active']=False;p.write_text(json.dumps(obj),encoding='utf-8')
    # A false cleanup acknowledgement is an intentional experimental fault.
    return {'retirement_ack':'SUCCESS','cleanup_ack':'SUCCESS','fault_injected':case['failed_cleanup']}

def admit(run_dir,root,epoch,auth_mode,route,phase):
    """Decision and observable effect share one BEGIN IMMEDIATE transaction."""
    start=time.perf_counter_ns()
    with connection(run_dir) as c:
        c.execute('BEGIN IMMEDIATE')
        config=dict((r['key'],r['value']) for r in c.execute('SELECT * FROM config'))
        arm=config['arm']; authority=c.execute('SELECT * FROM roots WHERE id=?',(root,)).fetchone()
        token=c.execute('SELECT * FROM tokens WHERE id=?',('token-'+root,)).fetchone()
        allowed=True;reason='accepted'
        if authority is None:
            allowed=False;reason='unknown-root'
        elif phase=='post' and arm=='blanket_deny':
            allowed=False;reason='blanket-deny'
        elif arm=='sink_overlay' and (authority['cut'] or authority['epoch']!=epoch):
            allowed=False;reason='durable-root-fence'
        elif phase=='post' and arm=='tool_hook' and route=='foreground' and config['administrative_retired']=='1' and root=='A':
            allowed=False;reason='foreground-hook'
        elif auth_mode=='issuer_recheck' and (token is None or not token['valid']):
            allowed=False;reason='revoked-token'
        # cached_token intentionally models a backend trusting a captured token;
        # local_uncredentialed models a path with no issuer recheck. The overlay
        # still fences both at the protected sink. Process stop affects only the
        # controller; this distinct worker process retains its submitted request.
        elapsed=time.perf_counter_ns()-start
        cur=c.execute('INSERT INTO requests(phase,root,epoch,route,auth_mode,allowed,reason,admission_ns) VALUES(?,?,?,?,?,?,?,?)',(phase,root,epoch,route,auth_mode,int(allowed),reason,elapsed))
        if allowed:
            c.execute('INSERT INTO effects(request_seq,root,payload) VALUES(?,?,?)',(cur.lastrowid,root,'inert-local-effect'))
        return {'allowed':allowed,'reason':reason,'admission_ns':elapsed}

def worker(run_dir,phase):
    case=json.loads((Path(run_dir)/'case.json').read_text(encoding='utf-8'))
    # Explicit replay attempts are made even when queue cancellation succeeds.
    # This separates cleanup effectiveness from protected-sink enforcement.
    return {'retired':admit(run_dir,'A',1,case['auth_mode'],case['route'],phase),
            'independent':admit(run_dir,'B',1,'issuer_recheck','background',phase)}
