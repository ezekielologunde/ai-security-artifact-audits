"""Native lifecycle/retrieval boundary with explicit synthetic model substitution."""
from pathlib import Path
import hashlib
import json
import platform
import sqlite3
import sys
import time

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'data/lightfoot-qualification-20261121'
PROTOCOL=ROOT/'LIGHTFOOT_NATIVE_BOUNDARY_PROTOCOL_20261121.json'
WORK=ROOT/'work/lightfoot-native-boundary-v1'
WORK.mkdir(parents=True,exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source_hashes={p.relative_to(SOURCE).as_posix():sha(p) for p in SOURCE.rglob('*.py')}
protocol_hash=sha(PROTOCOL)
sys.dont_write_bytecode=True
sys.path.insert(0,str(SOURCE))
import numpy as np
from lightfoot import Lightfoot, LightfootConfig
from lightfoot.store import SQLiteStore

class FixtureEmbedding:
    dim=4
    def encode(self,texts,show_progress=False):
        return np.array([self.encode_one(t) for t in texts],dtype=np.float32).reshape((-1,4))
    def encode_one(self,text):
        text=text.lower()
        if 'retiredviolet' in text or 'canaryalpha' in text: v=[1,0,0,0]
        elif 'survivinggreen' in text or 'utilitybeta' in text:v=[0,1,0,0]
        else:v=[0,0,0,1]
        return np.array(v,dtype=np.float32)
    def encode_names(self,texts):return self.encode(texts)
    def encode_query(self,text):return self.encode_one(text)

protocol=json.loads(PROTOCOL.read_text(encoding='utf-8'))
docs=protocol['fixtures']
questions=protocol['queries']

def vector_state(store):
    ids,matrix=store.all_vectors('chunks')
    return {k[0]:v.tolist() for k,v in sorted(zip(ids,matrix),key=lambda x:x[0])}

def inspect(lf,retired_id,survivor_id):
    queries=[]
    for question in questions:
        res=lf.query(question,answer=False)
        queries.append(dict(question=question,ranked_chunk_ids=res.ranked_chunk_ids,context=res.context,context_chunk_ids=res.retrieval.context_graph_ids,dense_seed_ids=list(lf.retriever.last_trace['dense']),retired_id_ranked=retired_id in res.ranked_chunk_ids,survivor_id_ranked=survivor_id in res.ranked_chunk_ids,retired_text_in_context=docs[0]['text'] in res.context,survivor_text_in_context=docs[1]['text'] in res.context,answer_generation_performed=False))
    record=dict(sql_chunks=lf.store.select('chunks'),vectors=vector_state(lf.store),graph_fingerprint=lf.graph_fingerprint(),counts=lf.counts(),queries=queries)
    if lf.store.path!=':memory:':
        path=Path(lf.store.path)
        con=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
        try:record['read_only_sql_chunks']=con.execute('SELECT chunk_id,doc_id,text FROM chunks ORDER BY chunk_id').fetchall()
        finally:con.close()
        npz=Path(str(path)+'.vec')/'chunks.npz'
        before=sha(npz)
        with np.load(npz,allow_pickle=True) as data:
            record['on_disk_vectors']={str(k):v.tolist() for k,v in zip(data['ids'],data['matrix'])}
        assert sha(npz)==before
        record['on_disk_vector_sha256']=before
    return record

results=[]
for condition in ('file-deferred','file-flushed','memory'):
    folder=WORK/condition
    folder.mkdir()
    path=':memory:' if condition=='memory' else str(folder/'store.db')
    cfg=LightfootConfig(mock=True,reranker_model='off',enable_decomposition=False,query_trace=False,cache_dir=str(folder/'cache'))
    store=SQLiteStore(path,dim=4)
    lf=Lightfoot(store,cfg,embedder=FixtureEmbedding())
    lf.index_documents(docs)
    store.flush()
    ids={r['doc_id']:r['chunk_id'] for r in store.select('chunks')}
    assert set(ids)=={'retired','survivor'}
    initial=inspect(lf,ids['retired'],ids['survivor'])
    assert initial['queries'][0]['retired_text_in_context']
    assert initial['queries'][1]['survivor_text_in_context']
    started=time.monotonic()
    before_calls=len(lf.costs.records)
    lf.delete_documents(['retired'])
    assert len(lf.costs.records)==before_calls
    if condition=='file-flushed':store.flush()
    after_delete=inspect(lf,ids['retired'],ids['survivor'])
    assert store.get('chunks',(ids['retired'],)) is None
    assert not any(q['retired_text_in_context'] for q in after_delete['queries'])
    try:
        with store.transaction():
            store.put('chunks',dict(chunk_id='temporary',doc_id='temporary',tenant=cfg.tenant,ordinal=0,text='temporary inert record',tokens=3))
            store.set_vector('chunks',('temporary',),np.array([0,0,1,0],dtype=np.float32),attrs={'tenant':cfg.tenant})
            raise RuntimeError('Authored pipeline rollback control')
    except RuntimeError as exc:
        assert str(exc)=='Authored pipeline rollback control'
    assert store.get('chunks',('temporary',)) is None and store.get_vector('chunks',('temporary',)) is None
    after_abort=inspect(lf,ids['retired'],ids['survivor'])
    elapsed=time.monotonic()-started
    assert elapsed<30
    store.close()
    after_reopen=None
    if condition!='memory':
        second=SQLiteStore(path,dim=4)
        reopened=Lightfoot(second,cfg,embedder=FixtureEmbedding())
        after_reopen=inspect(reopened,ids['retired'],ids['survivor'])
        second.close()
    results.append(dict(condition=condition,ids=ids,elapsed_seconds=elapsed,initial=initial,after_delete=after_delete,after_abort=after_abort,after_reopen=after_reopen,native_deletion_model_calls=0))
assert source_hashes=={p.relative_to(SOURCE).as_posix():sha(p) for p in SOURCE.rglob('*.py')}
assert sha(PROTOCOL)==protocol_hash
receipt=dict(date='2026-11-21',pin='fbba969e73eaeaf45e1e8a8ad33a96cfeadbb66d',protocol_sha256=protocol_hash,python=platform.python_version(),numpy=np.__version__,embedding='Authored deterministic stand-in through supported public parameter; not a learned model',source_hashes=source_hashes,source_unchanged=True,conditions=results,new_hosted_model_calls=0,independent_review_complete=False)
(ROOT/'results/lightfoot_native_boundary_20261121.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps([dict(condition=r['condition'],retired_vector_returns=r['ids']['retired'] in r['after_abort']['vectors'],queries=[dict(question=q['question'],stale_id_ranked=q['retired_id_ranked'],deleted_text_in_context=q['retired_text_in_context'],surviving_text_in_context=q['survivor_text_in_context']) for q in r['after_abort']['queries']]) for r in results],indent=2))
