# Senior Design dataset analysis

Base input: `data\senior_design_subset.json`.
Supplemental input: `data\senior_design_full_announcements.json`.
Tokenizer diagnostic: `BAAI/bge-m3` (8,192 tokens, 1,024 dimensions).
All word counts use whitespace-separated words on cleaned text.

## Records and missing data

| Metric | Count |
|---|---:|
| Researchers | 25 |
| Papers | 344 |
| Opportunities | 25 |
| Papers With Abstract | 337 |
| Opportunities With Full Announcement | 19 |
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
| Missing: paper abstract | 7 |
| Missing: paper summary | 344 |
| Missing: paper title | 0 |
| Missing: paper publication date | 7 |
| Missing: paper published in | 33 |
| Missing: opportunity summary | 25 |
| Missing: opportunity description | 0 |
| Missing: opportunity full announcement | 6 |
| Missing: opportunities without provided topics | 9 |
| Missing: opportunities without provided domains | 9 |
| Missing: opportunity description with html | 7 |

## Supplemental source validation

| Metric | Count |
|---|---:|
| Source Papers | 344 |
| Source Opportunities | 25 |
| Paper Descriptions Available | 337 |
| Paper Descriptions Missing | 7 |
| Opportunity Announcements Available | 19 |
| Opportunity Announcements Missing | 6 |

## Word length distributions

| Field | Min | Q1 | Median | Mean | Q3 | Max |
|---|---:|---:|---:|---:|---:|---:|
| Paper Title | 2 | 9.0 | 12.0 | 12.27 | 15.0 | 28 |
| Paper Abstract All Records | 0 | 119.0 | 130.5 | 132.45 | 142.25 | 350 |
| Paper Abstract Available Only | 2 | 120.0 | 131 | 135.2 | 143.0 | 350 |
| Paper Embedding Input | 11 | 144.0 | 158.0 | 159.48 | 172.0 | 380 |
| Opportunity Title | 1 | 6.0 | 8 | 9.2 | 13.0 | 25 |
| Opportunity Clean Description | 4 | 45.0 | 97 | 137.04 | 154.0 | 471 |
| Opportunity Short Embedding Input | 8 | 64.0 | 109 | 149.24 | 169.0 | 480 |
| Opportunity Full Announcement Available Only | 2462 | 8501.5 | 9891 | 11470.05 | 12664.5 | 28348 |
| Opportunity Full Announcement Input Available Only | 2472 | 8517.5 | 9911 | 11485.37 | 12681.0 | 28360 |
| Researcher Aggregate Embedding Input | 189 | 2160.0 | 2304 | 2229.8 | 2540.0 | 3417 |

## Paper abstract word-count histogram

| Word range | Papers |
|---|---:|
| 0-0 | 7 |
| 1-99 | 54 |
| 100-199 | 242 |
| 200-399 | 41 |
| 400-799 | 0 |
| 800+ | 0 |

## Full-announcement word-count histogram

| Word range | Opportunities |
|---|---:|
| 0-0 | 6 |
| 1-2499 | 1 |
| 2500-4999 | 0 |
| 5000-9999 | 9 |
| 10000-19999 | 7 |
| 20000-29999 | 2 |
| 30000+ | 0 |

## Longest paper abstracts

| ID | Title | Abstract words | Current embedding-input words |
|---:|---|---:|---:|
| 57876 | Environmental nitrogen losses from commercial crop production systems in the Suwannee River Basin of Florida | 350 | 380 |
| 57882 | Estimation of nitrogen pools in irrigated potato production on sandy soil using the model SUBSTOR | 303 | 332 |
| 57852 | Projected climate and agronomic implications for corn production in the Northeastern United States | 300 | 328 |
| 58802 | Hydrogen membrane separation techniques | 288 | 308 |
| 57825 | Projected heat stress challenges and abatement opportunities for US milk production | 285 | 311 |

## Longest full funding announcements

| ID | Title | Full announcement words | Estimated RAG chunks |
|---:|---|---:|---:|
| 315048 | Nuclear Data Interagency Working Group / Research Program | 28348 | 67 |
| 359145 | Diabetes Research Centers (P30 Clinical Trial Optional) | 24375 | 58 |
| 302346 | OJJDP FY 18 Juvenile Reentry Research and Evaluation Program | 16632 | 39 |
| 353763 | NIH Pathway to Independence Award (Parent K99/R00 Independent Clinical Trial Required) | 13915 | 33 |
| 353761 | NIH Pathway to Independence Award (Parent K99/R00 Independent Basic Experimental Studies with Humans Required) | 13654 | 32 |
| 357493 | NCCIH Natural Product Mid Phase Clinical Trial (R01 Clinical Trial Required) | 11675 | 28 |
| 359862 | Maximizing Investigators' Research Award (MIRA) (R35 - Clinical Trial Optional) | 11035 | 26 |
| 357019 | Bioengineering Partnerships with Industry (U01 Clinical Trial Optional) | 10290 | 25 |
| 357334 | Catalyze: Product Definition for Small Molecules, Biologics and Combination Products - Target Identification and Validation, and Preliminary Product/Lead Series Identification (R61/R33 Clinical Trials Not Allowed) | 10255 | 24 |
| 356811 | BRAIN Initiative: Brain Behavior Quantification and Synchronization- Next Generation Sensor Technology Development (U01 Clinical Trial Optional) | 9891 | 24 |

## Full-announcement RAG planning estimate

Planning assumption: approximately 500 words per chunk with 75 words of overlap.

- Announcements available: 19
- Estimated total chunks: 519
- Estimated chunks per available announcement: median 24, maximum 67.

> This is only a planning estimate. Final RAG chunking should use announcement structure and section headings where possible.

## Opportunities without full announcement

| ID | Title |
|---:|---|
| 275761 | Family Strengthening Scholars |
| 320081 | Ririe Recreation Area Operations and Maintenance |
| 320217 | EARTH MRI-SOUTH CAROLINA |
| 350582 | RFA-DD-18-000 |
| 350630 | RFA-SH-18-000 |
| 350651 | RFA-EH-18-000 |

## Papers without abstract/description

| ID | Title |
|---:|---|
| 9688 | Computer Aided Chemical Engineering |
| 19695 | Operators with Minimal Pseudospectra and Applications to Numerical Ranges |
| 19696 | Positive Semi-Definite Block Matrices and Norm Inequalities |
| 20674 | Convergence - Music & Cultural Legacy |
| 20675 | Narrative - Music by Women Composers for Flute and Piano |
| 20677 | Three Perspectives |
| 31942 | Comparing the Borich model with the Ranked Discrepancy Model for competency assessment: A novel approach. Advancements in Agricultural Development, 2 (3), 96–111 |

## BGE-M3 tokenizer diagnostics

Tokenizer not run. Re-run without `--skip-tokenizer` after installing `transformers` and `sentencepiece` if exact BGE-M3 token lengths are needed.

## Interpretation

- The supplemental source substantially improves paper-level semantic evidence because most papers now have an abstract/description.
- Full funding announcements are intentionally kept separate from the short opportunity description. They are better suited to section-aware chunking/retrieval than to one whole-document embedding.
- Researcher aggregate inputs now include paper abstracts where available, so their lengths may increase substantially. This is another reason to compare task-specific representations rather than force one aggregate vector strategy.
- BGE-M3 token diagnostics remain useful as a historical baseline, but model selection should be based on the separate human semantic benchmark and task-specific evaluation.
- Some opportunity records still have no recovered full announcement; those records should remain flagged rather than having missing text invented.
- The estimated RAG chunk counts are capacity-planning numbers only. Final retrieval experiments should prefer meaningful document sections such as purpose, research scope, eligibility, requirements, and review criteria.
