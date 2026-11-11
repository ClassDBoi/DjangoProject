# Matching pipeline

Produces the researcher-opportunity matches the website shows. It runs outside the web app,
reads the client data files in `data/`, and writes a `matches.json` that is loaded into the
database with `python manage.py import_matches`.

```
papers (title + abstract) ──► Qwen3-4B ──► research keywords per paper ─┐
                                                                         ├─► MPNet topic-to-topic ──► matches.json ──► import_matches ──► website
announcements ──► scientific sections ──► Qwen3-4B ──► research topics ─┘
```

## What each step does

| Step | Input | Output (under `matching_pipeline/runs/`) |
|---|---|---|
| `prepare-papers` | `data/senior_design_subset.json`, `data/senior_design_full_announcements.json` | `papers/units.jsonl`: one unit per paper with an abstract of at least 40 words |
| `prepare-opportunities` | same files | `opportunities/units.jsonl`: the scientific sections of each announcement, split into windows of up to 1,400 words; `opportunities/sections/` records every keep/drop decision |
| `generate --run papers` | `papers/units.jsonl` | `papers/generations/<unit>.json`: keywords for each paper |
| `generate --run opportunities` | `opportunities/units.jsonl` | `opportunities/generations/<unit>.json`: research topics for each section |
| `match` | both generation folders | `matches/matches.json`, `matches/match_report.md` and CSVs for checking |

How the parts work:

- **Section splitting** (`src/sections.py`): finds headings in each full announcement and keeps
  scientific sections (purpose, background, research objectives, scope) while dropping
  eligibility, budget, application and review instructions. Opportunities without a full
  announcement use their short description if it has at least 40 words; opportunities with
  too little text are listed as not matched.
- **Topic generation** (`src/generate.py`, `src/ollama.py`, `prompts/`): Qwen3-4B through a local
  Ollama server, temperature 0, with a JSON schema so every answer has the same structure.
  Results are saved per unit with a fingerprint of the prompt files, so a stopped run resumes
  where it left off and units made with older prompts are regenerated.
- **Rule filter** (`src/rules.py`): removes opportunity topics that are funding mechanisms,
  administration, eligibility or organization names; career-stage topics (e.g. "early-career
  investigators") are set aside for a future eligibility layer rather than matched.
- **Matching** (`src/match.py`, scoring "v2"): every opportunity topic is compared with every
  researcher keyword using `all-mpnet-base-v2` embeddings. Each opportunity uses up to 10 topics,
  taken evenly from its sections. A pair's evidence is its 3 strongest links, each using a
  different topic and keyword. Topics that are similar to everything (generic topics) count
  less in the ranking. Every match keeps its evidence: which topic matched which keyword, from
  which papers, and how similar they are.

Scores are **semantic similarity** (cosine), not a probability or a likelihood of funding.
Eligibility, deadlines, amounts and agency are not considered here.

## Setup (Windows, PowerShell, from the repository root)

1. Get the client data files from the client and place them in `data/` (they are gitignored; never commit them).
2. Install [Ollama](https://ollama.com) and download the generator model:

   ```powershell
   ollama pull qwen3:4b
   ```

3. Create the pipeline environment (separate from the Django `.venv`):

   ```powershell
   python -m venv .venv-pipeline
   .\.venv-pipeline\Scripts\Activate.ps1
   pip install -r matching_pipeline\requirements.txt
   ```

   The first `match` run downloads the MPNet model (about 440 MB) from Hugging Face.

## Running

```powershell
.\.venv-pipeline\Scripts\Activate.ps1
python matching_pipeline\run_pipeline.py prepare-papers
python matching_pipeline\run_pipeline.py prepare-opportunities
python matching_pipeline\run_pipeline.py generate --run papers
python matching_pipeline\run_pipeline.py generate --run opportunities
python matching_pipeline\run_pipeline.py match
```

- Generation is the slow part (roughly 20 to 30 seconds per unit on a laptop; an hour or more
  for all papers). Stop it with Ctrl+C and run the same command again to continue.
- `--limit 5` on a `generate` step processes only the first units, for a quick check.
- `--mock` runs every step without Ollama or the embedding model. The output is meaningless and
  `import_matches` refuses it; use it only to check that the code runs.

Then load the matches from the Django environment. Always do the dry run first: it checks
that every researcher, opportunity and paper in the file exists in the database.

```powershell
deactivate
.\.venv\Scripts\Activate.ps1
python manage.py import_matches matching_pipeline\runs\matches\matches.json --name matches_YYYY_MM
python manage.py import_matches matching_pipeline\runs\matches\matches.json --name matches_YYYY_MM --apply
```

The imported run becomes the one the website shows (`--no-activate` to load it without
switching). Matches below the cutoff (`--cutoff`, default 0.50) are shown as "No close match".
Earlier runs stay in the database.

## Checking the results

`runs/matches/match_report.md` summarizes the run. The CSVs next to it help review it:

- `opportunity_topics.csv`: every topic per opportunity, whether it was used, removed by a rule or set aside for eligibility.
- `researcher_terms.csv`: the keywords each researcher is matched on, with the papers they came from.
- `near_duplicate_topics.csv`: topic pairs that are almost the same (similarity ≥ 0.85), for a human to confirm or merge.

`runs/opportunities/sections/kept_text.md` shows exactly which announcement text the model saw.
Everything under `runs/` contains client text and is gitignored.

## Configuration

`config/pipeline.json` holds the model names, the pinned MPNet revision, generation settings and
matching settings. Changing a prompt regenerates outputs automatically; if you change the
generator model or its settings, delete `runs/<run>/generations/` first so nothing old is reused.
After any model or prompt change, rerun the affected steps and review the results with the team before importing (see `docs/DECISIONS.md`
for how the current choices were made).
