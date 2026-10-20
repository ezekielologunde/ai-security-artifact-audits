# Memory-deletion controlled study: public reproduction supplement

Ezekiel Ologunde, 20 October 2026. Existing study, synchronized named manuscript; not an additional new audit note or an accepted ACM publication.

## Run without model inference

Use CPython 3.12. From `reproduction/`:

```
python outputs/experiment/download_data.py
python -m unittest discover -s outputs/experiment -p test_overlay.py -v
python recheck_memory_evidence.py
python rerun_cache_audit.py
```

The downloader checks the pinned SHA-256 values before writing corpus files. The raw-record check reanalyzes 15,680 recorded storage trials and 792 recorded model calls; it does not rerun them. The cache command executes 96 fresh controlled cases in a new sandbox and compares complete outcome vectors. It refuses to overwrite an existing sandbox. Preserve its result rather than deleting the directory to conceal disagreements.

For fresh storage trials, run `python outputs/experiment/run_experiment.py --out outputs/experiment/reproduction --scratch work/storage-reproduction`, then `python outputs/experiment/analyze.py --results outputs/experiment/reproduction`. Install NumPy for analysis. These potentially long commands are distinct from the validated log reanalysis.

For optional local-model inference, read `outputs/behavioral-experiment/README.md` and use a separate copied project so original logs are preserved. The original acquisition script pins the model revision/runtime tag and checks published model/runtime digests, but rewrites model-manifest.json; preserve the reference manifest first. Runtime is Windows CPU; model download is about 1.12 GB. No paid API is required. Fresh inference was not repeated in the 20 October validation.

## Attribution, scope and differences

Raw corpus JSON files and model/runtime binaries are excluded; acquire them using the manifests. Recorded prompts contain corpus-derived public background excerpts plus synthetic secrets/preferences. LongMemEval's upstream MIT declaration and LoCoMo's CC BY-NC 4.0 terms apply to their respective material, including derived excerpts; see `outputs/datasets/` notices and download-manifest.json. Model notices remain in outputs/behavioral-experiment/. This release assigns no blanket reuse licence to authored material.

Original experiment source and recorded measurements are preserved byte for byte. Two new audit wrappers change only their local SOURCE path to this portable layout; original experiment imports are unchanged. Historical manuscript generators are retained only because recorded source manifests hash them: do not execute them to rebuild the current paper. Anonymous manuscript sources and raw dataset payloads are excluded. Rebuild the current paper from the separate Overleaf archive. The named PDF/Overleaf source acknowledges MemSecBench and omits contact/affiliation. The original private project and original archives are untouched.

Finite controlled storage outcomes do not establish physical erasure, deployment efficacy or universal behavioral forgetting. Matching full-restore/never-seen prompts are a construction check. Direct cache-reference removal is not heap zeroization. Independent human review remains pending.
