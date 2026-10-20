# Local offboarding microbenchmark

Only inert synthetic data are executed. Source AgentTrap skill files are untrusted research data and are never imported or run.

Requirements: Python 3.12+ standard library, Node 20+, and Ajv 8 in the unchanged `work/closure-baseline` release. The frozen release is `ef072360b7778e6e38a299576cbc2b8d7ac62f02`. The local helper currently records the bundled Windows Node path in `run_experiment.py`; change `NODE` to your installed Node executable on another machine.

From the project root:

```
python -m unittest discover -s experiment -p test_experiment.py
python experiment/run_experiment.py --repeats 5 --name replication-001
```

Every result directory must be new; existing runs are never overwritten. The script freezes the case configuration and code hashes before measured execution. It launches separate worker interpreters and saves raw SQLite stores, artifacts, JSON observations, evidence bundles, and unchanged-core receipts. `analyze.py` analyzes the published `measured-v2` directory. Adjust its `R` path for a new replication directory.

`validate_pilot.py` is a development diagnostic, excluded from measured results. The final measured execution follows schema repair. Check `outputs/experiment_report.md` and the manuscript for explicit limits. Repeated executions are repetitions of the same 24 scenarios, not 720 independently sampled attacks.

Source tasks: Hugging Face `zhmzm/AgentTrap`, commit `ab13f59d3f1236e7e65224d4fd6cc00dcdaaf68b`. Derived records: `datasets/derived/agenttrap_offboarding_adaptations.jsonl`. Source attribution and acquisition manifests reside in `datasets/upstream/agenttrap`. Component-specific upstream licensing applies; the experiment package does not redistribute original skill code.
