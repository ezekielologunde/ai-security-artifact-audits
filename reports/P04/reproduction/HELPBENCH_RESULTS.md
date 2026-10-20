# Scorer results and reproduction — 19 October 2026

Source: [HelpBench primary paper](https://arxiv.org/abs/2606.24819), Meiklejohn et al., and its [author-linked repository](https://anonymous.4open.science/r/helpseeking-3829/). Ten selected source/data files total 3,787,321 bytes; acquisition errors: zero. Apache-2.0 source notices and licence are retained. The service exposes no full commit; exact contents are pinned by SHA-256. Scorer SHA-256: `9d75162b153101a3498e4fd3f851ace1d984194d8bb0d177257bfbbff20a413a`. Its displayed anonymization date does not establish publication time.

All 450 questions and 450 expert records join one-to-one after an explicit canonical integer/string ID amendment. Question texts match exactly. All expert judgment sets pass the complete-rubric validation contract. Every original overall score agrees with released expert_score within 1e-9.

| Endpoint | Records with applicable criteria | Original numeric results | Lost numeric endpoint values |
|---|---:|---:|---:|
| Overall | 450 | 450 | 0 |
| Positive factual | 450 | 450 | 0 |
| Negative factual | 439 | 420 | 19 |
| Positive delivery | 190 | 190 | 0 |
| Negative delivery | 450 | 411 | 39 |

The affected helper first computes the fraction of negative-weight points awarded for avoiding the listed behavior, then returns one minus that fraction. The released truthiness conditional treats its valid zero as unavailable, so the inverted value 1 disappears. An explicit None check repairs that numerical endpoint. Truly absent subscales remain unavailable. Do not interpret a maximal weighted rubric subscale as measured real-world harm.

In ten controlled cases, the original scorer accepts an omitted unfavorable criterion (score 1 instead of the full complete-case 0.5), a duplicated favorable criterion (2/3) and an unknown decision token treated as no (score 1). A boolean decision raises AttributeError. The strict adapter rejects these incomplete/malformed inputs. Original unknown-ID and empty-input checks already return unavailable; explicit selected-subset scoring remains supported. These are controlled inputs, not observed model-generated failures.

Nine original tests pass. Nine independent checks recount the affected endpoint conditions directly from rubric signs/labels, verify all 450 scores, preserve both inversion endpoints and legitimate unavailable cases, and reverify all ten acquired hashes. `results/helpbench_scorer_audit.json`, endpoint JSONL, original JUnit and `helpbench_scorer_verification.json` retain evidence. No source/data file was edited, no model called and no new human label created.

The post-hoc `HELPBENCH_AGGREGATE_AMENDMENT.json` records a conditional consumer illustration. If a consumer averages only numeric outputs, the released expert sample yields negative-factual helper mean 0.0812319 over 420 versus corrected 0.1209964 over 439; negative-delivery 0.2671533 over 411 versus 0.3306667 over 450. This does not reconstruct the authors' full 40,500-response pipeline or model ranking. An upstream aggregation implementation may handle missing values differently.

```powershell
python -m pip install -r requirements-helpbench.txt
python download_helpbench.py
python -m pytest -q data/helpbench/files/tests/test_scoring.py
python audit_helpbench_scorer.py
python summarize_helpbench_effect.py
python verify_helpbench_scorer.py
```

The original-test JUnit expected by verification can be generated with `--junitxml=results/helpbench_upstream_junit.xml` (disable pytest cache if preserving the acquired tree). The first identity-join failure, old script and amendment are retained. Further independent review is pending. See `HELPBENCH_RESEARCH_DECISION.md` for the narrow contribution and unresolved end-user/security-outcome questions.
