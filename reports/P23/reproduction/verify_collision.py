"""Boundary and integration checks for the controlled ingestion finding."""
import dataclasses,json,unittest
from collision_experiment import ROOT,run_case,ImmutableIdStore,ProvenanceDatastore,Ed25519Signer,Chunk,ingest,revoke_source,inconsistencies
from ragtrap.gate import chunk_text,sign_chunk
from immutable_store import IndexConsistentUpsertStore
class CollisionChecks(unittest.TestCase):
    def test_posthoc_upsert(self):
        for same_principal in [False,True]:
            for same_text in [False,True]:
                result=run_case(IndexConsistentUpsertStore,True,same_principal,same_text)
                self.assertFalse(result['second_ingestion_rejected']);self.assertFalse(result['before_revocation']['principal_index_mismatches']);self.assertFalse(result['before_revocation']['hash_index_mismatches']);self.assertTrue(result['old_content_lookup_hash_matches_or_unknown']);self.assertEqual(result['current_other_source_false_purges'],[])
    def test_original_counterexample_with_valid_signatures(self):
        result=run_case(ProvenanceDatastore,True,False,False)
        self.assertTrue(result['live_signatures_valid_before_revocation']);self.assertEqual(result['signature_verification_failures'],[])
        self.assertEqual(len(result['current_other_source_false_purges']),1);self.assertFalse(result['old_content_lookup_hash_matches_or_unknown'])
    def test_versioned_id_control(self):
        for cls in [ProvenanceDatastore,ImmutableIdStore]:
            result=run_case(cls,False,False,False);self.assertFalse(result['second_ingestion_rejected']);self.assertEqual(result['remaining_records'],1);self.assertEqual(result['current_other_source_false_purges'],[])
    def test_reject_without_mutation(self):
        signer=Ed25519Signer.generate();store=ImmutableIdStore();chunk=Chunk('x','first','local://A','A')
        ingest([chunk],signer,datastore=store,detectors={});before=(dict(store.records),dict(store.chunks),{k:set(v) for k,v in store.by_principal.items()},{k:set(v) for k,v in store.by_content_hash.items()})
        with self.assertRaises(ValueError):ingest([dataclasses.replace(chunk,text='changed',principal='B')],signer,datastore=store,detectors={})
        self.assertEqual(before,(dict(store.records),dict(store.chunks),dict(store.by_principal),dict(store.by_content_hash)))
    def test_gate_generated_collision(self):
        signer=Ed25519Signer.generate();store=ProvenanceDatastore()
        for principal,text in [('A','first passage'),('B','second passage')]:
            chunks=chunk_text(text,chunk_chars=100,overlap=0,source_uri='local://'+principal,principal=principal,document_id='shared-doc')
            ingest(chunks,signer,datastore=store,detectors={})
        self.assertEqual(store.records['shared-doc::c0'].principal,'B')
        revoke_source(store,'A');self.assertNotIn('shared-doc::c0',store.records)
    def test_record_identity(self):
        signer=Ed25519Signer.generate();chunk=Chunk('x','first','local://A','A');record=sign_chunk(chunk,signer,{})
        for altered in [dataclasses.replace(record,principal='B'),dataclasses.replace(record,chunk_id='y'),dataclasses.replace(record,content_hash='0'*64)]:
            with self.assertRaises(ValueError):ImmutableIdStore().put(chunk,altered)
    def test_revoked_source_remains_denied(self):
        store=ImmutableIdStore();signer=Ed25519Signer.generate();revoke_source(store,'A')
        with self.assertRaises(ValueError):ingest([Chunk('x','text','local://A','A')],signer,datastore=store,detectors={})
    def test_matrix_preserves_unique_id_availability(self):
        matrix=json.loads((ROOT/'results/collision_matrix.json').read_text())
        for row in matrix['variants']['immutable_overlay']['cases']:
            self.assertEqual(row['second_ingestion_rejected'],row['same_id'])
            self.assertFalse(row['before_revocation']['principal_index_mismatches']);self.assertFalse(row['before_revocation']['hash_index_mismatches'])
if __name__=='__main__':
    run=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CollisionChecks))
    (ROOT/'results/collision_checks.json').write_text(json.dumps({'checks_run':run.testsRun,'passed':run.wasSuccessful(),'new_model_calls':0,'independent_human_review':False},indent=2),encoding='utf-8');raise SystemExit(0 if run.wasSuccessful() else 1)
