"""Audit reachable CPython memoizer keys, not heap or physical erasure."""
import gc,hashlib,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiment'))
from overlay import SQLiteStore,JSONStore,Authority,Overlay,artifact,vector,audit_bytes

class CacheClearingOverlay(Overlay):
    def delete(self,scope,source_id):
        super().delete(scope,source_id)
        vector.cache_clear()

def cached_text_keys():
    # CPython implementation-specific forensic access to directly reachable cache dict.
    result=[]
    for ref in gc.get_referents(vector):
        if isinstance(ref,dict):
            for key in ref:
                if isinstance(key,str):result.append(key)
                elif isinstance(key,tuple):result.extend(x for x in key if isinstance(x,str))
    return result

def main():
    out=ROOT/'behavioral-experiment';work=ROOT.parent/'work'/'cache-audit';work.mkdir(parents=True,exist_ok=True)
    rows=[]
    for backend in [SQLiteStore,JSONStore]:
        for index in range(24):
            marker='CACHE_'+hashlib.sha256(f'cache-v2:{index}'.encode()).hexdigest()[:24]
            for arm,cls in [('v1_full',Overlay),('cache_clearing_full',CacheClearingOverlay)]:
                vector.cache_clear();store=backend(work/f'{backend.name}-{index}-{arm}')
                authority=Authority(work/f'{backend.name}-{index}-{arm}-authority.json');authority._write({})
                target=artifact('target','raw','Project X code '+marker,['x'])
                store.replace([target,artifact('foil','raw','Project Y day Thursday',['y'])])
                overlay=cls(store,authority,'full_overlay');overlay.rebuild_index()
                before=any(marker in k for k in cached_text_keys());assert before
                overlay.delete('x','target')
                row={'backend':backend.name,'episode':index,'arm':arm,'acquired':before,'active_byte_recovery':bool(audit_bytes(store,marker)),'cache_key_recovery':any(marker in k for k in cached_text_keys()),'foil_preserved':any(r['id']=='foil' for r in store.records())}
                rows.append(row);store.close()
    assert len(rows)==96
    assert all(not r['active_byte_recovery'] and r['foil_preserved'] for r in rows)
    assert all(r['cache_key_recovery']==(r['arm']=='v1_full') for r in rows)
    (out/'cache-audit-results.json').write_text(json.dumps({'python':sys.version,'method':'gc.get_referents of functools.lru_cache wrapper, string keys only','trials':rows},indent=2),encoding='utf-8')
    print('96 cache cases: v1 48/48 reachable target keys; explicit clear 0/48; active files 0/96.')
if __name__=='__main__':main()
