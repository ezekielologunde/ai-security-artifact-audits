# Authorization review: first bounded experiment candidate

18 October 2026. The four portfolio topics share adjacent authorization literature, but no claim is made that one experiment completes credential blast radius, longitudinal permission creep or secure handoffs.

## Prior-art and candidate contribution

ASTRA (arXiv:2510.26702v1) already studies semantic task-to-tool matching, comparing a generated ideal-description/embedding matcher with a reasoning matcher on one-, two- and three-tool tasks. Its experiments calibrate thresholds/prompts on validation servers and evaluate disjoint servers. MiniScope (arXiv:2512.11147v2) already studies task/session-scoped least privilege and permission accumulation; multi-agent delegation is left outside its main scope. Delegation Without Trust (arXiv:2609.00267v1) already tests binding, attenuation, provenance and runtime governance. A first authorization wrapper, scope filter, permission score or agent credential graph is not an established novelty here.

The bounded candidate contribution is a transparent, low-resource baseline and transfer audit of the public semantic-matching artifact. A TF-IDF matcher is an established method, not a proposed algorithmic invention. Its value, if any, is measured dataset-specific performance and calibration/coverage behavior under the same visible task/tool evidence. This is not an authorization-server or least-privilege enforcement experiment.

RQ: How well does a lexical, non-generative baseline distinguish the published appropriate/inappropriate task-tool pairs on ASTRA's held-out servers, and does one validation-calibrated decision rule transfer to the processed TOUCAN test cases?

H1: Adding tool descriptions to names improves macro-F1 relative to constant predictions and a name-only lexical control on the original held-out ASTRA tests. Report failures rather than tuning on test data.

H2: Calibration on ASTRA validation cases does not necessarily transfer to TOUCAN with the same false-positive rate. Report exact false-appropriate predictions; semantic appropriateness is not proof of actual delegated authority or resource-level permission safety.

## Data and fixed analysis boundary

Acquire only revision-pinned JSON splits, tool descriptions and licenses, initially below 15 MB. Inspect schemas, labels, missing fields, class balance and documented split units before implementation. Preserve original bytes. No author code, tool endpoint or generated instruction will be executed.

Use separate validation and test files. Fit lexical representations from allowed tool-catalog descriptions without task labels; threshold calibration uses validation labels only. Freeze feature choices/threshold selection before evaluating test outcomes. Name-only and description-inclusive representations use the same data/calibration rule. Constant-positive and constant-negative controls expose imbalance. Report the real split sizes and unique task/server units rather than assuming independent rows.

If the artifact schema does not support this experiment, amend this design explicitly before scoring. Do not silently use expected-tool/label fields as inputs. Missing descriptions must be counted and handled explicitly. No model training, paid inference or human-subject data collection is needed for this first analysis. Independent validation and comparison against the authors' live model configurations remain separate work.
