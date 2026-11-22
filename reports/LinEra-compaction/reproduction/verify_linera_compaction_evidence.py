"""Read-only direct check of the recorded interrupted fixture."""
from pathlib import Path
import sys,json,sqlite3,hashlib
ROOT=Path(__file__).resolve().parent
WORK=ROOT/'work/linera-compaction-v1'
sys.path.insert(0,str(WORK/'source'))
from lf.pprf import PPRF
from lf.keydag import KeyDAG
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
folder=WORK/'interrupted_rotation'
paths=[folder/'objects.db',folder/'state.json',folder/'tags.json']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before={p.name:sha(p) for p in paths}
state=PPRF.loads((folder/'state.json').read_text())
con=sqlite3.connect((folder/'objects.db').as_uri()+'?mode=ro',uri=True)
records=con.execute('SELECT tag,parents,nonce,ct FROM obj').fetchall();con.close()
dag=KeyDAG(state)
for tag,parents,_,_ in records:dag.register(tag,json.loads(parents))
tags=json.loads((folder/'tags.json').read_text());index={row[0]:row for row in records};checks={}
for name,tag in tags.items():
 _,parents,nonce,ct=index[tag];ps=json.loads(parents)
 try:
  key=dag.key(tag)
  ad=tag.to_bytes(4,'big')+b''.join(p.to_bytes(4,'big') for p in ps)
  plaintext=ChaCha20Poly1305(key).decrypt(nonce,ct,ad)
  checks[name]={'readable':True,'plaintext':plaintext.decode()}
 except Exception as exc:checks[name]={'readable':False,'exception_type':type(exc).__name__}
assert all(not x['readable'] for x in checks.values())
assert checks['retained_source']['exception_type']==checks['retained_derived']['exception_type']=='InvalidTag'
assert all(sha(p)==before[p.name] for p in paths)
result={'date':'2026-11-21','method':'Read-only SQLite plus direct key derivation and AEAD decryption; no LineageStore constructor/get used','results':checks,'input_sha256':before,'inputs_unchanged':True,'same_source_crypto_primitives':True,'independent_external_validation':False,'scope':'Corroborates recorded stored key/ciphertext mismatch, not independent implementation or security proof.'}
(ROOT/'results/linera_compaction_direct_verification_20261121.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
