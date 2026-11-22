"""Test 2: THE ERASURE TEST. index(A, B) then delete(B) == index(A), with zero model calls on delete."""
from lightfoot import Lightfoot, LightfootConfig
from lightfoot.store import SQLiteStore
from synthetic_docs import DOCS

A = DOCS[:6]
B = DOCS[6:12]


def _fresh(embedder, reranker, tmp_cache, path):
    cfg = LightfootConfig(mock=True, cache_dir=tmp_cache)
    store = SQLiteStore(path, dim=embedder.dim)
    return Lightfoot(store, cfg, embedder=embedder, reranker=reranker)


def test_erasure(embedder, reranker, tmp_cache, tmp_path):
    lf_a = _fresh(embedder, reranker, tmp_cache, str(tmp_path / "a.db"))
    lf_a.index_documents(A)
    fp_a = lf_a.graph_fingerprint()
    counts_a = lf_a.counts()

    lf_ab = _fresh(embedder, reranker, tmp_cache, str(tmp_path / "ab.db"))
    lf_ab.index_documents(A)
    lf_ab.index_documents(B)
    fp_ab = lf_ab.graph_fingerprint()
    assert fp_ab != fp_a
    assert lf_ab.counts()["chunks"] == 12
    # touch the topic cache so delete must invalidate it
    lf_ab.query("What are the overall themes across these companies?")
    assert lf_ab.store.count("topic_cache") > 0

    n_before = len(lf_ab.costs.records)
    touched = lf_ab.delete_documents([d["doc_id"] for d in B])
    assert len(lf_ab.costs.records) == n_before, "delete made model calls"
    assert touched.removed_chunk_ids == {c["chunk_id"] for c in []} or len(touched.removed_chunk_ids) == 6

    assert lf_ab.counts() == counts_a
    assert lf_ab.graph_fingerprint() == fp_a
    assert lf_ab.store.count("topic_cache") == 0
    # the in-memory graph matches a fresh rebuild
    assert lf_ab.graph.num_nodes == lf_a.graph.num_nodes
    assert lf_ab.graph.num_edges == lf_a.graph.num_edges

    # deleting everything leaves an empty ledger
    lf_ab.delete_documents([d["doc_id"] for d in A])
    assert all(v == 0 for v in lf_ab.counts().values())
    assert lf_ab.graph.num_nodes == 0


def test_erasure_with_facts_and_shared_entities(embedder, reranker, tmp_cache, tmp_path):
    """Hand-built extractions with facts: shared entities survive with reduced provenance."""
    from lightfoot.chunking import Chunk, chunk_id_for
    from lightfoot.extract import Extraction, ExtractedEntity, ExtractedFact
    from lightfoot.resolve import Candidate

    def ex_for(doc):
        if doc == "A":
            return Extraction(
                entities=[ExtractedEntity("Acme Corp", "ORGANIZATION", "A maker of anvils."),
                          ExtractedEntity("Wile Coyote", "PERSON", "A customer of Acme.")],
                facts=[ExtractedFact("Wile Coyote", "buys from", "Acme Corp", "Wile Coyote buys anvils from Acme Corp.", "buys anvils from Acme")])
        return Extraction(
            entities=[ExtractedEntity("Acme Corporation", "ORGANIZATION", "The anvil company."),
                      ExtractedEntity("Road Runner", "PERSON", "A fast bird.")],
            facts=[ExtractedFact("Acme Corporation", "sued by", "Road Runner", "Acme Corporation was sued by Road Runner.", "sued by Road Runner")])

    def run(docs):
        cfg = LightfootConfig(mock=True, cache_dir=tmp_cache)
        store = SQLiteStore(":memory:", dim=embedder.dim)
        lf = Lightfoot(store, cfg, embedder=embedder, reranker=reranker)
        for d in docs:
            text = f"Document {d}."
            ch = Chunk(chunk_id_for(d, text), d, 0, text, 3)
            ex = ex_for(d)
            names = [e.name for e in ex.entities]
            vecs = dict(zip(names, embedder.encode(names)))
            cands = [Candidate(ch.chunk_id, e.name, e.type, e.description, vecs[e.name]) for e in ex.entities]
            resolution = lf.resolver.resolve(cands)
            fe = embedder.encode([f.embed_text() for f in ex.facts])
            with store.transaction():
                store.put("documents", {"doc_id": d, "content_hash": d, "tenant": cfg.tenant, "metadata": {}, "created_at": 0})
                t = lf.ledger.upsert_chunk_extraction(ch, ex, resolution, vecs, fe, embedder.encode_one(text))
            lf._apply_touched(t)
        return lf

    lf_a = run(["A"])
    lf_ab = run(["A", "B"])
    assert lf_ab.counts()["facts"] == 2
    # "Acme Corporation" should have merged into "Acme Corp" (auto band or judge band)
    assert lf_ab.counts()["entities"] == 3, lf_ab.counts()
    n = len(lf_ab.costs.records)
    lf_ab.delete_documents(["B"])
    assert len(lf_ab.costs.records) == n
    assert lf_ab.counts() == lf_a.counts()
    assert lf_ab.graph_fingerprint() == lf_a.graph_fingerprint()
    assert lf_ab.graph.num_edges == lf_a.graph.num_edges
