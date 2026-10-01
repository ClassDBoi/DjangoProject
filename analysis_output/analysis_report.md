# Senior Design dataset analysis

Input: `data\senior_design_subset.json`. Embedding candidate: `BAAI/bge-m3` (8,192 tokens, 1,024 dimensions).
All word counts use whitespace-separated words on HTML-cleaned text.

## Records and missing data

| Metric | Count |
|---|---:|
| Researchers | 25 |
| Papers | 344 |
| Opportunities | 25 |
| Paper Keyword Records | 1720 |
| Unique Keyword Phrases Casefolded | 1466 |
| Paper Researcher References In Source | 399 |
| Paper Researcher Links Matching 25 Researchers | 349 |
| Paper Researcher References To External Researchers | 50 |
| Distinct External Researcher Auids | 32 |
| Provided Opportunity Topics | 80 |
| Provided Opportunity Domains | 63 |
| Duplicate Paper Titles Not Necessarily Duplicate Papers | 1 |
| Missing: researcher expertise | 25 |
| Missing: paper abstract | 344 |
| Missing: paper summary | 344 |
| Missing: paper title | 0 |
| Missing: paper publication date | 7 |
| Missing: paper published in | 33 |
| Missing: opportunity summary | 25 |
| Missing: opportunity description | 0 |
| Missing: opportunities without provided topics | 9 |
| Missing: opportunities without provided domains | 9 |
| Missing: opportunity description with html | 7 |

## Word length distributions

| Field | Min | Q1 | Median | Mean | Q3 | Max |
|---|---:|---:|---:|---:|---:|---:|
| Paper Title | 2 | 9.0 | 12.0 | 12.27 | 15.0 | 28 |
| Paper Abstract | 0 | 0.0 | 0.0 | 0 | 0.0 | 0 |
| Paper Embedding Input | 11 | 22.0 | 26.0 | 26.05 | 29.0 | 50 |
| Opportunity Title | 1 | 6.0 | 8 | 9.2 | 13.0 | 25 |
| Opportunity Clean Description | 4 | 45.0 | 97 | 137.04 | 154.0 | 471 |
| Opportunity Embedding Input | 8 | 64.0 | 109 | 149.24 | 169.0 | 480 |
| Researcher Aggregate Embedding Input | 70 | 359.0 | 397 | 367.12 | 421.0 | 518 |

## Description word-count histogram

| Word range | Opportunities |
|---|---:|
| 0-49 | 7 |
| 50-99 | 6 |
| 100-199 | 7 |
| 200-399 | 2 |
| 400+ | 3 |

## Longest opportunity descriptions

| ID | Title | Clean description words |
|---:|---|---:|
| 313636 | USAID/Afghanistan Request for Information: Higher Education | 471 |
| 315048 | Nuclear Data Interagency Working Group / Research Program | 417 |
| 45638 | Earth Sciences: Instrumentation and Facilities | 404 |
| 357493 | NCCIH Natural Product Mid Phase Clinical Trial (R01 Clinical Trial Required) | 280 |
| 359862 | Maximizing Investigators' Research Award (MIRA) (R35 - Clinical Trial Optional) | 201 |

## BGE-M3 tokenizer results

Actual counts include the special tokens that `AutoTokenizer` adds.

| Input representation | Median tokens | Maximum tokens | > 8192 |
|---|---:|---:|---:|
| Papers | 56.5 | 102 | 0 |
| Opportunities | 167 | 734 | 0 |
| Researchers | 841 | 1069 | 0 |

## Interpretation

- Paper abstracts and summaries are missing in this source subset. For the first demo, use paper titles plus scored-keyword phrases; do not invent abstracts.
- Clean HTML before tokenizing or embedding funding descriptions.
- Some opportunity descriptions are too vague for topic identification; flag for manual review.
- Some paper researcher_auids refer to researchers absent from this 25-person subset. The Django importer should only link researchers that exist in the database.
- Tokenize the exact proposed paper/opportunity/researcher input string, not the title or description in isolation, when evaluating BGE-M3's context requirements.
- Word length measures input size; embedding quality requires separate human review of genuine cross-document similarity examples.
