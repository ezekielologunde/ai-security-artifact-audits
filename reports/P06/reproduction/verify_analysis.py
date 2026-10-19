"""Independent metric arithmetic, source integrity, split and unknown-case diagnostics."""
import collections,hashlib,json,tempfile,unittest
from pathlib import Path
from lexical_baseline import Matcher,metrics,tokenize,server_key
ROOT=Path(__file__).resolve().parent

class Boundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.model=Matcher('names_descriptions')
    def test_receipts_are_not_catalogs(self):
        folder=ROOT/'data/benchmark/data/mcp_servers/ASTRA'
        with tempfile.NamedTemporaryFile(mode='w',suffix='.json',dir=folder,delete=False) as f:
            f.write('{"audit_receipt":true}');path=Path(f.name)
        try:self.assertEqual(Matcher('names_descriptions').catalog,self.model.catalog)
        finally:path.unlink()
    def test_unknown_binding_is_indeterminate(self):
        self.assertIsNone(self.model.score({'task':'Read a message','tools':['not_a_tool'],'mcp_servers':['missing']},'ASTRA'))
    def test_tokenization_preserves_action_words(self):
        self.assertEqual(tokenize('Please getUser and delete_file'),['get','user','delete','file'])
    def test_server_binding_is_not_just_tool_name(self):
        key=next(iter(self.model.catalog));source,server,tool=key
        self.assertIsNone(self.model.score({'task':tool,'tools':[tool],'mcp_servers':['definitely_missing']},source))
    def test_unknown_is_not_correctly_rejected(self):
        x=metrics([{'truth':True,'score':None}],0.1)
        self.assertEqual(x['indeterminate'],1);self.assertEqual(x['assessed'],0)

def main():
    tests=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries))
    if not tests.wasSuccessful():raise SystemExit(1)
    manifest=json.loads((ROOT/'data/benchmark_manifest.json').read_text())
    for item in manifest['receipts']:assert hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['sha256']
    summary=json.loads((ROOT/'results/lexical-v2/summary.json').read_text())
    unknowns=[]
    for variant,record in summary['variants'].items():
        predictions=[json.loads(x) for x in (ROOT/f'results/lexical-v2/{variant}_predictions.jsonl').read_text().splitlines()]
        for group,expected in record['test'].items():
            source,n=group.rsplit('_',1)
            rows=[r for r in predictions if r['source']==source and r['split']=='test' and r['tools_per_task']==int(n)]
            counts=collections.Counter()
            for row in rows:
                if row['score'] is None:counts['unknown']+=1;continue
                pred=row['score']>=record['calibrated_threshold'];truth=row['truth']
                counts['tp' if pred and truth else 'fp' if pred else 'fn' if truth else 'tn']+=1
            actual=expected['lexical']
            assert all(counts[k]==actual[k] for k in ['tp','fp','fn','tn'])
            assert counts['unknown']==actual['indeterminate']
        if variant=='names_descriptions':
            model=Matcher(variant)
            for r in predictions:
                if r['score'] is not None:continue
                folder={1:'01_tool',2:'02_tools',3:'03_tools'}[r['tools_per_task']]
                row=json.loads((ROOT/f'data/benchmark/data/{folder}/{r["source"]}/{r["split"]}.json').read_text())[r['row']]
                missing=[{'server':s,'tool':t} for t,s in zip(row['input']['tools'],row['input']['mcp_servers']) if (r['source'],server_key(s),t) not in model.catalog]
                unknowns.append(dict(r,missing_catalog_bindings=missing))
    result={'source_files_sha256_verified':len(manifest['receipts']),'boundary_tests_passed':tests.testsRun,
        'independent_confusion_count_recalculation':True,'unknown_cases':unknowns,
        'limits':'This validates software arithmetic and file identity; it does not independently adjudicate source semantic labels.'}
    (ROOT/'results/lexical-v2/verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'verified_sources':len(manifest['receipts']),'tests':tests.testsRun,'unknowns':len(unknowns),'missing':[r['missing_catalog_bindings'] for r in unknowns]},indent=2))

if __name__=='__main__':main()
