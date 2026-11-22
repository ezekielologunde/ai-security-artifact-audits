"""The provenance ledger (design sections 3 and 5).

Every entity, alias, mention, fact, fact_source and synonym row carries `prov`,
a dict chunk_id -> count. A row exists iff its prov is non-empty.

- `upsert_batch` / `upsert_chunk_extraction` increment provenance for everything
  a batch of chunks produced, in one transaction with executemany writes.
- `delete_document` / `delete_chunks` remove the chunks' contribution and drop
  zero-provenance rows in the order mentions, fact_sources, aliases, facts,
  entities, synonyms; zero model calls, one transaction.
- `graph_fingerprint` hashes all surviving nodes and edges by content (names,
  not ids) so index(A,B) then delete(B) can be compared with index(A).

The ground truth is the surface ledger: `forms` (one row per chunk and surface form, with
the chunk's description) and `form_links` (same-entity edges between two forms, decided by
the name cosine and the cached judge; a function of the two forms only). Entities, aliases
and mentions are derived: an entity is a connected component of linked forms, its id comes
from its smallest form, its canonical name is the alias with the most provenance (ties
broken lexicographically). Facts are keyed by their surface forms, so a merge or split only
re-points their entity ids. Alias embeddings are stored so a canonical name can revert on
delete without an embedding call. Synonym edges are all entity pairs above the cosine
threshold, so they depend on the live entity set only.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np

from .chunking import Chunk
from .config import LightfootConfig
from .extract import Extraction
from .resolve import (ResolvedEntity, EntityNameIndex, FormIndex, Resolution, canonical_score, component_id,
                      components, form_key, split_form)
from .store.base import Store, DELETE_ORDER


@dataclass
class Touched:
    """Nodes whose graph edges must be refreshed after an upsert or delete."""
    chunk_ids: Set[str] = field(default_factory=set)
    entity_ids: Set[str] = field(default_factory=set)
    fact_ids: Set[str] = field(default_factory=set)
    removed_entity_ids: Set[str] = field(default_factory=set)
    removed_fact_ids: Set[str] = field(default_factory=set)
    removed_chunk_ids: Set[str] = field(default_factory=set)
    removed_rows: Dict[str, int] = field(default_factory=dict)

    def merge(self, other: "Touched") -> "Touched":
        """Fold in a later change set: a node removed earlier and re-created later (or vice versa) ends in the later state."""
        self.entity_ids -= other.removed_entity_ids
        self.removed_entity_ids -= other.entity_ids
        self.fact_ids -= other.removed_fact_ids
        self.removed_fact_ids -= other.fact_ids
        self.chunk_ids -= other.removed_chunk_ids
        self.removed_chunk_ids -= other.chunk_ids
        self.chunk_ids |= other.chunk_ids
        self.entity_ids |= other.entity_ids
        self.fact_ids |= other.fact_ids
        self.removed_entity_ids |= other.removed_entity_ids
        self.removed_fact_ids |= other.removed_fact_ids
        self.removed_chunk_ids |= other.removed_chunk_ids
        for k, v in other.removed_rows.items():
            self.removed_rows[k] = self.removed_rows.get(k, 0) + v
        return self


@dataclass
class ChunkItem:
    """One chunk's contribution to a batch upsert."""
    chunk: Chunk
    extraction: Extraction
    fact_embeddings: Optional[np.ndarray] = None   # one row per extraction.facts entry
    chunk_embedding: Optional[np.ndarray] = None


def make_fact_id(subject_id: str, predicate: str, object_id: str, sentence: str) -> str:
    return hashlib.sha256(f"{subject_id}\x00{predicate}\x00{object_id}\x00{sentence}".encode("utf-8")).hexdigest()[:24]


def norm_predicate(p: str) -> str:
    return " ".join(p.strip().lower().split())


def _merge_prov(a: Optional[Dict[str, int]], b: Dict[str, int]) -> Dict[str, int]:
    out = dict(a or {})
    for c, n in b.items():
        out[c] = out.get(c, 0) + n
    return out


_KEYS = {
    "mentions": ("chunk_id", "entity_id"), "fact_sources": ("fact_id", "chunk_id"), "aliases": ("alias_text", "entity_id"),
    "facts": ("fact_id",), "entities": ("entity_id",), "synonyms": ("entity_a", "entity_b"), "forms": ("chunk_id", "form"),
}


class Ledger:
    def __init__(self, store: Store, config: LightfootConfig, name_index: Optional[EntityNameIndex] = None,
                 form_index: Optional[FormIndex] = None) -> None:
        self.store = store
        self.config = config
        self.name_index = name_index if name_index is not None else EntityNameIndex.load(store, config.tenant, store.dim)
        self.form_index = form_index if form_index is not None else FormIndex.load(store, config.tenant, store.dim)

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------
    def upsert_chunk_extraction(self, chunk: Chunk, extraction: Extraction,
                                resolution: Dict[Tuple[str, str], ResolvedEntity],
                                name_embeddings: Dict[str, np.ndarray],
                                fact_embeddings: Optional[np.ndarray] = None,
                                chunk_embedding: Optional[np.ndarray] = None) -> Touched:
        """Single-chunk convenience wrapper around `upsert_batch`."""
        return self.upsert_batch([ChunkItem(chunk, extraction, fact_embeddings, chunk_embedding)], resolution, name_embeddings)

    def upsert_batch(self, items: Sequence[ChunkItem], resolution: Resolution,
                     name_embeddings: Dict[str, np.ndarray]) -> Touched:
        """Write the batch's surface forms, links and facts, then rebuild every entity component the batch touched.
        One transaction, executemany writes.

        resolution: Resolver.resolve output for the batch's candidates.
        name_embeddings: surface form -> vector (kept for interface compatibility; vectors come from `resolution`).
        """
        st = self.store
        cfg = self.config
        tenant = cfg.tenant
        fi = self.form_index
        touched = Touched()
        if not items:
            return touched

        chunk_rows: List[Dict] = []
        chunk_keys: List[Tuple] = []
        chunk_vecs: List[np.ndarray] = []
        form_acc: Dict[Tuple[str, str], Dict] = {}
        fact_acc: Dict[str, Tuple[Dict, Dict[str, int], Optional[np.ndarray]]] = {}
        src_acc: Dict[Tuple[str, str], Tuple[str, Dict[str, int]]] = {}

        for it in items:
            ch, ex = it.chunk, it.extraction
            cid = ch.chunk_id
            touched.chunk_ids.add(cid)
            chunk_rows.append({"chunk_id": cid, "doc_id": ch.doc_id, "tenant": tenant, "ordinal": ch.ordinal,
                               "text": ch.text, "tokens": ch.tokens})
            if it.chunk_embedding is not None:
                chunk_keys.append((cid,))
                chunk_vecs.append(it.chunk_embedding)
            # the first occurrence of a name in the chunk defines its surface form (same rule as the resolver)
            name_form: Dict[str, str] = {}
            for k, e in enumerate(ex.entities):
                if e.name in name_form:
                    continue
                if (cid, e.name) not in resolution:
                    continue
                f = form_key(e.type, e.name)
                name_form[e.name] = f
                form_acc[(cid, f)] = {"chunk_id": cid, "form": f, "tenant": tenant, "type": e.type, "name": e.name,
                                      "description": e.description or "", "ord": k, "prov": {cid: 1}}
            for i, fc in enumerate(ex.facts):
                sf, of = name_form.get(fc.subject), name_form.get(fc.object)
                if not sf or not of:
                    continue
                pred = norm_predicate(fc.predicate)
                fid = make_fact_id(sf, pred, of, fc.sentence)
                row, prov, vec = fact_acc.get(fid, (None, {}, None))
                if row is None:
                    row = {"fact_id": fid, "tenant": tenant, "subject_entity_id": "", "predicate": pred,
                           "object_entity_id": "", "sentence": fc.sentence, "prov": {},
                           "subject_form": sf, "object_form": of}
                    if it.fact_embeddings is not None and i < len(it.fact_embeddings):
                        vec = it.fact_embeddings[i]
                prov = dict(prov)
                prov[cid] = prov.get(cid, 0) + 1
                fact_acc[fid] = (row, prov, vec)
                sk = (fid, cid)
                ev, sprov = src_acc.get(sk, (fc.evidence_span, {}))
                sprov = dict(sprov)
                sprov[cid] = sprov.get(cid, 0) + 1
                src_acc[sk] = (ev, sprov)
                touched.fact_ids.add(fid)

        with st.transaction():
            st.put_many("chunks", chunk_rows)
            if chunk_keys:
                st.set_vectors("chunks", chunk_keys, np.stack(chunk_vecs), [{"tenant": tenant}] * len(chunk_keys))

            # surface forms, links, new form vectors -------------------------
            existing = {(r["chunk_id"], r["form"]): r
                        for r in st.select("forms", {"chunk_id": sorted({k[0] for k in form_acc})})} if form_acc else {}
            to_put = []
            for key in sorted(form_acc):
                row = form_acc[key]
                old = existing.get(key)
                if old is not None:
                    old["prov"] = _merge_prov(old["prov"], row["prov"])
                    row = old
                to_put.append(row)
            st.put_many("forms", to_put)
            st.put_many("form_links", [{"form_a": a, "form_b": b, "tenant": tenant, "type": t, "score": float(s), "kind": kd}
                                       for a, b, t, s, kd in getattr(resolution, "links", [])])
            new_forms = getattr(resolution, "new_forms", {})
            nf = sorted(f for f in new_forms if fi.get(f) is None)
            if nf:
                fi.upsert_many(nf, [split_form(f)[0] for f in nf], np.stack([new_forms[f] for f in nf]))

            # entity components touched by the batch -------------------------
            comps: Dict[str, Set[str]] = {}
            old_ids: Set[str] = set()
            for eid, (_, members, old) in getattr(resolution, "groups", {}).items():
                comps[eid] = set(members)
                old_ids |= old
            alive, removed = self._rebuild(old_ids, comps, touched)

            # facts and sources ---------------------------------------------
            fids = sorted(fact_acc)
            existing_f = {f["fact_id"]: f for f in st.select("facts", {"fact_id": fids})} if fids else {}
            to_put, fkeys, fvecs = [], [], []
            for fid in fids:
                row, inc, vec = fact_acc[fid]
                f = existing_f.get(fid)
                if f is None:
                    f = row
                    if vec is not None:
                        fkeys.append((fid,))
                        fvecs.append(vec)
                f["prov"] = _merge_prov(f["prov"], inc)
                f["subject_entity_id"] = fi.owner.get(f["subject_form"], f["subject_entity_id"])
                f["object_entity_id"] = fi.owner.get(f["object_form"], f["object_entity_id"])
                to_put.append(f)
            st.put_many("facts", to_put)
            if fkeys:
                st.set_vectors("facts", fkeys, np.stack(fvecs), [{"tenant": tenant}] * len(fkeys))
            skeys = sorted(src_acc)
            existing_s = {(s["fact_id"], s["chunk_id"]): s for s in st.select("fact_sources", {"fact_id": fids})} if fids else {}
            to_put = []
            for sk in skeys:
                ev, inc = src_acc[sk]
                s_row = existing_s.get(sk) or {"fact_id": sk[0], "chunk_id": sk[1], "evidence_span": ev, "prov": {}}
                s_row["prov"] = _merge_prov(s_row["prov"], inc)
                to_put.append(s_row)
            st.put_many("fact_sources", to_put)

            # derived state -----------------------------------------------------
            self._refresh_fact_endpoints(old_ids, touched)
            self._recompute_synonyms(alive, removed, touched)
        return touched

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------
    def delete_document(self, doc_id: str) -> Touched:
        st = self.store
        with st.transaction():
            chunks = st.select("chunks", {"doc_id": doc_id})
            touched = self.delete_chunks([c["chunk_id"] for c in chunks])
            st.delete("documents", (doc_id,))
        return touched

    def delete_chunks(self, chunk_ids: Sequence[str]) -> Touched:
        """Remove the contribution of `chunk_ids`. Zero model calls, one transaction.

        Surface forms, facts and fact sources lose the chunks' provenance (rows at zero are dropped). A form that
        no longer occurs anywhere is dropped with its links, and every entity that owned an affected form is
        recomputed as the connected components of its surviving forms under the stored links: exactly the
        partition a fresh index of the surviving documents produces, since links depend only on their two forms."""
        st = self.store
        fi = self.form_index
        tenant = self.config.tenant
        touched = Touched()
        chunk_ids = list(dict.fromkeys(chunk_ids))
        if not chunk_ids:
            return touched
        gone = set(chunk_ids)
        with st.transaction():
            affected_forms: Set[str] = set()
            for table in ("forms", "fact_sources", "facts"):
                keys = _KEYS[table]
                rows: Dict[Tuple, Dict] = {}
                for cid in chunk_ids:
                    for row in st.rows_with_prov(table, cid):
                        rows.setdefault(tuple(row[k] for k in keys), row)
                keep, drop = [], []
                for key, row in rows.items():
                    if table == "forms":
                        affected_forms.add(row["form"])
                    prov = {c: n for c, n in (row["prov"] or {}).items() if c not in gone}
                    if prov:
                        row["prov"] = prov
                        keep.append(row)
                        if table == "facts":
                            touched.fact_ids.add(row["fact_id"])
                    else:
                        drop.append(key)
                        if table == "facts":
                            touched.removed_fact_ids.add(row["fact_id"])
                st.put_many(table, keep)
                st.delete_many(table, drop)
                if drop:
                    touched.removed_rows[table] = touched.removed_rows.get(table, 0) + len(drop)

            live_forms = {r["form"] for r in st.select("forms", {"form": sorted(affected_forms)})} if affected_forms else set()
            dead = affected_forms - live_forms
            old_ids = {fi.owner[f] for f in affected_forms if f in fi.owner}
            comps: Dict[str, Set[str]] = {}
            for eid in sorted(old_ids):
                members = fi.members.get(eid, set()) - dead
                if not members:
                    continue
                lk = st.select("form_links", {"form_a": sorted(members)})
                edges = [(l["form_a"], l["form_b"]) for l in lk if l["form_b"] in members]
                for comp in components(sorted(members), edges):
                    comps[component_id(tenant, comp)] = comp
            if dead:
                dl = st.select("form_links", {"form_a": sorted(dead)}) + st.select("form_links", {"form_b": sorted(dead)})
                dk = sorted({(l["form_a"], l["form_b"]) for l in dl})
                st.delete_many("form_links", dk)
                if dk:
                    touched.removed_rows["form_links"] = touched.removed_rows.get("form_links", 0) + len(dk)
                for f in dead:
                    fi.drop_form(f)
            alive, removed = self._rebuild(old_ids, comps, touched)
            self._refresh_fact_endpoints(old_ids, touched)
            self._recompute_synonyms(alive, removed, touched)
            # topic cache invalidation
            for row in st.select("topic_cache"):
                if set(row.get("chunk_ids") or []) & gone:
                    st.delete("topic_cache", (row["topic_key"],))
            # chunks last
            st.delete_many("chunks", [(c,) for c in chunk_ids])
            touched.removed_chunk_ids |= gone
        return touched

    # ------------------------------------------------------------------
    # Derived state (batched)
    # ------------------------------------------------------------------
    def _rebuild(self, old_ids: Set[str], comps: Dict[str, Set[str]], touched: Touched) -> Tuple[Set[str], Set[str]]:
        """Replace the entities `old_ids` by the components `comps` (entity id -> member forms), deriving entity,
        alias and mention rows from the surface-form rows. Canonical name = alias with max total provenance, ties
        lexicographic; the entity name vector is that alias's vector. Returns (live ids written, ids removed)."""
        st = self.store
        fi = self.form_index
        tenant = self.config.tenant
        old = sorted(old_ids)
        if old:
            al = st.select("aliases", {"entity_id": old})
            st.delete_many("aliases", [(a["alias_text"], a["entity_id"]) for a in al])
            me = st.select("mentions", {"entity_id": old})
            st.delete_many("mentions", [(m["chunk_id"], m["entity_id"]) for m in me])
            for e in old:
                fi.drop_entity(e)
        all_forms = sorted(set().union(*comps.values())) if comps else []
        by_form: Dict[str, List[Dict]] = {}
        for r in (st.select("forms", {"form": all_forms}) if all_forms else []):
            by_form.setdefault(r["form"], []).append(r)
        ent_rows: List[Dict] = []
        ent_vecs: List[np.ndarray] = []
        ent_attrs: List[Dict] = []
        alias_rows: List[Dict] = []
        alias_keys: List[Tuple] = []
        alias_vecs: List[np.ndarray] = []
        mention_rows: List[Dict] = []
        alive: Set[str] = set()
        for eid in sorted(comps):
            live = sorted(f for f in comps[eid] if f in by_form)
            for f in comps[eid]:
                if f not in by_form:
                    fi.drop_form(f)
            if not live:
                continue
            etype = split_form(live[0])[0]
            eprov: Dict[str, int] = {}
            aprov: Dict[str, Dict[str, int]] = {}
            macc: Dict[str, List] = {}
            for f in live:
                name = split_form(f)[1]
                for r in by_form[f]:
                    p = r["prov"] or {}
                    aprov[name] = _merge_prov(aprov.get(name), p)
                    eprov = _merge_prov(eprov, p)
                    m = macc.setdefault(r["chunk_id"], [{}, None])
                    m[0] = _merge_prov(m[0], p)
                    if r.get("description"):
                        cand = (int(r.get("ord") or 0), r["description"])
                        if m[1] is None or cand < m[1]:
                            m[1] = cand
            canonical = min(aprov, key=lambda n: (-sum(aprov[n].values()), n))
            ent_rows.append({"entity_id": eid, "tenant": tenant, "canonical_name": canonical, "type": etype, "prov": eprov})
            v = fi.get(form_key(etype, canonical))
            if v is not None:
                ent_vecs.append(np.array(v))
                ent_attrs.append({"tenant": tenant, "type": etype})
            for name in sorted(aprov):
                alias_rows.append({"alias_text": name, "entity_id": eid, "tenant": tenant, "prov": aprov[name]})
                av = fi.get(form_key(etype, name))
                if av is not None:
                    alias_keys.append((name, eid))
                    alias_vecs.append(np.array(av))
            for c in sorted(macc):
                prov, best = macc[c]
                mention_rows.append({"chunk_id": c, "entity_id": eid, "description": best[1] if best else "", "prov": prov})
            fi.assign(eid, live)
            alive.add(eid)
        removed = set(old) - alive
        st.delete_many("entities", [(e,) for e in sorted(removed)])
        for e in removed:
            self.name_index.remove(e)
        st.put_many("entities", ent_rows)
        with_vec = [r for r in ent_rows if fi.get(form_key(r["type"], r["canonical_name"])) is not None]
        if with_vec:
            mat = np.stack(ent_vecs)
            st.set_vectors("entities", [(r["entity_id"],) for r in with_vec], mat, ent_attrs)
            self.name_index.upsert_many([r["entity_id"] for r in with_vec], [r["type"] for r in with_vec], mat)
        st.put_many("aliases", alias_rows)
        if alias_keys:
            st.set_vectors("aliases", alias_keys, np.stack(alias_vecs), [{"tenant": tenant}] * len(alias_keys))
        st.put_many("mentions", mention_rows)
        if removed:
            touched.removed_rows["entities"] = touched.removed_rows.get("entities", 0) + len(removed)
        touched.entity_ids -= removed
        touched.removed_entity_ids -= alive
        touched.entity_ids |= alive
        touched.removed_entity_ids |= removed
        return alive, removed

    def _refresh_fact_endpoints(self, old_ids: Set[str], touched: Touched) -> None:
        """Facts are keyed by surface forms; their entity ids follow the forms' current entities."""
        st = self.store
        fi = self.form_index
        ids = sorted(old_ids)
        if not ids:
            return
        seen: Set[str] = set()
        put: List[Dict] = []
        for f in st.select("facts", {"subject_entity_id": ids}) + st.select("facts", {"object_entity_id": ids}):
            if f["fact_id"] in seen:
                continue
            seen.add(f["fact_id"])
            s, o = fi.owner.get(f.get("subject_form") or ""), fi.owner.get(f.get("object_form") or "")
            if s is None or o is None:
                continue
            if (s, o) != (f["subject_entity_id"], f["object_entity_id"]):
                f["subject_entity_id"], f["object_entity_id"] = s, o
                put.append(f)
                touched.fact_ids.add(f["fact_id"])
        st.put_many("facts", put)

    def _recompute_synonyms(self, changed: Set[str], removed: Set[str], touched: Touched) -> None:
        """Synonym edges are derived: every entity pair whose name vectors have exact cosine >= synonym_threshold
        (no top-k cap, so the edge set is a function of the live entities only). prov = merged prov of both
        endpoints. All rows of the changed and removed entities are rebuilt."""
        st = self.store
        cfg = self.config
        ids = sorted(set(changed) | set(removed))
        if not ids:
            return
        old = st.select("synonyms", {"entity_a": ids}) + st.select("synonyms", {"entity_b": ids})
        old_keys = sorted({(r["entity_a"], r["entity_b"]) for r in old})
        st.delete_many("synonyms", old_keys)
        for a, b in old_keys:   # the other endpoint loses an edge
            for e in (a, b):
                if e not in removed:
                    touched.entity_ids.add(e)
        live = [e for e in sorted(changed) if self.name_index.get(e) is not None]
        if not live:
            return
        Q = np.stack([self.name_index.get(e) for e in live])
        pairs: Dict[Tuple[str, str], float] = {}
        for e, cands in zip(live, self.name_index.pairs_above(Q, cfg.synonym_threshold)):
            ve = self.name_index.get(e)
            for o in cands:
                if o == e:
                    continue
                key = (e, o) if e < o else (o, e)
                if key in pairs:
                    continue
                s = canonical_score(ve, self.name_index.get(o))
                if s >= cfg.synonym_threshold:
                    pairs[key] = s
        if not pairs:
            return
        involved = sorted({e for p in pairs for e in p})
        ents = {e["entity_id"]: e for e in st.select("entities", {"entity_id": involved})}
        rows = []
        for (a, b), score in sorted(pairs.items()):
            ea, eb = ents.get(a), ents.get(b)
            if ea is None or eb is None:
                continue
            rows.append({"entity_a": a, "entity_b": b, "tenant": cfg.tenant, "score": float(score),
                         "prov": _merge_prov(ea["prov"], eb["prov"] or {})})
            touched.entity_ids.add(a)
            touched.entity_ids.add(b)
        st.put_many("synonyms", rows)

    # ------------------------------------------------------------------
    # Fingerprint
    # ------------------------------------------------------------------
    def graph_fingerprint(self) -> str:
        """Deterministic content hash of all surviving nodes and edges, independent of ids."""
        st = self.store
        names: Dict[str, str] = {}
        ents = []
        for e in st.select("entities"):
            names[e["entity_id"]] = e["canonical_name"]
            ents.append([e["canonical_name"], e["type"], sorted((e["prov"] or {}).items())])
        aliases = [[a["alias_text"], names.get(a["entity_id"], "?"), sorted((a["prov"] or {}).items())] for a in st.select("aliases")]
        mentions = [[m["chunk_id"], names.get(m["entity_id"], "?"), m["description"], sorted((m["prov"] or {}).items())] for m in st.select("mentions")]
        fact_desc: Dict[str, list] = {}
        facts = []
        for f in st.select("facts"):
            d = [names.get(f["subject_entity_id"], "?"), f["predicate"], names.get(f["object_entity_id"], "?"), f["sentence"]]
            fact_desc[f["fact_id"]] = d
            facts.append(d + [sorted((f["prov"] or {}).items())])
        sources = [fact_desc.get(s["fact_id"], ["?"]) + [s["chunk_id"], s["evidence_span"], sorted((s["prov"] or {}).items())] for s in st.select("fact_sources")]
        syns = [sorted([names.get(s["entity_a"], "?"), names.get(s["entity_b"], "?")]) + [round(float(s["score"]), 4), sorted((s["prov"] or {}).items())] for s in st.select("synonyms")]
        chunks = [[c["chunk_id"], c["doc_id"], c["ordinal"]] for c in st.select("chunks")]
        forms = [[r["chunk_id"], r["form"], r["description"], r["ord"], sorted((r["prov"] or {}).items())] for r in st.select("forms")]
        links = [[l["form_a"], l["form_b"], round(float(l["score"]), 4), l["kind"]] for l in st.select("form_links")]
        payload = {
            "forms": sorted(forms, key=json.dumps), "form_links": sorted(links, key=json.dumps),
            "entities": sorted(ents, key=json.dumps), "aliases": sorted(aliases, key=json.dumps),
            "mentions": sorted(mentions, key=json.dumps), "facts": sorted(facts, key=json.dumps),
            "fact_sources": sorted(sources, key=json.dumps), "synonyms": sorted(syns, key=json.dumps),
            "chunks": sorted(chunks, key=json.dumps),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    def counts(self) -> Dict[str, int]:
        return {t: self.store.count(t) for t in ("documents", "chunks", "entities", "aliases", "mentions", "facts", "fact_sources", "synonyms", "forms", "form_links")}
