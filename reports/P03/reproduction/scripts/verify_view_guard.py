"""Boundary checks and full-row projection of the two locally generated runs."""
import csv, hashlib, json, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from view_guard import FEATURES, project_record, validate_feature_columns

class GuardChecks(unittest.TestCase):
    def test_original_leaked_schema_rejected(self):
        with self.assertRaises(ValueError):validate_feature_columns(FEATURES|{'session_type'})
    def test_label_renamed_to_unknown_column_rejected(self):
        with self.assertRaises(ValueError):validate_feature_columns(FEATURES|{'outcome_alias'})
    def test_join_identity_not_a_feature(self):
        with self.assertRaises(ValueError):validate_feature_columns(FEATURES|{'session_id'})
    def test_required_observations_enforced(self):
        with self.assertRaises(ValueError):validate_feature_columns({'upload_kb'})
    def test_allowed_projection(self):
        r=project_record({'destination_domain':'example.invalid','upload_kb':1,'download_kb':2,
                          'session_type':'shadow_ai_violation','session_id':'join-only'})
        self.assertNotIn('session_type',r['features']);self.assertNotIn('session_id',r['features'])
        self.assertEqual(r['join_metadata']['session_id'],'join-only')

def main():
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(GuardChecks)
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
    runs=[]
    for number in [1,2]:
        p=ROOT/'work'/f'generator-run-{number}'/'outputs/detector_view.csv'
        before=hashlib.sha256(p.read_bytes()).hexdigest();n=0
        with p.open(newline='',encoding='utf-8') as f:
            for row in csv.DictReader(f):
                projected=project_record(row)
                assert not {'session_type','session_id','employee_id'}&projected['features'].keys()
                n+=1
        assert hashlib.sha256(p.read_bytes()).hexdigest()==before
        runs.append({'run':number,'rows_projected':n,'original_sha256_unchanged':before})
    out={'boundary_tests':result.testsRun,'failed':0,'runs':runs,'limitation':'Successful projection enforces the declared schema; it is not proof of exhaustive statistical leakage removal or field observability in a real network.'}
    (ROOT/'results/view_guard_verification.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))

if __name__=='__main__':main()
