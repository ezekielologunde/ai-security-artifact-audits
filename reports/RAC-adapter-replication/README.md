# Returned Errors and Compensation Bookkeeping

A four-page RAC replication-and-extension preprint by Ezekiel Ologunde,
Independent researcher, Boston, USA. The paper and frozen replay inputs distinguish
known core callback behavior from the measured native-adapter extension.

All 21 selected upstream tests pass. Eight authored conditions and eight matched
status-guard conditions reproduce. Four explicit errors lead to compensated
bookkeeping in the original path; three use the native adapter. The wrapper reports
those failures but does not restore state or detect a success-returning no-op.
This is not a full LangChain application, new recovery algorithm, real credential
revocation study or first discovery of the core behavior. Read the prior report:
https://kla.digital/blog/ai-agent-rollback-recovery-compensation

## Reproduction

From a fresh extraction of reproduction.zip, use Python 3.12.14 and follow
reproduction/README.md. The three commands run the 21 unchanged upstream tests,
the original eight conditions, and the eight status-guard conditions. EXPECTED.json
provides normalized outputs; the manifest verifies all 64 listed input members.
The recorded clean replay used the existing pinned Windows runtime, not a fresh OS.

Some frozen preparation metadata predates the manuscript and describes no paper
or public release. PUBLICATION.json and this README provide the current release
context without rewriting experimental records. The initial enum-summary error is
preserved; the corrected analysis and replay establish four cases, not the initial
zero counter. Random record IDs vary. No hosted model call is required.

## Rights

Authored report: CC BY 4.0. Authored code: MIT. Original upstream root LICENSE is
Apache-2.0 while pyproject metadata declares MIT; both original files are retained.
No third-party notice is replaced by the authored licences. Raw literature webpage,
model weights and dependency binaries are excluded. The Overleaf source uses a
standard installed acmart class, which is not bundled. This GitHub release does
not represent an external preprint-server submission.
