"""Run a controlled counterexample against pinned original aggregation and strict join."""
import hashlib,importlib.util,json,unittest
from pathlib import Path
import pandas as pd
from strict_join import join_outcomes,cost_outcomes
ROOT=Path(__file__).resolve().parent
module_path=ROOT/'data/trace-tables/scripts/paper_stats.py'
spec=importlib.util.spec_from_file_location('upstream_paper_stats',module_path);upstream=importlib.util.module_from_spec(spec);spec.loader.exec_module(upstream)
def fixtures(same=False):
    loaded=upstream.load_all_data([ROOT/'data/trace-tables/data/analysis_val_gpt'])
    base=loaded['runs'].iloc[0].to_dict();runs=[];tokens=[];outcomes=[]
    for model,ratio,correct in [('controlled_A',3.,True),('controlled_B',1.,True if same else False)]:
        runs.append({**base,'task_id':'shared_task','perturbation_type':'shared_perturbation','model':model,'source_dir':model})
        tokens.append({'task_id':'shared_task','perturbation_type':'shared_perturbation','model':model,'source_dir':model,
                       'baseline_tokens':100,'perturbed_tokens':100*ratio,'extra_tokens':100*(ratio-1),'file_type':'tabular','token_multiplier':ratio})
        outcomes.append({'model':model,'task_id':'shared_task','perturbation_type':'shared_perturbation','is_correct':correct})
    return runs,tokens,outcomes
def evaluate(reverse=False,same=False):
    runs,tokens,outcomes=fixtures(same)
    if reverse:runs.reverse();tokens.reverse();outcomes.reverse()
    original=upstream.compute_paper_stats(pd.DataFrame(runs),pd.DataFrame(tokens),pd.DataFrame(outcomes))
    corrected=cost_outcomes(join_outcomes(tokens,outcomes))
    return {'original':{k:original[k] for k in ['high_cost_correct_pct','low_cost_incorrect_pct','high_cost_count','low_cost_count']},'strict':corrected}
class JoinChecks(unittest.TestCase):
    def test_counterexample(self):
        result=evaluate();self.assertEqual(result['original']['high_cost_correct_pct'],50.);self.assertEqual(result['original']['low_cost_incorrect_pct'],50.)
        self.assertEqual(result['original']['high_cost_count'],2);self.assertEqual(result['strict']['high_cost_labeled_rows'],1)
        self.assertEqual(result['strict']['high_cost_correct_pct'],100.);self.assertEqual(result['strict']['low_cost_incorrect_pct'],100.)
    def test_order(self):self.assertEqual(evaluate(),evaluate(reverse=True))
    def test_negative_control(self):
        result=evaluate(same=True);self.assertEqual(result['original']['high_cost_correct_pct'],result['strict']['high_cost_correct_pct']);self.assertEqual(result['original']['low_cost_incorrect_pct'],result['strict']['low_cost_incorrect_pct'])
    def test_missing_identity(self):
        _,tokens,outcomes=fixtures();del outcomes[0]['model']
        with self.assertRaises(ValueError):join_outcomes(tokens,outcomes)
    def test_unknown(self):
        _,tokens,outcomes=fixtures();result=cost_outcomes(join_outcomes(tokens,outcomes[:1]));self.assertEqual(result['unknown_correctness_rows'],1);self.assertIsNone(result['low_cost_incorrect_pct'])
    def test_duplicates(self):
        _,tokens,outcomes=fixtures()
        with self.assertRaises(ValueError):join_outcomes(tokens,outcomes+outcomes[:1])
        with self.assertRaises(ValueError):join_outcomes(tokens+tokens[:1],outcomes)
if __name__=='__main__':
    receipts=json.loads((ROOT/'data/trace_tables_manifest.json').read_text());receipt=next(r for r in receipts if r['path'].endswith('scripts/paper_stats.py'))
    assert hashlib.sha256(module_path.read_bytes()).hexdigest()==receipt['sha256']
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(JoinChecks);run=unittest.TextTestRunner(verbosity=2).run(suite)
    record={'original_script_sha256':receipt['sha256'],'controlled_fixture':evaluate(),'equal_correctness_control':evaluate(same=True),
            'tests_run':run.testsRun,'tests_passed':run.wasSuccessful(),'raw_author_correctness_available':False,'natural_effect_size_estimated':False}
    (ROOT/'results/join_counterexample.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record,indent=2));raise SystemExit(0 if run.wasSuccessful() else 1)
