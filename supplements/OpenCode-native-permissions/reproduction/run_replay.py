"""MIT. Replay in this fresh extraction with a separately verified official native binary."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys
from normalize import normalize
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--binary',required=True,type=Path)
args=parser.parse_args()
for line in (ROOT/'SHA256SUMS').read_text().splitlines():
    h,n=line.split('  ',1)
    assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
binary=args.binary.resolve()
expected='2359208e2f81539fd16eb755a4d8a747e87c6fd5cd59a49bb552f8a610d33eb9'
assert hashlib.sha256(binary.read_bytes()).hexdigest()==expected
assert not (ROOT/'work').exists(),'Use a fresh extraction; existing evidence is never removed automatically'
(ROOT/'work').mkdir()
(ROOT/'results').mkdir(exist_ok=False)
acquisition={'binary_path':str(binary),'binary_sha256':expected}
(ROOT/'results/opencode_binary_acquisition_20261123.json').write_text(json.dumps(acquisition,indent=2)+'\n')
env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
commands=[]
for script in ['run_opencode_write_effects_20261123.py','verify_opencode_write_effects_20261123.py']:
    process=subprocess.run([sys.executable,str(ROOT/script)],env=env,capture_output=True,timeout=180)
    (ROOT/'results'/(script+'.stdout')).write_bytes(process.stdout)
    (ROOT/'results'/(script+'.stderr')).write_bytes(process.stderr)
    commands.append({'script':script,'exit_code':process.returncode})
    assert process.returncode==0,(script,process.stderr.decode(errors='replace')[-1500:])
actual=json.loads((ROOT/'results/opencode-write-effects-20261123-r2/RESULTS.json').read_text())
observed=normalize(actual)
assert observed==json.loads((ROOT/'EXPECTED_OBSERVATIONS.json').read_text())
for line in (ROOT/'SHA256SUMS').read_text().splitlines():
    h,n=line.split('  ',1)
    assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
receipt={'commands':commands,'normalized_observations_match':True,'conditions':len(observed),'packaged_members_unchanged':True,'real_inference_models':0,'external_peer_review':False}
(ROOT/'results/CLEAN_REPLAY.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
