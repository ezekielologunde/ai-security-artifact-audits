---
language:
- en
license: cc-by-4.0
size_categories:
- n<1K
task_categories:
- text-generation
pretty_name: SABench
tags:
- agents
- tool-use
- safety
- benchmark
- side-effects
configs:
- config_name: default
  data_files:
  - split: train
    path: tasks.jsonl
---

# SABench

SABench (Side-effect-Aware Benchmark) is a benchmark dataset for side-effect-aware
evaluation of tool-using language model agents. It accompanies the paper

> Jiaju Huang, Shaobin Chen, Xinglong Liang, Xinyu Ma, Hao Yang, Wei Ke, Tao Tan, Yue Sun.
> *Task Success Is Not Enough: Side-effect-Aware Evaluation of Tool-Using Language Model Agents.*
> NeurIPS 2026, Track on Evaluations and Datasets.

**Paper:** [Task Success Is Not Enough: Side-effect-Aware Evaluation of Tool-Using Language Model Agents](https://huggingface.co/papers/2610.34167)

Code, deterministic oracle, and the 2,211 evaluation traces from the paper:
https://github.com/hjj194/sabench-artifact

## Dataset

The dataset contains 201 office-style tasks over email, calendar, and ticket workspaces.
Each row in `tasks.jsonl` is one benchmark task with:

- `task_id`, `template_id`, `state_type`, and `trap_type`
- `x`: natural-language user instruction
- `s0`: initial workspace state
- `A_explicit`: explicitly authorized write operations
- `G`: deterministic goal conditions
- ambiguity and dependency metadata used by the oracle

Each task crosses one of four state structures (independent, dependent, externally
reachable, cross-tool) with one of four trap families (ambiguity, mis-targeting,
cascade harm, overreach).

All names, email addresses, organizations, identifiers, and workspace records are
synthetic. The dataset contains no real personal data.

## Intended Use

Evaluating tool-using language model agents for unauthorized state-changing actions
(collateral damage) alongside task success. Scores are specific to this controlled
office-style setting and should not be read as a general deployment-safety guarantee.

## License

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The accompanying code is
released under the MIT license.

## Citation

```bibtex
@inproceedings{huang2026sabench,
  title     = {Task Success Is Not Enough: Side-effect-Aware Evaluation of Tool-Using Language Model Agents},
  author    = {Huang, Jiaju and Chen, Shaobin and Liang, Xinglong and Ma, Xinyu and Yang, Hao and Ke, Wei and Tan, Tao and Sun, Yue},
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS), Track on Evaluations and Datasets},
  year      = {2026}
}
```