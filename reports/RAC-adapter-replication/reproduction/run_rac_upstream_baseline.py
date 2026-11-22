"""Execute the selected unchanged native upstream test file in the qualified runtime."""
from pathlib import Path
import hashlib,json,os,sys
ROOT=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path[:0]=[str(Path(os.environ.get('RAC_RUNTIME_PATH',str(ROOT/'tools/rac-runtime')))),str(ROOT/'data/rac-qualification-20261121/src')]
import pytest
test=ROOT/'data/rac-adapter-followup-20261121/test_recovery_manager.py'
expected=json.loads((test.parent/'acquisition.json').read_text())
entry=next(x for x in expected['files'] if x['local_file']==test.name)
assert hashlib.sha256(test.read_bytes()).hexdigest()==entry['sha256']
report=ROOT/'results/rac_upstream_baseline_20261121.xml'
code=pytest.main(['-q','-p','no:cacheprovider','--junitxml='+str(report),str(test)])
(ROOT/'results/rac_upstream_baseline_exit_20261121.json').write_text(json.dumps(dict(exit_code=int(code),test_sha256=entry['sha256'],source_unchanged=hashlib.sha256(test.read_bytes()).hexdigest()==entry['sha256']))+'\n')
raise SystemExit(code)
