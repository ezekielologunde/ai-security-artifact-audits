# Durable checkpoint admission race v1

Executed October 7, 2026. Ten controlled runs: two admission controls, five repetitions. This is a separate extension of P01; earlier experiments are unchanged.

Actual LangGraph SqliteSaver checkpoints are created for roots A and B. A consistent SQLite backup is retained. A worker checks A's authority, then waits at a barrier. Retirement invalidates A and invokes delete_thread('A'). Raw database queries confirm zero live A checkpoint rows and unchanged B rows. The late worker is then released.

With a check-before-wait gate, all five runs recreate durable A checkpoints. With a second authority check under the same lifecycle lock used by retirement, held throughout graph execution and checkpoint writes, none of five runs recreates A checkpoints. A fresh database connection confirms the final live counts. B's checkpoint count remains unchanged in all ten runs. All ten backups retain A's original checkpoint rows.

This is a controlled time-of-check/time-of-use conformance test of an authored lifecycle wrapper, not a newly discovered LangGraph vulnerability. The serialized control governs callers using that wrapper and trusted authority state. It does not govern bypass callers, cross-process writers, external checkpoint restores or distributed workers. Holding a lock through a long graph invocation can delay retirement; this experiment does not measure worst-case delay or liveness. The forced interleaving is one schedule, not exhaustive race exploration. No model, effect sink, provider credential or closure certificate is evaluated. The readback counts checkpoint rows; it does not claim physical erasure of SQLite pages or every possible serialized artifact. A retained backup must be separately disposed of or fenced under a recovery policy.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m pip install -r integration/requirements-durable-lock.txt
.\.venv\Scripts\python.exe integration/durable_race.py --name durable-replication-001 --repeats 5
```

Every new run requires a new directory. Protocol/source hash, package versions, records and summary are tracked for durable-race-v1; raw checkpoint databases and backups remain local. The original framework dependency lock is preserved separately.

Primary references: [SqliteSaver](https://reference.langchain.com/python/langgraph.checkpoint.sqlite/SqliteSaver), [delete_thread contract](https://reference.langchain.com/python/langgraph.checkpoint.sqlite/SqliteSaver/delete_thread). These document the storage API; they do not establish our wrapper's production security or physical deletion.

Next evidence: independent replay of this experiment, cross-process checkpoint writes, and restored-backup replay against durable authority state. Do not pool these ten repeated executions with the earlier 80-run integration as independent attack samples.
