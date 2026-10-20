"""Persistent reference memory adapters and scope-revocation overlay.

No LLM or neural embeddings. Index uses a deterministic hashed lexical vector.
Never point adapters at personal or production storage.
"""
from __future__ import annotations
import copy, hashlib, json, math, pathlib, re, sqlite3, time
from functools import lru_cache
from collections import Counter

def terms(text):
    return re.findall(r'[a-z0-9_]+', text.lower())

@lru_cache(maxsize=8192)
def vector(text, dimensions=128):
    out=[0.0]*dimensions
    for token,count in Counter(terms(text)).items():
        digest=hashlib.sha256(token.encode()).digest()
        out[int.from_bytes(digest[:4],'big')%dimensions]+=count*(1 if digest[4]%2 else -1)
    norm=math.sqrt(sum(x*x for x in out)) or 1
    return tuple(x/norm for x in out)

def atomic_replace(pending,target):
    # Antivirus/indexer sharing locks can transiently deny Windows renames.
    for attempt in range(20):
        try:pending.replace(target);return
        except PermissionError:
            if attempt==19:raise
            time.sleep(0.01*(attempt+1))

def rank(records,query,k=3):
    q=vector(query)
    scored=[(sum(a*b for a,b in zip(q,vector(r['content']))),r['id']) for r in records if r['layer']=='raw']
    return [rid for score,rid in sorted(scored,key=lambda x:(-x[0],x[1]))[:k]]

class SQLiteStore:
    name='sqlite_wal'
    def __init__(self,path):
        self.path=pathlib.Path(path);self.path.mkdir(parents=True,exist_ok=True)
        self.connection=sqlite3.connect(self.path/'memory.sqlite')
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('PRAGMA synchronous=FULL')
        self.connection.execute('PRAGMA secure_delete=ON')
        self.connection.execute('CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        self.connection.execute('CREATE VIRTUAL TABLE IF NOT EXISTS lexical USING fts5(id UNINDEXED, content)')
        self.connection.commit()
    def records(self):
        return [json.loads(r[0]) for r in self.connection.execute('SELECT payload FROM records ORDER BY id')]
    def replace(self,records):
        with self.connection:
            self.connection.execute('DELETE FROM records');self.connection.execute('DELETE FROM lexical')
            self.connection.executemany('INSERT INTO records VALUES (?,?)',[(r['id'],json.dumps(r,sort_keys=True)) for r in records])
            self.connection.executemany('INSERT INTO lexical VALUES (?,?)',[(r['id'],r['content']) for r in records])
    def add(self,record):
        rows=[r for r in self.records() if r['id']!=record['id']]+[copy.deepcopy(record)];self.replace(rows)
    def compact(self):
        self.connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        self.connection.execute('VACUUM')
        self.connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    def close(self):self.connection.close()
    def reopen(self):self.close();self.__init__(self.path)
    def files(self):return [p for p in self.path.iterdir() if p.is_file()]

class JSONStore:
    name='json_files'
    def __init__(self,path):
        self.path=pathlib.Path(path);self.path.mkdir(parents=True,exist_ok=True)
        self.file=self.path/'records.json'
        if not self.file.exists():self.replace([])
    def records(self):return json.loads(self.file.read_text(encoding='utf-8'))
    def replace(self,records):
        pending=self.path/'records.pending'
        pending.write_text(json.dumps(records,sort_keys=True),encoding='utf-8');atomic_replace(pending,self.file)
    def add(self,record):self.replace([r for r in self.records() if r['id']!=record['id']]+[copy.deepcopy(record)])
    def compact(self):pass
    def close(self):pass
    def reopen(self):self.__init__(self.path)
    def files(self):return [p for p in self.path.iterdir() if p.is_file()]

class Authority:
    """Independent current authority, outside the memory snapshot.

    Generation checks are serialized by the test coordinator. This prototype
    does not implement a distributed transactional authority.
    """
    def __init__(self,path):
        self.path=pathlib.Path(path)
        if not self.path.exists():self._write({})
    def _write(self,state):
        pending=self.path.with_suffix('.pending');pending.write_text(json.dumps(state,sort_keys=True),encoding='utf-8');atomic_replace(pending,self.path)
    def state(self):return json.loads(self.path.read_text(encoding='utf-8'))
    def revoke(self,scope):
        state=self.state();state[scope]={'epoch':state.get(scope,{}).get('epoch',0)+1,'revoked':True};self._write(state)
    def allowed(self,record,state=None):
        state=self.state() if state is None else state
        for scope,epoch in record['scope_epochs'].items():
            current=state.get(scope,{'epoch':0,'revoked':False})
            if current['revoked'] or epoch!=current['epoch']:return False
        return True

class Overlay:
    def __init__(self,store,authority,arm):
        self.store=store;self.authority=authority;self.arm=arm
        self.durable=arm not in ('native_source_delete','dependency_purge')
        self.commit_guard=self.durable and arm!='without_commit_guard'
        self.restore_guard=self.durable and arm!='without_restore_guard'
        self.lineage=arm!='without_lineage_purge'
    def delete(self,scope,source_id):
        if self.durable:self.authority.revoke(scope)
        if self.arm=='native_source_delete' or not self.lineage:
            self.store.replace([r for r in self.store.records() if r['id']!=source_id])
        else:self.store.replace([r for r in self.store.records() if scope not in r['scope_epochs']])
        self.store.compact();self.rebuild_index()
    def commit(self,record,bypass=False):
        if not bypass and self.commit_guard and not self.authority.allowed(record):return False
        self.store.add(record);self.rebuild_index();return True
    def restore(self,records):
        state=self.authority.state() if self.restore_guard else None
        kept=[copy.deepcopy(r) for r in records if not self.restore_guard or self.authority.allowed(r,state)]
        self.store.replace(kept);self.store.compact();self.rebuild_index()
    def rebuild_index(self):
        index=[{'id':r['id'],'layer':r['layer'],'content':r['content'],'scope_epochs':r['scope_epochs'],'vector':vector(r['content'])} for r in self.store.records()]
        (self.store.path/'index.json').write_text(json.dumps(index,sort_keys=True),encoding='utf-8')
    def index(self):return json.loads((self.store.path/'index.json').read_text(encoding='utf-8'))
    def restart(self):self.store.reopen();self.rebuild_index()

def artifact(rid,layer,content,scopes,parents=()):
    return {'id':rid,'layer':layer,'content':content,'scope_epochs':{s:0 for s in scopes},'parents':list(parents)}

def audit_bytes(store,needle):
    marker=needle.encode();return [p.name for p in store.files() if marker in p.read_bytes()]
