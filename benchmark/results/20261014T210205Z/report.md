# AUSME semantic embedding benchmark

Run UTC: 2026-10-14T21:02:40.127130+00:00
Benchmark pairs: 75
Benchmark SHA256: `aea3d72c98bfafa2aefbcc8fd6a8bafdeb24661e046bc4d4d326af035cd979a7`

## Model ranking

Primary criterion: Spearman rank correlation between the 1-5 human semantic score and model cosine similarity.
Kendall tau-b is included as a second rank-based measure; Pearson is supplementary only.

| Rank | Model | Family | Spearman ρ | 95% bootstrap CI | Kendall τ-b | Pearson r |
|---:|---|---|---:|---:|---:|---:|
| 1 | all_mpnet_base_v2 | Sentence Transformers / SBERT | 0.8291 | [0.736, 0.889] | 0.6895 | 0.8197 |
| 2 | gte_large_en_v1_5 | GTE | 0.8127 | [0.708, 0.882] | 0.6737 | 0.8052 |
| 3 | e5_large_v2 | E5 | 0.7307 | [0.593, 0.829] | 0.5902 | 0.7116 |
| 4 | bge_m3 | BGE | 0.6641 | [0.505, 0.782] | 0.5268 | 0.6533 |

## Interpretation guardrails

- Do not compare models by average raw cosine magnitude; their score distributions differ.
- This benchmark evaluates short scientific/research phrase similarity only.
- A winner here is a strong candidate for keyword/topic semantic comparison, not automatically the best model for long-document retrieval or RAG.
- Review `worst_disagreements_*.csv` before selecting a model so lexical traps and domain-specific failures are visible.
