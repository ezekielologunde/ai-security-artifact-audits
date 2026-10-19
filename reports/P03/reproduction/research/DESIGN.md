# P03 — Shadow AI inventory: candidate measurement study

Design date: 18 October 2026. Status: literature/data-suitability review; no results yet.

## Prior-art boundary

Generic AI discovery is established: Trusera AI-BOM, Cisco AIBOM and perfecxion-ai's agent scanner already inventory AI components. LLMmap fingerprints model-backed applications. Policy-aware commercial inventory and governance systems also exist. Building another discovery CLI, reconciling an allow-list, or adding uncertainty is not individually novel.

A public synthetic source, Deepa-15/shadowai-enterprise-dataset, distinguishes detector-visible network metadata, investigator evidence and labels. Its suitability must be inspected before treating its labels as unauthorized-use ground truth. Its own synthetic examples do not measure enterprise prevalence.

## Candidate gap and question

Candidate contribution: an empirical observability audit of Shadow AI detection claims, with counterfactual authorization changes that leave network observations fixed, complemented by analysis of the public dataset's label/feature semantics. This is not an assertion that policy-aware detection or indistinguishability arguments are new. Retain this project only if the closest-method review and actual dataset inspection support a useful, reproducible measurement result.

RQ1: Which claimed unauthorized-AI outcomes are identifiable from detector-visible features in a public synthetic dataset, and which require organizational policy or account evidence?

RQ2: When a service's approval changes over time or across organizational identities while network metadata remains identical, how do domain-only, static allow-list and time/identity-scoped policy evidence differ in coverage and incorrect determinate decisions?

H1: Network-only and static organization-wide domain decisions cannot correctly distinguish all constructed same-observation/different-authorization pairs. This is a structural control, not a population prediction or a new machine-learning theorem.

H2: An evaluator using explicit applicable policy, identity and validity intervals resolves the fully observed authored cases while abstaining when necessary evidence is absent or conflicting. This is a controlled reference implementation, not a production detector or guaranteed novel algorithm.

## Evidence and evaluation plan

First inspect pinned source inventories, generator rules, schemas, licenses and public data sizes. Do not execute author code during initial acquisition. Hash every acquired file. Separate AI-service use, organizational authorization and harmful data exposure labels.

For a controlled suite, define observable network records separately from policy/identity evidence and oracle labels. Include approved/denied pairs, time-bound grants, tenant-specific permissions, missing identity, unknown provider, stale policy, conflicts and non-AI controls. Freeze the protocol and authored cases before final execution; the freeze is local, not preregistration or independent ground truth. Preserve all cases and failed hypotheses. Report exact denominators, coverage, false authorized/unauthorized decisions and abstention. No employee monitoring, third-party scanning, paid API calls or live model execution is required.

A naturally occurring enterprise benchmark is not available merely because synthetic records are public. No natural-case accuracy, unauthorized-use prevalence or data-exfiltration inference is supported by a designed conformance experiment.
