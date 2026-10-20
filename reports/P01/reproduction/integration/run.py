"""Local framework conformance experiment; no model calls or provider credentials."""
import argparse
import hashlib
import hmac
import importlib.metadata
import json
import os
import platform
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TypedDict
from urllib.error import HTTPError
from urllib.request import Request, urlopen

os.environ['LANGSMITH_TRACING'] = 'false'
from apscheduler.schedulers.background import BackgroundScheduler
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END


class State(TypedDict):
    root: str
    phase: str
    status: int


def run_case(folder, backend, fenced, cleanup, graph_gate):
    folder.mkdir()
    lock = threading.Lock()
    key = secrets.token_bytes(32)
    active = {'A': True, 'B': True}
    effect_path = folder / ('effects.sqlite' if backend == 'sqlite' else 'effects.jsonl')
    if backend == 'sqlite':
        with sqlite3.connect(effect_path) as db:
            db.execute('CREATE TABLE effects(root TEXT, phase TEXT)')
    else:
        effect_path.touch()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            signature = self.headers.get('Authorization', '')
            signed = hmac.compare_digest(signature, hmac.new(key, raw, hashlib.sha256).hexdigest())
            data = json.loads(raw)
            with lock:
                permitted = signed and data['root'] in active and (not fenced or active[data['root']])
                if permitted:
                    if backend == 'sqlite':
                        with sqlite3.connect(effect_path) as db:
                            db.execute('INSERT INTO effects VALUES (?,?)', (data['root'], data['phase']))
                    else:
                        with effect_path.open('a', encoding='utf-8') as stream:
                            stream.write(json.dumps(data) + '\n')
                self.send_response(201 if permitted else 403)
                self.end_headers()

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    scheduler = BackgroundScheduler(timezone='UTC')
    memory = InMemorySaver()
    receipts = []

    def request(root, phase, forged=False):
        raw = json.dumps({'root': root, 'phase': phase}, sort_keys=True).encode()
        signature = 'invalid' if forged else hmac.new(key, raw, hashlib.sha256).hexdigest()
        req = Request(f'http://127.0.0.1:{server.server_port}/effect', data=raw,
                      headers={'Authorization': signature, 'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=10) as response:
                status = response.status
        except HTTPError as error:
            status = error.code
        with lock:
            receipts.append({'root': root, 'phase': phase, 'status': status})
        return status

    def node(state):
        return {'status': request(state['root'], state['phase'])}

    builder = StateGraph(State)
    builder.add_node('tool', node)
    builder.add_edge(START, 'tool')
    builder.add_edge('tool', END)
    graph = builder.compile(checkpointer=memory)
    config = lambda root: {'configurable': {'thread_id': root}}
    entered, release, finished, pending_finished = (threading.Event() for _ in range(4))

    def in_flight():
        entered.set()
        if not release.wait(10):
            return
        try:
            request('A', 'in-flight-after-cut')
        finally:
            finished.set()

    def pending():
        try:
            request('A', 'pending-after-cut')
        finally:
            pending_finished.set()

    try:
        for root in ('A', 'B'):
            assert graph.invoke({'root': root, 'phase': 'calibration'}, config(root))['status'] == 201
        assert request('B', 'forged', forged=True) == 403
        checkpoint_before = memory.get_tuple(config('A')) is not None
        scheduler.add_job(in_flight, 'date', id='in-flight', run_date=datetime.now(timezone.utc))
        scheduler.add_job(pending, 'date', id='pending', run_date=datetime.now(timezone.utc) + timedelta(hours=1))
        scheduler.start()
        assert entered.wait(10), 'scheduler did not dispatch in-flight job'
        with lock:
            active['A'] = False
        if cleanup:
            scheduler.remove_job('pending')
            memory.delete_thread('A')
        checkpoint_after_cleanup = memory.get_tuple(config('A')) is not None
        pending_after_cleanup = scheduler.get_job('pending') is not None
        release.set()
        assert finished.wait(10), 'in-flight job did not finish'
        if not cleanup:
            scheduler.modify_job('pending', next_run_time=datetime.now(timezone.utc))
            assert pending_finished.wait(10), 'pending job did not finish'
        # A sequential lifecycle admission gate also protects checkpoint creation.
        # This check is not atomic with invoke; concurrent admission is a remaining limit.
        if not graph_gate or active['A']:
            graph.invoke({'root': 'A', 'phase': 'graph-after-cut'}, config('A'))
        graph.invoke({'root': 'B', 'phase': 'graph-after-cut'}, config('B'))
        checkpoint_recreated = memory.get_tuple(config('A')) is not None
        scheduler.shutdown(wait=True)
        if backend == 'sqlite':
            with sqlite3.connect(effect_path) as db:
                effects = [{'root': r, 'phase': p} for r, p in db.execute('SELECT root, phase FROM effects')]
        else:
            effects = [json.loads(line) for line in effect_path.read_text().splitlines()]
        post = [e for e in effects if 'after-cut' in e['phase']]
        a_count = sum(e['root'] == 'A' for e in post)
        b_count = sum(e['root'] == 'B' for e in post)
        assert a_count == (0 if fenced else 1 + int(not cleanup) + int(not graph_gate))
        assert b_count == 1
        assert checkpoint_before and checkpoint_recreated == (not cleanup or not graph_gate)
        assert checkpoint_after_cleanup == (not cleanup)
        assert pending_after_cleanup == (not cleanup)
        record = {'backend': backend, 'fenced': fenced, 'cleanup': cleanup, 'graph_gate': graph_gate,
                  'retired_effects': a_count, 'independent_effects': b_count,
                  'checkpoint_after_cleanup': checkpoint_after_cleanup,
                  'checkpoint_recreated_by_late_graph': checkpoint_recreated,
                  'pending_after_cleanup': pending_after_cleanup, 'receipts': receipts,
                  'effects_sha256': hashlib.sha256(effect_path.read_bytes()).hexdigest()}
        (folder / 'record.json').write_text(json.dumps(record, indent=2))
        return record
    finally:
        release.set()
        if scheduler.running:
            scheduler.shutdown(wait=True)
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--repeats', type=int, default=5)
    args = parser.parse_args()
    if Path(args.name).name != args.name or args.name in ('.', '..') or args.repeats < 1:
        parser.error('Use a new simple directory name and positive repeat count')
    out = Path(__file__).resolve().parent / 'results' / args.name
    out.mkdir(parents=True, exist_ok=False)
    protocol = {'version': 1, 'frozen_at': datetime.now(timezone.utc).isoformat(),
                'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'python': platform.python_version(), 'platform': platform.platform(),
                'packages': {p: importlib.metadata.version(p) for p in ('langgraph', 'langgraph-checkpoint', 'APScheduler')},
                'repeats': args.repeats, 'backends': ['sqlite', 'jsonl'],
                'factors': ['sink fencing', 'cleanup', 'sequential graph admission gate'],
                'limits': ['No LLM/provider calls', 'In-process HTTP server and ephemeral HMAC key',
                           'InMemorySaver is not durable or physical erasure', 'Controlled barrier interleaving',
                           'No distributed fault or independent external auditor', 'No closure certificate computed',
                           'Graph admission check is not atomic with execution; checkpoint races remain untested']}
    (out / 'protocol.json').write_text(json.dumps(protocol, indent=2))
    rows = []
    for repeat in range(args.repeats):
        for backend in ('sqlite', 'jsonl'):
            for fenced in (False, True):
                for cleanup in (False, True):
                    for graph_gate in (False, True):
                        ident = f'r{repeat}-{backend}-fence{int(fenced)}-cleanup{int(cleanup)}-gate{int(graph_gate)}'
                        rows.append({'run_id': ident, **run_case(out / ident, backend, fenced, cleanup, graph_gate)})
    (out / 'records.json').write_text(json.dumps(rows, indent=2))
    summary = {'runs': len(rows), 'fenced_retired_effects': sum(r['retired_effects'] for r in rows if r['fenced']),
               'unfenced_retired_effects': sum(r['retired_effects'] for r in rows if not r['fenced']),
               'independent_effects': sum(r['independent_effects'] for r in rows),
               'late_checkpoint_recreations': sum(r['checkpoint_recreated_by_late_graph'] for r in rows),
               'all_assertions_passed': True}
    (out / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps({'output': str(out), **summary}))


if __name__ == '__main__':
    main()
