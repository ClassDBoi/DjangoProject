# AUSME 75-Pair Semantic Embedding Benchmark

This directory is a standalone evaluation harness for short scientific/research phrase similarity. It does not read from or write to the Django/MySQL application database.

## Human benchmark

Canonical input: `data/human_semantic_benchmark.csv`

Validated source workbook properties:
- 75 total phrase pairs
- 25 pairs in each reviewer set
- all pair IDs unique
- no exact or reversed duplicate phrase pairs
- every pair has a human similarity score from 1 through 5
- the source workbook assigns one reviewer set per team member; it does **not** contain three independent ratings for every pair

Score distribution:
- 1: 23 pairs
- 2: 3 pairs
- 3: 16 pairs
- 4: 25 pairs
- 5: 8 pairs

Reviewer-set mean scores are very similar (Set 1 = 2.92, Set 2 = 2.88, Set 3 = 2.88).

## First-round model representatives

`config/models.json` contains:

1. `BAAI/bge-m3` — final BGE-M3 use, comparison only
2. `sentence-transformers/all-mpnet-base-v2` — Sentence Transformers / SBERT representative
3. `intfloat/e5-large-v2` — E5 representative
4. `Alibaba-NLP/gte-large-en-v1.5` — GTE representative

All four models are loaded through Sentence Transformers in the new harness. The old BGE-specific `FlagEmbedding` pipeline is not needed for this benchmark.

For E5, the harness applies `query: ` to **both phrases**, following the model-card guidance for symmetric semantic-similarity tasks.

## Why the benchmark ranks models this way

Primary metric: **Spearman rank correlation** between human score and model cosine similarity.

Supplementary metrics:
- Kendall tau-b
- Pearson correlation
- 95% bootstrap confidence interval for Spearman
- worst rank disagreements for manual inspection

Do **not** choose a model because it produces larger average cosine values. Different embedding families have different raw cosine distributions.

## Install

From the project virtual environment:

```powershell
pip install -r .\benchmark\requirements-benchmark.txt
```

The first run will download the configured model weights. BGE-M3, E5-large-v2, and GTE-large-en-v1.5 are large models, so allow several GB of Hugging Face cache space.

## Run all four models

From the Django project root:

```powershell
python .\benchmark\src\run_benchmark.py --device cpu
```

If CUDA is available:

```powershell
python .\benchmark\src\run_benchmark.py --device cuda
```

Run only selected models:

```powershell
python .\benchmark\src\run_benchmark.py --models all_mpnet_base_v2,e5_large_v2 --device cpu
```

## Output

Each run creates a timestamped directory under `benchmark/results/` containing:

- `manifest.json` — model IDs, dimensions, revisions when available, package versions, benchmark SHA256, device and run settings
- `pair_scores.csv` — human score plus each model's cosine for every pair
- `model_summary.csv` — Spearman, bootstrap CI, Kendall tau-b, Pearson and runtime
- `score_by_human_rating.csv` — within-model cosine distribution by human rating
- `worst_disagreements_<model>.csv` — pairs with the largest human/model percentile-rank disagreement
- `embeddings/<model>.npz` — normalized vectors for the unique benchmark phrases
- `figures/` — human-vs-model plots and model score-correlation plot
- `report.md` — ranked summary

## Selection rule

Use Spearman as the primary first-round ranking, then inspect:

1. the confidence intervals,
2. Kendall tau-b,
3. the worst disagreements,
4. especially lexical-trap pairs scored 1 by humans.

A model that wins this benchmark should be treated as the best candidate for **short scientific phrase semantic comparison**. It is not automatically the best model for full-announcement retrieval/RAG; that is a separate task-specific evaluation.

## Windows / GTE compatibility note

`Alibaba-NLP/gte-large-en-v1.5` uses custom remote modeling code originally
written for Transformers 4.x. The benchmark therefore pins:

- `sentence-transformers==5.7.0`
- `transformers==4.57.6`

Do not upgrade this benchmark environment to Sentence Transformers 6.x /
Transformers 5.x before the four-model comparison is complete. The benchmark
runner now checks this before model loading and exits with a clear message if
GTE is selected under Transformers 5.x.

If the main Django environment needs newer ML packages, use a separate
`.venv-benchmark` for this experiment. Hugging Face's model cache is outside
the virtual environment, so already downloaded model weights can be reused.
