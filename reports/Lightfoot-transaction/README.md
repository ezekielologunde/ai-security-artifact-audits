# Committed Vector State After a Later Abort: A Lightfoot Audit and Bounded Repair

Author: Ezekiel Ologunde, Independent researcher, Boston, USA.

Two file-backed deferred-save storage controls show vector rollback despite correct SQL rows; four flush/in-memory controls preserve state. Native retrieval uses deterministic injected embeddings: all 16 post-deletion query observations exclude retired text and final-ranked retired IDs while preserving survivor context. No deleted-text disclosure or learned-model efficacy claim.

This directory supplies the four-page ACM-style technical preprint, Overleaf
source archive, frozen reproduction archive and unpacked reproduction files.
External peer review is not required to prepare or release this preprint.
No external preprint-server submission is represented by this GitHub release.

## Replay

Use a fresh extraction and Python 3.12.14. From the `reproduction` directory:

```powershell
python -m pip install numpy==2.2.6 scipy==1.15.3 rank-bm25==0.2.2
python run_lightfoot_rollback_controls.py
python run_lightfoot_native_boundary.py
python verify_lightfoot_native_boundary.py
```

The exact 42-member archive was replayed from a clean extraction; all three commands exited zero and scientific outcomes matched. Timing, timestamp-bearing NPZ container byte hashes and the dependent receipt hash are excluded from comparison; vector values, row content, identifiers, graph fingerprints and context are compared.

The recorded clean replay used the existing pinned Windows environment, not a
fresh operating system or independent replication. Publication checks revalidate
archive members and manuscript identities; they do not rerun experiments.
The frozen reproduction metadata and any blank review form are historical
preparation artifacts; they impose no publication prerequisite.

## Rights

Authored report: CC BY 4.0. Authored code: MIT. Selected upstream source retains
its bundled MIT notice and attribution. No model weights, private user data or
hosted model calls are included. Read PUBLICATION.json and the paper for scope.

## Bounded repair extension

The revised paper adds a paired repair comparison. The original preserves 4/6 live controls and 2/4 file reopen states; an entry-snapshot-only repair preserves 6/6 and 3/4; snapshot restoration with dirty empty indexes preserves 6/6 and 4/4. The failed intermediate repair, import/runtime correction and verifier correction remain disclosed. This is a standard storage repair, not a new transaction algorithm, tested disclosure fix or RAG-wide erasure guarantee.

The original 42-member reproduction.zip and unpacked files retain their bytes. Download [repair-reproduction.zip](repair-reproduction.zip) separately into a fresh directory. Its 61 members include 60 manifest-listed inputs, all 27 selected upstream MIT files, frozen results and the patch. Run:

```powershell
python -m pip install -r requirements.txt
python REPLAY.py
```

Both native replay commands passed from a clean extraction using the existing qualification runtime; normalized original/final outcomes match and all packaged input bytes remain unchanged. The intermediate repair is preserved as recorded evidence, not rerun by this final replay. No independent operating-system replication, hosted model, credential or external preprint-server submission is claimed.
