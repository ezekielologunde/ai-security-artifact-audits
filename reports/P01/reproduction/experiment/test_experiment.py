import json,subprocess,sys,tempfile,unittest
from pathlib import Path
from runtime import initialize,retire,admit
from adapter import bundle
from score import ground_truth

class Boundaries(unittest.TestCase):
 def make(self,arm='sink_overlay',failed=False):
  p=Path(self.tmp.name)/str(len(list(Path(self.tmp.name).iterdir())))
  case={'source_case_id':1,'artifact_kind':'synthetic','auth_mode':'cached_token','route':'background','failed_cleanup':failed,'stale_adapter':False,'missing_source':False}
  initialize(p,case,arm);return p,case
 def setUp(self):self.tmp=tempfile.TemporaryDirectory()
 def tearDown(self):self.tmp.cleanup()
 def test_durable_fence_and_independent_root(self):
  p,c=self.make();self.assertTrue(admit(p,'A',1,'cached_token','background','pre')['allowed']);retire(p,c,'sink_overlay')
  # A fresh interpreter tests persistence across a process boundary.
  out=json.loads(subprocess.check_output([sys.executable,str(Path(__file__).parent/'worker.py'),str(p),'post'],text=True))
  self.assertFalse(out['retired']['allowed']);self.assertTrue(out['independent']['allowed'])
  self.assertEqual(ground_truth(p)['old_root_effects'],0)
 def test_revocation_cannot_recall_unchecked_cache(self):
  p,c=self.make('credential_revoke');retire(p,c,'credential_revoke')
  self.assertTrue(admit(p,'A',1,'cached_token','background','post')['allowed'])
  self.assertFalse(admit(p,'A',1,'issuer_recheck','background','post')['allowed'])
 def test_false_ack_and_stale_adapter(self):
  p,c=self.make(failed=True);c['stale_adapter']=True;retire(p,c,'sink_overlay')
  self.assertTrue(ground_truth(p)['closure_blocker'])
  snap=bundle(p,c,'snapshot');probe=bundle(p,c,'probe')
  self.assertEqual(snap['scans'][0]['sources'][0]['residuals'][0]['effect'],'INERT')
  self.assertEqual(probe['scans'][0]['sources'][0]['residuals'][0]['effect'],'ACTIVE')
 def test_blanket_deny_blocks_legitimate_effect(self):
  p,c=self.make('blanket_deny');retire(p,c,'blanket_deny')
  self.assertFalse(admit(p,'B',1,'issuer_recheck','background','post')['allowed'])
 def test_unknown_root(self):
  p,c=self.make();self.assertFalse(admit(p,'X',1,'local_uncredentialed','background','pre')['allowed'])

if __name__=='__main__':unittest.main()
