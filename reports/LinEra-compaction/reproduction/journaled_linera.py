"""Single-writer research comparator. Process-crash recovery only; no power-loss proof.
Key journals retain the upstream key-state trust boundary and must never be backed up as data.
"""
from pathlib import Path
import json,os,secrets,sqlite3
from lf.store import LineageStore,_ad
from lf.keydag import KeyDAG,Forgotten
from lf.pprf import PPRF
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

def atomic(path,text):
    tmp=str(path)+'.tmp'
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f:
        f.write(text);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

def state_text(dag,generation):
    d=json.loads(dag.pprf.dumps());d['journal_generation']=generation
    return json.dumps(d)

class JournaledStore(LineageStore):
    """Exclusive single writer required; caller must not open this with upstream writer."""
    def __init__(self,path,state_path):
        self.journal=Path(str(state_path)+'.rotation-journal')
        self.phase_hook=lambda phase:None
        con=sqlite3.connect(path)
        con.execute('CREATE TABLE IF NOT EXISTS rotation_meta (id INTEGER PRIMARY KEY CHECK(id=1), generation TEXT NOT NULL)')
        row=con.execute('SELECT generation FROM rotation_meta WHERE id=1').fetchone()
        if row is None:
            self.generation='legacy'
            con.execute('INSERT INTO rotation_meta VALUES(1,?)',(self.generation,));con.commit()
        else:self.generation=row[0]
        con.close()
        if self.journal.exists():
            j=json.loads(self.journal.read_text(encoding='utf-8'))
            states={j['old_generation']:j['old_state'],j['new_generation']:j['new_state']}
            if self.generation not in states:raise RuntimeError('unmatched journal generation')
            selected=states[self.generation]
            if json.loads(selected).get('journal_generation','legacy')!=self.generation:
                raise RuntimeError('invalid state generation')
            atomic(state_path,selected)
            self.journal.unlink()
        if Path(state_path).exists():
            d=json.loads(Path(state_path).read_text(encoding='utf-8'))
            if d.get('journal_generation','legacy')!=self.generation:
                raise RuntimeError('state/database generation mismatch')
        elif self.generation!='legacy':raise RuntimeError('missing generation state')
        super().__init__(path,state_path)
    def _save_state(self):
        atomic(self.state_path,state_text(self.dag,self.generation))
    def rotate(self):
        if self.journal.exists():raise RuntimeError('pending recovery; reopen first')
        rows=[]
        for tag in self.tags():
            try:rows.append((tag,self.get(tag)))
            except Forgotten:continue
        new=KeyDAG(PPRF())
        for tag,_ in rows:new.register(tag,self.dag.parents.get(tag,()))
        generation=secrets.token_hex(16)
        fresh=state_text(new,generation)
        old=state_text(self.dag,self.generation)
        atomic(self.journal,json.dumps({'old_generation':self.generation,'new_generation':generation,'old_state':old,'new_state':fresh}))
        try:
            self.db.execute('BEGIN IMMEDIATE')
            for tag,content in rows:
                ps=new.parents[tag];nonce=secrets.token_bytes(12)
                ct=ChaCha20Poly1305(new.key(tag)).encrypt(nonce,content.encode(),_ad(tag,ps))
                self.db.execute('UPDATE obj SET nonce=?,ct=? WHERE tag=?',(nonce,ct,tag))
            self.db.execute('UPDATE rotation_meta SET generation=? WHERE id=1',(generation,))
            self.phase_hook('before_db_commit')
            self.db.commit()
            self.phase_hook('after_db_commit')
            atomic(self.state_path,fresh)
            self.phase_hook('after_state_publication')
            self.journal.unlink()
            self.dag=new;self.generation=generation
            return len(rows)
        except BaseException:
            self.db.rollback()
            raise
