# Cross-process checkpoint admission and recovery

The manuscript's final evidence uses **process-recovery-v2**, implemented in `process_recovery_v2.py`. V1 is preserved as an excluded portability run: its behavioral assertions passed, but the Linux verifier found that recorded database hashes could change after SQLite WAL checkpointing because some connections were not explicitly closed. V2 explicitly closes connections and performs a WAL checkpoint before recording database hashes. V1 counts are not pooled with v2 or presented as independently validated final evidence.

This version tests an authored synchronous SqliteSaver wrapper against delayed writers and checkpoint-only restoration. It uses no LLM, provider credential, external effect sink, or original benchmark payload. Earlier experiments remain byte-preserved.

Four controls × two interleavings × two recovery conditions × five repetitions define 80 runs, representing 16 configurations. Development runs are excluded. Each A writer, B invocation and A access probe executes in a fresh Python process.

The controls are unmediated checkpoint access, cached admission, durable operation-level admission, and blanket denial. A worker pauses either before invoking a graph or inside its echo node. The parent invalidates A's authority, advances its epoch and invokes `delete_thread('A')`. Fresh SQL confirms zero A checkpoint rows. In recovery cases the parent restores the checkpoint database from the pre-retirement backup. The separate authority database remains retired. Releasing the worker tests delayed writes; subsequent fresh processes test A access and B preservation.

The wrapper binds a trusted root and epoch zero to its instance. It checks `get_tuple`, `put` and `put_writes` under an authority `BEGIN IMMEDIATE` transaction held through the corresponding checkpoint operation. Retirement uses the same serialization boundary. A node already admitted before retirement can finish; arbitrary node effects are not fenced by this checkpoint wrapper. Each operation uses authority-then-checkpoint lock ordering.

## Assurance boundary

Checkpoint-only restoration retains original A bytes. Denying their access is logical fencing, not physical deletion. The original backup remains intentionally observable. Restoring or bypassing the authority database is outside the tested profile and can invalidate the admission property. Async methods, checkpoint listing, subgraphs, adversarial identity claims, key management, distributed partitions, crashes and physical media recovery are not evaluated.

The authority and checkpoint databases are not a single atomic crash transaction. A failure between checkpoint commit and authority-audit commit can leave incomplete evidence. Normal-completion barrier tests cannot establish crash recovery or liveness. Raw database access bypasses the wrapper. All reported identities and epochs are trusted harness values.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m pip install -r integration/requirements-durable-lock.txt
.\.venv\Scripts\python.exe integration/process_recovery_v2.py --name process-recovery-replication-001 --repeats 5
.\.venv\Scripts\python.exe integration/verify_process_recovery.py --name process-recovery-replication-001
```

Use a new directory name for every execution. The protocol records exact source bytes before collection. Every run saves checkpoint, backup and authority databases, raw audit observations and hashes. The separate verifier opens fresh read-only SQLite connections and verifies all three hashes per run, final checkpoint counts, authority states and the audit sequence. This is a separate read path by the same researcher, not independent external review. Aggregates are committed; raw files are included in the local review package and recreated by these commands.
