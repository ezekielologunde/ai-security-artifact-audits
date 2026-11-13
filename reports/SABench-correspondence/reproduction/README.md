# SABench runtime/offline normalization correspondence

Ezekiel Ologunde. Local reproducibility supplement, 12 November 2026. No peer review, priority claim, or new authorization defense.

Requires CPython 3.12 and its standard library only. No package installation, API key, model inference or external service is needed. From a fresh extraction run:

    python replay_sabench.py
    python compare_sabench_normalization.py
    python check_sabench_cli.py
    python verify_replay.py

These commands refuse to overwrite existing experiment work folders. The source snapshot and tasks are bundled so this offline check uses their exact pinned bytes. Both direct and runtime-normalized reports are preserved separately. There are 2,211 recorded traces; normalization changes thirteen calls and nine classifications. It reuses the upstream normalizer, not a new repair algorithm. Aggregate correspondence does not prove the actual author scoring pipeline or independent semantic truth.

The scripts under work/sabench-pinned/scripts include an optional hosted-agent runner: do not execute it for this replay. Only the documented local verifier and the four selected pure normalization functions are used by the listed commands.

Third-party attribution: SABench by Jiaju Huang, Shaobin Chen, Xinglong Liang, Xinyu Ma, Hao Yang, Wei Ke, Tao Tan and Yue Sun. Code/scripts retain MIT (work/sabench-pinned/LICENSE). Traces retain CC BY 4.0 as declared in the upstream README. Tasks retain CC BY 4.0 (data/authorization-refresh-20261112/hf/LICENSE and README). Sources: https://github.com/hjj194/sabench-artifact at 1baf318fbdc55df2d190467a1b6bf91dfc5f6524; https://huggingface.co/datasets/Phaedrus/sabench at 21b40adec3f49d954c524c5c5aa95f30c2cb91fd. Third-party snapshot bytes are unchanged. New authored scripts/reports: copyright 2026 Ezekiel Ologunde; no general reuse licence selected. Upstream licences are unaffected.
