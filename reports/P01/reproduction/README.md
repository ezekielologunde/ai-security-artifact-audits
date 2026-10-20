# Offboarding controlled study: public reproduction

Ezekiel Ologunde. Preliminary controlled study; no peer-reviewed acceptance or deployment assurance. This package preserves original reference source and inert raw evidence, with upstream task prose restored from its original host rather than republished. Do not execute historical attack helpers; none are included or needed.

## Restore and check reference evidence

Use Python 3.12 and Node.js 20+ with npm. From this directory:

```
python restore_reference_metadata.py
python scripts/verify_artifact.py
python -m unittest discover -s experiment -p test_experiment.py -v
python integration/verify_process_recovery.py --name process-recovery-v2
npm --prefix work/closure-baseline ci --ignore-scripts
npm --prefix work/closure-baseline install --no-save --package-lock=false --ignore-scripts fast-uri@3.1.8
```

The first command fetches only the SHA-256-pinned 141-row task ledger, reconstructs reference JSON/JSONL files and verifies their original byte hashes. It refuses mismatched existing files. This makes the original frozen-design hash valid without distributing task descriptions under an assumed licence. Network access is required for the first download and npm dependencies. The baseline runtime override is documented separately from its unchanged original lockfile.

Create `work/closure-baseline/inspector/public/cases`, then run `npm --prefix work/closure-baseline run inspector:generate` and `npm --prefix work/closure-baseline test` for the original 75-test suite. All five Python boundary tests and 80-case raw checkpoint/authority readbacks use the supplied reference evidence. Readback is distinct from fresh framework execution.

## Fresh fixture reproduction

```
python scripts/reproduce.py --name public-replication-001 --repeats 5
python scripts/compare_replication.py --name public-replication-001
```

Supply `--node /absolute/path/to/node` if needed. This creates 720 new local runs and 1,440 verifier evaluations and compares security outcomes/verdicts, excluding timing. A unique new name is mandatory. Do not run the original analyzer over measured-v2 unless intentionally regenerating a copied reference; it overwrites summary files. A one-repeat smoke run is incomplete for the full comparison command.

Framework reproduction requires the separate preserved integration dependency locks. Follow integration/README.md, DURABLE_RACE.md and PROCESS_RECOVERY.md in a dedicated environment, always using new run names. No LLM, real credential or provider API is needed. The 20 October validation freshly reran only the core 720-run fixture; it reread existing framework/process evidence rather than rerunning all extensions.

## Attribution and limits

The unchanged bounded-agent-closure verifier retains its Apache-2.0 licence and notices. See LICENSE.md and THIRD_PARTY_NOTICES.md: no blanket new-project reuse licence has been selected. AgentTrap metadata reports component-dependent/other licensing; task descriptions and the source ledger are acquired from origin, not distributed here. Templates contain placeholders; their reconstruction must pass original SHA-256 checks. Installed dependency terms remain separate.

Raw SQLite files contain authored synthetic tokens, inert effects and controlled checkpoints. They are reference measurements, not compromised production data. Logical denial of access does not prove physical erasure. Stale adapters and failed cleanup are assigned controls, not measured product failure rates. Source identities are trusted; independent external audit and exclusive novelty remain unestablished. The original source repository remains private; this package supplies the explicitly included reproduction materials independently.
