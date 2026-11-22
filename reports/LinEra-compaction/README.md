# Interrupted Key Compaction in LinEra: A Bounded Availability Audit

Author: Ezekiel Ologunde, Independent researcher, Boston, USA.

One interrupted core-store compaction makes both retained objects unreadable; a separate single-writer journal comparator preserves retained reads in the tested interruption phases. Forgotten objects remain unreadable. No cryptographic break, physical erasure or production reliability claim.

This directory supplies the three-page ACM-style technical preprint, Overleaf
source archive, frozen reproduction archive and unpacked reproduction files.
External peer review is not required to prepare or release this preprint.
No external preprint-server submission is represented by this GitHub release.

## Replay

Use a fresh extraction and Python 3.12.14. From the `reproduction` directory:

```powershell
python -m pip install cryptography==50.0.2
python -B run_linera_compaction_audit.py
python -B verify_linera_compaction_evidence.py
python -B run_linera_journal_comparator.py
```

The earlier 14-member scientific archive was replayed from a clean extraction. The 17-member licensed archive preserves all 12 executable/scientific members byte-for-byte, adds authored licence notices, and updates only replay/manifest metadata. Its 16 listed members verify. The paper describes the original scientific archive.

The recorded clean replay used the existing pinned Windows environment, not a
fresh operating system or independent replication. Publication checks revalidate
archive members and manuscript identities; they do not rerun experiments.
The frozen reproduction metadata and any blank review form are historical
preparation artifacts; they impose no publication prerequisite.

## Rights

Authored report: CC BY 4.0. Authored code: MIT. Selected upstream source retains
its bundled MIT notice and attribution. No model weights, private user data or
hosted model calls are included. Read PUBLICATION.json and the paper for scope.
