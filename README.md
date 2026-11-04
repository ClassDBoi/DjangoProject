# AUSME: Researcher to Funding Opportunity Matching

Auburn University Senior Design project. A web application for browsing Auburn
researchers, their papers and federal funding opportunities, with semantic
matching of researchers to opportunities under development.

- **Backend:** Django + Django REST Framework (`SeniorDesign_AUSME/` project, `researchdata/` app)
- **Database:** shared MySQL (connection settings in `.env`, never committed)
- **Frontend:** React + Vite (`frontend/`)

## Repository layout

| Path | What it is |
|---|---|
| `SeniorDesign_AUSME/` | Django project: settings, URL routes |
| `researchdata/` | Django app: models, API views, management commands, tests |
| `frontend/` | React/Vite web app (see `frontend/README.md`) |
| `benchmark/` | Standalone embedding-model benchmark (no database access) |
| `docs/API.md` | REST API reference |
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

## Semantic matching (status)

Researchers are matched to opportunities topic to topic: keywords generated from each
researcher's papers are compared with topics extracted from the scientific sections of
each announcement, using the `all-mpnet-base-v2` embedding model. Every match keeps
its evidence (which topic matched which keyword, and from which paper). Scores are
semantic similarity, not a probability or likelihood of funding. This pipeline runs
outside the web app for now; its results are not yet in the database or the frontend.
