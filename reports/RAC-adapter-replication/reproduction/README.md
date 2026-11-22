# RAC compensation-result replication and native-adapter extension

This package is a reproducible research artifact, not a new rollback algorithm or
first discovery of returned compensation errors. Antonella Serine's 16 November
2026 first-party report describes the core behavior at the same revision:
https://kla.digital/blog/ai-agent-rollback-recovery-compensation
It explicitly excludes framework-adapter execution. Our extension loads the
unchanged native LangChainToolExecutor file directly with authored invoke-compatible
local tools. It does not run a full LangChain agent, real credentials or a model.

The acquired revision is 068c327ab3f9b79a86a39503946e26320b74b97a.
The initial 21 unchanged recovery-manager tests pass. Eight authored conditions
compare native returns, record status and independent SQLite state. Four explicit
errors are followed by compensated bookkeeping; three use the native adapter.
A separately authored explicit-status guard surfaces all four errors and preserves
both successful controls. It does not finish failed compensations or verify a
success-returning no-op. Fixture state remains the same under the guard.

## Reproduction

Use a fresh directory, Python 3.12.14 and a Windows environment. Run:

    python -m pip install --target tools/rac-runtime -r requirements.txt
    python run_rac_upstream_baseline.py
    python run_rac_compensation_results.py
    python run_rac_compensation_results.py --reject-error-results

The qualified clean replay uses the existing pinned runtime through the optional
RAC_RUNTIME_PATH environment variable instead of reinstalling dependencies. This
is a clean-package replay, not an independent operating-system replication.
EXPECTED.json records original and guarded outcomes with random record IDs omitted.
The initial uppercase/lowercase enum-summary error and its original harness remain
preserved in results/ and the initial script; use the native per-case fields or the
corrected analysis, not the initial zero counter. No native observations were
changed by that analysis correction. Original and guard protocols are source-informed.

## Rights and scope

Authored code MIT; authored report/protocol text CC BY 4.0. Upstream files keep their
own notices. The pinned root LICENSE is Apache-2.0 while pyproject.toml declares MIT;
both original files are preserved without resolving or replacing that discrepancy.
No licence is inferred for unrelated upstream data. This local qualification package
contains selected code and synthetic receipts, no model weights or private data.
No external submission, new stand-alone paper or field-wide priority is claimed.
