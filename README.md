# AUSME: Researcher to Funding Opportunity Matching

Auburn University Senior Design project (fall 2026). A web application for browsing
Auburn researchers, their papers and federal funding opportunities, and for seeing which
opportunities fit each researcher's work, with the evidence for every match.

- **Backend:** Django + Django REST Framework (`SeniorDesign_AUSME/` project, `researchdata/` app)
- **Database:** MySQL 8, hosted by your team (connection settings in `.env`, never committed)
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
| `docs/DATA.md` | Structure of the client data files, for adding or updating data |
| `start-dev.ps1` | Starts Django and Vite together on Windows |
| `data/` | Client data files. **Gitignored: never commit them.** Obtain them from the client. |

## What you receive outside the repository

The repository contains code only. Get these from the client:

| Item | Used for |
|---|---|
| Database export (`.sql` file made with `mysqldump`) | Restoring the complete database: client data, full announcements and the current matches |
| `data/senior_design_subset.json` | Client data file; needed by the matching pipeline and to re-import or extend the data |
| `data/senior_design_full_announcements.json` | Full announcement text; same uses |

All three contain client data. Never commit them or share them outside the project.

## First-time setup (Windows, PowerShell)

Requirements: Python 3.12+, Node.js 20+, MySQL Server 8 (with the `mysql` command-line
client on your PATH).

### 1. Code and dependencies

```powershell
git clone https://github.com/ClassDBoi/DjangoProject.git
cd DjangoProject

# Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Frontend
cd frontend
npm ci
cd ..
```

### 2. Create the database and accounts
Please note that ONE of the team members will need to host this and ensure it is running consistently. \
To provide access for the other group members we used a Tailscale network, allowing developer devices to access the port used by the MySQL database. Tailscale does not have to be used for this, but you will need something setup to allow remote access to the server port.
Sign in to MySQL as an administrator (`mysql -u root -p`) and run the following, with
your own passwords:

```sql
CREATE DATABASE senior_design CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- App account: used by the website and import commands (read/write rows only)
CREATE USER 'senior_design_user'@'localhost' IDENTIFIED BY 'choose-a-password';
GRANT SELECT, INSERT, UPDATE, DELETE ON senior_design.* TO 'senior_design_user'@'localhost';

-- Admin account: used only for schema changes (migrations)
CREATE USER 'senior_design_admin'@'localhost' IDENTIFIED BY 'choose-another-password';
GRANT ALL PRIVILEGES ON senior_design.* TO 'senior_design_admin'@'localhost';
```

### 3. Restore the database export

```powershell
cmd /c "mysql -u senior_design_admin -p senior_design < path\to\ausme_db_export.sql"
```

(`cmd /c` is needed because PowerShell does not support `<` input redirection.)

The export contains every table, including Django's migration history and the active
matching run, so no import commands or pipeline runs are needed to get a working site.

### 4. Configure `.env`

Copy `.env.example` to `.env` in the project root and fill it in with the app account:

```
DB_NAME=senior_design
DB_USER=senior_design_user
DB_PASSWORD=...
DB_HOST=127.0.0.1
DB_PORT=3306
DJANGO_SECRET_KEY=...
```

Generate a secret key with:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 5. Check the setup

```powershell
python manage.py check
$env:DB_USER = "senior_design_admin"; $env:DB_PASSWORD = "<admin password>"
python manage.py migrate        # should report "No migrations to apply"
Remove-Item Env:DB_USER, Env:DB_PASSWORD
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
# API tests use a temporary SQLite database, so they never touch the MySQL data
python manage.py test researchdata --settings=SeniorDesign_AUSME.settings_test

# Frontend lint and production build
cd frontend
npm run lint
npm run build
```

## Data rules

- Client data (the JSON files, database exports and any client-supplied text) must never
  be added to the repository.
- The client's records live in the original tables (researchers, papers, keywords,
  opportunities). Data created by this project (for example, matches) goes into separate
  `ausme_*` tables rather than changing the client's records.
- The app account can read and write rows but cannot change the schema. Migrations must be
  run with the admin account (see "Schema changes" below).

## Semantic matching

Researchers are matched to opportunities topic to topic: keywords generated from each
researcher's papers are compared with research topics extracted from the scientific
sections of each announcement, using the `all-mpnet-base-v2` embedding model. Every
match keeps its evidence (which topic matched which keyword, and from which paper).
Scores are semantic similarity, not a probability or likelihood of funding;
eligibility and deadlines are not checked.

The matches are produced outside the web app by `matching_pipeline/` (setup and steps in
`matching_pipeline/README.md`) and imported into the `ausme_*` tables:

```powershell
# Dry run first: checks every researcher, opportunity and paper exists and prints counts
python manage.py import_matches matching_pipeline\runs\matches\matches.json --name matches_YYYY_MM
python manage.py import_matches matching_pipeline\runs\matches\matches.json --name matches_YYYY_MM --apply
```

The imported run becomes the one the website shows. Matches below its semantic
similarity cutoff (default 0.50, chosen from the team's blind review of matches)
are shown as "No close match". See `docs/DECISIONS.md` for how this was decided.

## Adding or updating data

The matching pipeline reads the client JSON files in `data/`, **not the database**.
New data must therefore be added to those files (same structure) and then imported, so
the database and the pipeline see the same records. Rows added directly to the database
are not matched.

1. Add the new records to `data/senior_design_subset.json` (and their full announcements
   or abstracts to `data/senior_design_full_announcements.json`).
2. Back up the database first (see "Backing up the database").
3. Import:

   ```powershell
   python manage.py import_dataset data\senior_design_subset.json
   python manage.py import_full_announcements --input data\senior_design_full_announcements.json
   python manage.py import_full_announcements --input data\senior_design_full_announcements.json --apply
   ```

   - `import_dataset` writes immediately and updates existing rows by ID, so re-running it
     with an extended file is safe.
   - `import_full_announcements` is a dry run unless `--apply` is given. It never creates
     papers or opportunities and only fills empty fields unless `--overwrite` is given.
4. Rerun the matching pipeline (`matching_pipeline/README.md`). Keywords and topics already
   generated are reused, so only new papers and announcement sections go through the model.
5. Import the new matches under a new run name (`import_matches ... --name matches_YYYY_MM`).
   Earlier runs stay in the database.

The 0.50 cutoff was chosen from a review of the original 25 researchers and 25
opportunities. After a large addition, rate a fresh sample of matches before relying on it.

## Backing up the database

```powershell
mysqldump --single-transaction --no-tablespaces --default-character-set=utf8mb4 -h 127.0.0.1 -P 3306 -u senior_design_admin -p senior_design > ausme_db_YYYY_MM.sql
```

This writes every table and row to one `.sql` file, which can be restored with the command
in setup step 3. The file contains client data: store it outside the repository.

## Schema changes

Changes to `researchdata/models.py` need a migration, run with the admin account. Set it
for one PowerShell session only (these override `.env`):

```powershell
python manage.py makemigrations researchdata
$env:DB_USER = "senior_design_admin"; $env:DB_PASSWORD = "<admin password>"
python manage.py migrate
Remove-Item Env:DB_USER, Env:DB_PASSWORD
```
