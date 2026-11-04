# AUSME: Researcher to Funding Opportunity Matching

Auburn University Senior Design project (fall 2026). A web application for browsing
Auburn researchers, their papers and federal funding opportunities, and for seeing which
opportunities fit each researcher's work, with the evidence for every match.

- **Backend:** Django + Django REST Framework (`SeniorDesign_AUSME/` project, `researchdata/` app)
- **Database:** shared MySQL (connection settings in `.env`, never committed)
- **Frontend:** React + Vite (`frontend/`)
- **Matching pipeline:** Qwen3-4B (Ollama) + MPNet embeddings (`matching_pipeline/`), run offline

## Repository layout

| Path | What it is |
|---|---|
| `SeniorDesign_AUSME/` | Django project: settings, URL routes |
| `researchdata/` | Django app: models, API views, management commands, tests |
| `frontend/` | React/Vite web app (see `frontend/README.md`) |
| `matching_pipeline/` | Offline pipeline that generates topics and matches (see `matching_pipeline/README.md`) |
| `docs/API.md` | REST API reference |
| `docs/DECISIONS.md` | How the models, filters, scoring and cutoffs were chosen, with the evidence |
| `start-dev.ps1` | Starts Django and Vite together on Windows |
| `data/` | Client data files. **Gitignored: never commit them.** Obtain them from the team. |

## First-time setup (Windows, PowerShell)

Requirements: Python 3.12+, Node.js 20+, access to the shared MySQL database.

```powershell
git clone https://github.com/ClassDBoi/DjangoProject.git
cd DjangoProject

# Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Secrets: create .env in the project root (ask the team for the values)
#   DJANGO_SECRET_KEY=...
#   DB_NAME=...  DB_USER=...  DB_PASSWORD=...  DB_HOST=...  DB_PORT=...

# Frontend
cd frontend
npm ci
cd ..
```

## Running

```powershell
.\start-dev.ps1
```

This opens Django on http://127.0.0.1:8000 and the web app on http://localhost:5173.
To run them separately: `python manage.py runserver` (with `.venv` active) and
`npm run dev` inside `frontend/`.

## Tests and checks

```powershell
# API tests use a temporary SQLite database, so they never touch the shared MySQL data
python manage.py test researchdata --settings=SeniorDesign_AUSME.settings_test

# Frontend lint and production build
cd frontend
npm run lint
npm run build
```

## Data rules

- `data/senior_design_subset.json` and `data/senior_design_full_announcements.json`
  are client data. They are gitignored and were removed from Git history; never add
  them, or any client-supplied text, to the repository.
- The database holds the client's original data. Data created by this project
  (for example, generated topics or matches) goes into separate, clearly named tables
  rather than changing the client's records.
- Normal database accounts can read and write rows but cannot change the schema.
  Migrations must be run with the privileged account.

## Semantic matching

Researchers are matched to opportunities topic to topic: keywords generated from each
researcher's papers are compared with research topics extracted from the scientific
sections of each announcement, using the `all-mpnet-base-v2` embedding model. Every
match keeps its evidence (which topic matched which keyword, and from which paper).
Scores are semantic similarity, not a probability or likelihood of funding;
eligibility and deadlines are not checked.

The matches are produced outside the web app by `matching_pipeline/` (setup and steps in
`matching_pipeline/README.md`) and imported into the project-created `ausme_*` tables:

```powershell
# Dry run first: checks every researcher, opportunity and paper exists and prints counts
python manage.py import_matches matching_pipeline\runs\matches\matches.json --name matches_YYYY_MM
python manage.py import_matches matching_pipeline\runs\matches\matches.json --name matches_YYYY_MM --apply
```

The imported run becomes the one the website shows. Matches below its semantic
similarity cutoff (default 0.50, chosen from the team's blind review of matches)
are shown as "No close match". See `docs/DECISIONS.md` for how this was decided.

## Database updates

The shared database is already loaded; these are for a new or rebuilt database.

- `python manage.py import_dataset data\senior_design_subset.json`: loads the client's researchers,
  papers and opportunities (writes immediately; updates existing rows by ID).
- `python manage.py import_full_announcements --input data\senior_design_full_announcements.json`:
  adds full announcement text (dry run by default, `--apply` to write).
- `python manage.py import_matches`: loads a matching run (above).
- Schema changes need the privileged database account. Set it for one PowerShell session only
  (these override `.env`):

  ```powershell
  $env:DB_USER = "<privileged user>"; $env:DB_PASSWORD = "<password>"
  python manage.py migrate
  Remove-Item Env:DB_USER, Env:DB_PASSWORD
  ```
