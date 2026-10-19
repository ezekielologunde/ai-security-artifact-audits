"""Run the pinned author's offline suite with the acquired sample, recording runtime."""
import hashlib,json,os,sys
from importlib.metadata import version,PackageNotFoundError
from pathlib import Path
ROOT=Path(__file__).resolve().parent
if __name__=='__main__':
    for receipt in json.loads((ROOT/'data/code_manifest.json').read_text()):assert hashlib.sha256((ROOT/receipt['path']).read_bytes()).hexdigest()==receipt['sha256']
    sample=json.loads((ROOT/'data/sample_manifest.json').read_text());assert hashlib.sha256((ROOT/sample['path']).read_bytes()).hexdigest()==sample['sha256']
    sys.path.insert(0,str(ROOT/'data/source-code/src'));os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
    import pytest
    out=ROOT/'results';out.mkdir(exist_ok=True)
    exitcode=pytest.main([str(ROOT/'data/source-code/tests'),'-q','--junitxml='+str(out/'upstream_junit.xml'),'-o','cache_dir='+str(ROOT/'work/pytest-cache')])
    packages={}
    for name in ['cryptography','pytest','pyarrow','datasets','numpy']:
        try:packages[name]=version(name)
        except PackageNotFoundError:packages[name]=None
    result={'exit_code':int(exitcode),'python':sys.version,'packages':packages,'author_code_modified':False,'new_model_calls':0,'source_files_verified':32,'sample_sha256':sample['sha256']}
    (out/'upstream_tests.json').write_text(json.dumps(result,indent=2),encoding='utf-8');raise SystemExit(exitcode)
