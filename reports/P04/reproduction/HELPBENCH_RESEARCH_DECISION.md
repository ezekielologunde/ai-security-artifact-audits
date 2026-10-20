# HelpBench scorer audit: research decision — 19 October 2026

The P04 candidate asks about the security of AI advice. HelpBench already evaluates advice against expert rubrics, so a generic text-quality scorer or LLM judge is not a new contribution. The measured increment here concerns **evaluation integrity in one content-pinned public scorer**. It does not solve whether people act safely on AI advice or whether recommended commands preserve services.

The source-informed exploratory questions, frozen before score outcomes in `HELPBENCH_SCORER_PROTOCOL.json`, are:

1. Does a true numerical zero remain distinct from an unavailable score under the released negative-subscale inversion?
2. What do missing, duplicate and malformed judgments do under an explicitly complete-rubric input contract?
3. Do the 450 released expert records exercise an affected numerical endpoint?

The source-derived expectations are a zero/None distinction failure, preserved complete-case overall scores, and a coverage-validation boundary. These were not blind field hypotheses: source and original tests were inspected first. The actual natural endpoint counts were unknown until the amended exact identity/text join completed. The first join failed because question IDs were integers and expert IDs decimal strings; the original script, failure and canonicalization amendment are preserved.

## Contribution supported by current evidence

All 450 overall scores agree with released expert_score. Applicable negative-factual and negative-delivery helper endpoints lose 19/439 and 39/450 numeric values respectively; every lost value is 1 under the helper's explicit inversion. The one-line zero/None comparator recovers those endpoints without changing overall scores. Ten controlled fixtures characterize API behavior, including three malformed/incomplete numeric acceptances and a non-string decision exception. None of those malformed cases occurred in the released expert records. Nine original tests and nine independent audit checks pass.

A separately dated post-hoc analysis shows a conditional skip-None consumer's helper-value mean shifting from 0.0812 (420 records) to 0.1210 (439) and from 0.2672 (411) to 0.3307 (450) on this expert sample. These are weighted subscale values, not percentages of users harmed or replications of the paper's model means. No 18-model ranking or published figure was reconstructed.

## Novelty boundary and paper decision

Truth-value semantics, input validation, missing-data bias and rubric scoring are established. A None guard or strict adapter is not an algorithmic invention. Exact-name/function/bug searches did not identify a primary earlier report of this specific content-pinned condition, but search returns were sparse; anonymous source history/issue status is not exposed. This is not proof of first discovery or field-wide novelty. Current author publication pages still point to the same paper rather than a verified newer scorer release.

The evidence supports a short preliminary artifact-audit technical note with exact hashes, controlled cases, released-record denominators and a minimal correction comparator. Independent reproduction remains pending. It does not justify claiming that the paper's overall results are wrong, advice became safer, or the original P04 human-outcome gap is solved. Preserve P05 patch agreement and SecRespond as separate studies/data; do not merge their denominators into this audit.
