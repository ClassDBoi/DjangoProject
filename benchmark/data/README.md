# Benchmark data

- `embedding_semantic_benchmark_75_pairs.xlsx` is the unmodified human-review workbook supplied for the benchmark phase.
- `human_semantic_benchmark.csv` is the canonical machine-readable export used by the model runner.

Source workbook SHA256:
`5299c8e533e388b95656d42ac44d78598a2dfd1cb75615478761d5a955676301`

Canonical CSV SHA256:
`aea3d72c98bfafa2aefbcc8fd6a8bafdeb24661e046bc4d4d326af035cd979a7`

The CSV intentionally omits reviewer names. `reviewer_set` is retained because the benchmark workbook assigns one 25-pair set to each reviewer. The model evaluation uses the human score only; reviewer identity is not a model feature.
