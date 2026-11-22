# Rego generated-oracle audit reproduction

The paper reports a conditional artifact audit of a known Rego test-semantics hazard.
No new mutation operator, language vulnerability, deployment exploit, or superiority
over Regal/regodrill is claimed. Full-suite semantic escapes from an originally
passing suite were not demonstrated. See the paper and novelty assessment.

## Replay environment and commands

Verified controller: Windows, Python 3.12.14, WSL distribution named Ubuntu,
Linux Python 3 and bubblewrap. The controller uses only Python standard libraries.
Native OPA commands run in private bubblewrap namespaces. Extract to a short path,
such as `C:\p22-replay`, to stay within Windows path limits on long repository names.
A fresh output directory
is required: scripts refuse to overwrite a prior experiment. Reserve at least 1 GB
of free space for safe operation; verbose native results are stored compressed.

From this reproduction directory, use PowerShell:

```powershell
python prepare_reparo_replay_inputs.py
python run_replay.py
```

To replay with already acquired local bytes, avoiding fresh downloads:

```powershell
python prepare_reparo_replay_inputs.py --archive 'C:\path\reparo-public-snapshot.zip' --opa 'C:\path\opa_linux_amd64_static'
python run_replay.py
```

Both paths validate exact input hashes. Existing local inputs may be hard-linked
to conserve storage; they are read-only during native execution. The archive URL
is mutable. A different hash is a hard failure, not a new comparable snapshot.
If the original snapshot is unavailable, the aggregate claims remain recorded but
full replay requires a lawfully held copy of those original bytes. The OPA version
is a qualification runtime, not an established match to the original paper runtime.

The replay performs 1,050 baseline commands, 335 follow-up commands and 19 overlay
commands, then compares all recorded aggregate fields with EXPECTED.json. It
derives candidates and literal requests locally from the acquired files. Baseline
native test failures are expected measurements; controller errors are fatal.
No hosted model calls, credentials or application network access are needed.

## Overlay CLI

`rego_assertion_overlay.py` accepts a package name, JSON list of explicit expected
decisions and literal input objects, and `--contract bool-allow-deny-overrides`.
The caller selects that contract; the tool does not recover application intent.
Example: `python rego_assertion_overlay.py --package authz --cases cases.json
--contract bool-allow-deny-overrides --output typed_assertions.rego`.
Case objects use `case_id`, `expected` (`allow` or `deny`) and `input` (an object).

## Rights and provenance

Authored code: MIT. Authored report: CC BY 4.0. Raw Reparo policies, generated tests,
CSV results, paper sources and the OPA binary are omitted from this distribution.
An explicit redistribution grant for the anonymous artifact was not established.
Acquisition does not relicense third-party material. See the acquisition hashes,
protocols and aggregate expectations. Native raw records are regenerated locally.
The first exploratory witness preceded the frozen corpus/overlay follow-ups.
The original run's disk interruption and one incorrect undefined-value control
fixture are disclosed in the paper; replay uses the corrected collector/control.
