# AgentDefense-Bench entry-point audit replay

Author: Ezekiel Ologunde. Local technical report supplement, 21 October 2026.

Requires Python 3.10+ and Git. No third-party Python packages, model downloads or API keys. Tested runtime and exact receipt appear in the clean-package verification record. Network access to the public upstream Git repository is needed only for restoration. Git may transfer roughly 133 MB of repository blobs; selected restored files are approximately 46 MB.

Run from this directory:

```
python restore_agentdefense.py
python audit_agentdefense_entrypoints.py
python verify_agentdefense_replay.py
```

Restoration obtains the fixed revision, checks sizes, Git blob SHA-1 and SHA-256, and refuses changed existing input files. It does not check out code, fetch submodules, execute attacks or contact defense endpoints. Failed fetch logs remain in results/. The replay executes only inspected mock/evaluator definitions through AST selection. The final verifier compares the entire resulting JSON to the retained expected result. Inspect AGENTDEFENSE_ENTRYPOINT_PROTOCOL.md and AGENTDEFENSE_ENTRYPOINT_RESULTS.md for measurement boundaries.

All exports are kept separate. Label normalization changes evaluation semantics; it does not improve a detector. Natural labels have not been independently validated. These data do not establish longitudinal authority drift, production efficacy or effects on published model rankings.

The package includes authored code, protocol, notes, hash manifests and aggregate expected results. No raw multi-source attack corpus or upstream source code is bundled. Restored upstream files retain their original terms; see the restored LICENSE and dataset documentation, including source-specific licences. No blanket licence for this authored supplement has been selected; rights reserved. Public availability is not a claim of peer review or unrestricted reuse.
