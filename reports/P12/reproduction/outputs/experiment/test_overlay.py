import copy,pathlib,tempfile,unittest
from overlay import SQLiteStore,JSONStore,Authority,Overlay,artifact,audit_bytes,vector

class OverlayTests(unittest.TestCase):
    def exercise(self,cls,arm,event):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp);s=cls(path/'active');a=Authority(path/'authority.json');o=Overlay(s,a,arm)
            target=artifact('source','raw','secret controlled_marker_123',['X'])
            child=artifact('derived','summary','paraphrase controlled_marker_123',['X'],['source'])
            retained=artifact('retained','raw','Thursday meeting',['Y'])
            old=[target,child,retained];s.replace(old);o.rebuild_index();o.delete('X','source')
            if event=='commit':o.commit(target)
            if event=='restore':o.restore(old)
            if event=='rollback':a._write({});o.restore(old)
            if event=='bypass':o.commit(target,bypass=True)
            if event=='restart':o.restart()
            if event=='repeat':o.delete('X','source')
            leaked=any('controlled_marker_123' in r['content'] for r in s.records())
            preserved=any(r['id']=='retained' for r in s.records())
            files=audit_bytes(s,'controlled_marker_123');index=copy.deepcopy(o.index());records=s.records();s.close()
            return leaked,preserved,files,index,records
    def test_full_immediate(self):
        for cls in (SQLiteStore,JSONStore):self.assertEqual(self.exercise(cls,'full_overlay','immediate')[:2],(False,True))
    def test_native_derived_residue(self):
        for cls in (SQLiteStore,JSONStore):self.assertTrue(self.exercise(cls,'native_source_delete','immediate')[0])
    def test_one_time_purge_immediate(self):
        for cls in (SQLiteStore,JSONStore):self.assertFalse(self.exercise(cls,'dependency_purge','immediate')[0])
    def test_one_time_purge_restore(self):
        for cls in (SQLiteStore,JSONStore):self.assertTrue(self.exercise(cls,'dependency_purge','restore')[0])
    def test_full_blocks_stale_commit(self):
        for cls in (SQLiteStore,JSONStore):self.assertFalse(self.exercise(cls,'full_overlay','commit')[0])
    def test_full_filters_restore(self):
        for cls in (SQLiteStore,JSONStore):self.assertFalse(self.exercise(cls,'full_overlay','restore')[0])
    def test_commit_ablation(self):
        for cls in (SQLiteStore,JSONStore):self.assertTrue(self.exercise(cls,'without_commit_guard','commit')[0])
    def test_restore_ablation(self):
        for cls in (SQLiteStore,JSONStore):self.assertTrue(self.exercise(cls,'without_restore_guard','restore')[0])
    def test_lineage_ablation(self):
        for cls in (SQLiteStore,JSONStore):self.assertTrue(self.exercise(cls,'without_lineage_purge','immediate')[0])
    def test_restart_preserves_authority(self):
        for cls in (SQLiteStore,JSONStore):self.assertFalse(self.exercise(cls,'full_overlay','restart')[0])
    def test_repeat_delete_idempotence(self):
        for cls in (SQLiteStore,JSONStore):self.assertFalse(self.exercise(cls,'full_overlay','repeat')[0])
    def test_raw_bytes_after_purge(self):
        for cls in (SQLiteStore,JSONStore):self.assertEqual(self.exercise(cls,'full_overlay','immediate')[2],[])
    def test_authority_rollback_negative_control(self):
        for cls in (SQLiteStore,JSONStore):self.assertTrue(self.exercise(cls,'full_overlay','rollback')[0])
    def test_bypass_negative_control(self):
        for cls in (SQLiteStore,JSONStore):self.assertTrue(self.exercise(cls,'full_overlay','bypass')[0])
    def test_index_matches_records(self):
        for cls in (SQLiteStore,JSONStore):
            _,_,_,index,records=self.exercise(cls,'full_overlay','restore')
            self.assertEqual({x['id'] for x in index},{x['id'] for x in records})
    def test_authority_scope_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Authority(pathlib.Path(tmp)/'authority.json');a.revoke('X')
            self.assertFalse(a.allowed(artifact('x','raw','secret',['X'])))
            self.assertTrue(a.allowed(artifact('y','raw','retained',['Y'])))
    def test_vectors_reproducible(self):self.assertEqual(vector('test query'),vector('test query'))
    def test_distinct_layer_without_literal_canary(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp);s=JSONStore(p/'active');a=Authority(p/'auth.json');o=Overlay(s,a,'full_overlay')
            s.replace([artifact('source','raw','opaque token',['X']),artifact('derived','summary','preference without exact token',['X'],['source'])]);o.rebuild_index();o.delete('X','source');self.assertEqual(s.records(),[])

if __name__=='__main__':unittest.main(verbosity=2)
