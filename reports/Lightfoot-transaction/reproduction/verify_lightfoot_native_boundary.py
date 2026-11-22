"""Check recorded native pipeline outputs against direct persisted-state readings."""
from pathlib import Path
import hashlib
import json
import sqlite3

ROOT=Path(__file__).resolve().parent
PATH=ROOT/'results/lightfoot_native_boundary_20261121.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before=sha(PATH)
data=json.loads(PATH.read_text(encoding='utf-8'))
post_queries=0
rows=[]
for case in data['conditions']:
    retired=case['ids']['retired']
    survivor=case['ids']['survivor']
    after_delete=case['after_delete']
    after_abort=case['after_abort']
    assert after_delete['sql_chunks']==after_abort['sql_chunks']
    assert after_delete['graph_fingerprint']==after_abort['graph_fingerprint']
    assert after_delete['counts']==after_abort['counts']
    for stage in ('after_delete','after_abort','after_reopen'):
        state=case[stage]
        if state is None:continue
        assert [r['chunk_id'] for r in state['sql_chunks']]==[survivor]
        for q in state['queries']:
            assert retired not in q['ranked_chunk_ids']
            assert not q['retired_text_in_context']
            assert q['survivor_text_in_context']
            assert q['context_chunk_ids']==[survivor]
            post_queries+=1
    direct=None
    if case['condition']!='memory':
        db=ROOT/'work/lightfoot-native-boundary-v1'/case['condition']/'store.db'
        con=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True)
        try:direct=con.execute('SELECT chunk_id,doc_id,text FROM chunks ORDER BY chunk_id').fetchall()
        finally:con.close()
        assert [list(row) for row in direct]==case['after_reopen']['read_only_sql_chunks']
        assert len(direct)==1 and direct[0][1]=='survivor'
    dense_stale=[retired in q['dense_seed_ids'] for q in after_abort['queries']]
    rows.append(dict(condition=case['condition'],retired_vector_returned=retired in after_abort['vectors'],stale_dense_seed_observations=sum(dense_stale),stale_final_rank_observations=sum(q['retired_id_ranked'] for q in after_abort['queries']),deleted_text_context_observations=sum(q['retired_text_in_context'] for q in after_abort['queries']),survivor_context_observations=sum(q['survivor_text_in_context'] for q in after_abort['queries']),same_sql_graph_and_counts_after_abort=True,direct_read_only_sql=direct))
assert sha(PATH)==before
receipt=dict(date='2026-11-21',native_receipt_sha256=before,conditions=rows,post_deletion_query_observations=post_queries,all_post_deletion_contexts_exclude_deleted_text=True,all_post_deletion_contexts_include_survivor=True,inputs_unchanged=True,independent_external_validation=False,scope='Read-only SQL corroboration plus recorded native pipeline outputs, with authored deterministic embeddings; no generated-answer or learned-model efficacy claim.')
(ROOT/'results/lightfoot_native_boundary_verification_20261121.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt,indent=2))
