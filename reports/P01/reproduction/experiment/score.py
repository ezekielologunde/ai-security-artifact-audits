"""Ground truth reads raw effect/store state; it never calls adapter.bundle()."""
import json,sqlite3
from contextlib import closing
from pathlib import Path

def ground_truth(run_dir):
    p=Path(run_dir)
    with closing(sqlite3.connect(p/'runtime.sqlite')) as c:
        old=c.execute("SELECT COUNT(*) FROM effects e JOIN requests r ON r.seq=e.request_seq WHERE r.phase='post' AND e.root='A'").fetchone()[0]
        legitimate=c.execute("SELECT COUNT(*) FROM effects e JOIN requests r ON r.seq=e.request_seq WHERE r.phase='post' AND e.root='B'").fetchone()[0]
        queued=c.execute("SELECT COUNT(*) FROM jobs WHERE root='A' AND state='QUEUED'").fetchone()[0]
        samples=[r[0]/1e6 for r in c.execute("SELECT admission_ns FROM requests WHERE phase='post'")]
    active=json.loads((p/'residual.json').read_text(encoding='utf-8'))['active']
    return {'old_root_effects':old,'independent_effects':legitimate,'active_artifact':bool(active),'queued_residuals':queued,'closure_blocker':bool(old or active or queued),'admission_ms':samples}
