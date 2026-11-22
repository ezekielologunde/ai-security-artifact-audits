"""Six prespecified native storage controls; never modifies acquired source."""
from pathlib import Path
import hashlib
import json
import platform
import sys
import time

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'data/lightfoot-qualification-20261121'
PROTOCOL=ROOT/'LIGHTFOOT_ROLLBACK_PROTOCOL_20261121.json'
WORK=ROOT/'work/lightfoot-rollback-controls-v1'
WORK.mkdir(parents=True,exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source_hashes={p.relative_to(SOURCE).as_posix():sha(p) for p in SOURCE.rglob('*.py')}
protocol_hash=sha(PROTOCOL)
sys.path.insert(0,str(SOURCE))
import numpy as np
from lightfoot.store import SQLiteStore

def put(store, ident, vector):
    store.put('chunks',dict(chunk_id=ident,doc_id='synthetic',tenant='fixture',ordinal=0,text='Synthetic inert '+ident,tokens=3))
    store.set_vector('chunks',(ident,),np.array(vector,dtype=np.float32),attrs={'tenant':'fixture'})

def state(store):
    keys, matrix=store.all_vectors('chunks')
    return dict(rows=sorted(store.select('chunks'),key=lambda r:r['chunk_id']),vectors={k[0]:v.tolist() for k,v in sorted(zip(keys,matrix),key=lambda pair:pair[0])},search=[list(k)+[score] for k,score in store.search('chunks',np.array([1,0,0,0],dtype=np.float32),10)])

results=[]
for change in ('delete','insert'):
    for condition in ('file-deferred','file-flushed','memory'):
        path=':memory:' if condition=='memory' else str(WORK/f'{change}-{condition}.db')
        store=SQLiteStore(path,dim=4)
        started=time.monotonic()
        with store.transaction():
            put(store,'original',[1,0,0,0])
        store.flush()
        with store.transaction():
            if change=='delete': store.delete('chunks',('original',))
            else: put(store,'committed-new',[0,1,0,0])
        if condition=='file-flushed': store.flush()
        before=state(store)
        aborted=False
        try:
            with store.transaction():
                put(store,'temporary',[0,0,1,0])
                raise RuntimeError('Authored rollback control')
        except RuntimeError as exc:
            assert str(exc)=='Authored rollback control'
            aborted=True
        after=state(store)
        elapsed=time.monotonic()-started
        assert elapsed<30, 'Deferred-flush window not established'
        assert aborted and store.get('chunks',('temporary',)) is None
        assert store.get_vector('chunks',('temporary',)) is None
        store.close()
        reopened=None
        if condition!='memory':
            second=SQLiteStore(path,dim=4)
            reopened=state(second)
            second.close()
        results.append(dict(change=change,condition=condition,autosave_interval_s=30.0,elapsed_seconds=elapsed,before_abort=before,after_abort=after,rows_preserved=before['rows']==after['rows'],vectors_preserved=before['vectors']==after['vectors'],search_preserved=before['search']==after['search'],after_reopen=reopened))
assert source_hashes=={p.relative_to(SOURCE).as_posix():sha(p) for p in SOURCE.rglob('*.py')}
assert sha(PROTOCOL)==protocol_hash
receipt=dict(date='2026-11-21',protocol_sha256=protocol_hash,pin='fbba969e73eaeaf45e1e8a8ad33a96cfeadbb66d',python=platform.python_version(),numpy=np.__version__,source_hashes=source_hashes,source_unchanged=True,conditions=results,new_model_calls=0,independent_validation=False,scope='Native synthetic storage controls; no full RAG query, crash or physical-erasure claim')
out=ROOT/'results/lightfoot_rollback_controls_20261121.json'
out.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps([dict(change=x['change'],condition=x['condition'],rows_preserved=x['rows_preserved'],vectors_preserved=x['vectors_preserved'],search_preserved=x['search_preserved']) for x in results],indent=2))
