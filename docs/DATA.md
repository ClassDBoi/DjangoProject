# Data file reference

The client data comes in two JSON files, kept in `data/` and never committed:

| File | Loaded by | Read by the matching pipeline |
|---|---|---|
| `data/senior_design_subset.json` | `python manage.py import_dataset <file>` | Yes |
| `data/senior_design_full_announcements.json` | `python manage.py import_full_announcements --input <file> [--apply]` | Yes |

New or supplemental data must follow the structures below. The matching pipeline reads
these files, not the database (see "Adding or updating data" in the main README), so every
record the website should match must be in them.

All examples on this page are invented for illustration.

## `senior_design_subset.json`

The top level is an object with three lists:

```json
{
  "researchers":   [ ... ],
  "papers":        [ ... ],
  "opportunities": [ ... ]
}
```

All three keys must be present (a list may be empty). `import_dataset` loads them in this
order in a single transaction: if any record fails, nothing is written.

### `researchers[]`

| Field | Type | Required | Notes |
|---|---|---|---|
| `auid` | string, max 20 chars | Yes | Unique researcher ID (the existing data uses three letters and four digits, e.g. `"ABC1234"`). Primary key: re-importing the same `auid` updates the researcher. |
| `name` | string, max 255 | Yes | Display name. |
| `title` | string, max 255 | No | Job title. |
| `department` | string, max 255 | No | Shown in the app and used for filtering. |
| `college` | string, max 255 | No | Used for filtering and the college badge. Spell each college the same way every time; images in `frontend/src/config/collegeImages.js` are matched by exact name. |
| `expertise` | list | No | Present in the client file but **not imported** (empty in the current data). |

```json
{ "auid": "ABC1234", "name": "Jane Doe", "title": "Associate Professor",
  "department": "Biological Sciences", "college": "College of Sciences and Mathematics",
  "expertise": [] }
```

### `papers[]`

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | integer | Yes | Unique paper ID. Primary key: re-importing the same `id` updates the paper. Must match `paper_id` in the full announcements file. |
| `title` | string | Yes | Used by the matching pipeline. |
| `authors_display` | string | No | Author list as it should be shown. |
| `publication_date` | string `YYYY-MM-DD` or `null` | No | Used for sorting. A value that is not a valid date in this format is stored as empty. |
| `published_in` | string, max 255, or `null` | No | Journal or venue. |
| `total_citations` | integer | No | Missing or `null` is stored as 0. |
| `abstract` | string or `null` | No | `null` in the current data; abstracts are supplied in the full announcements file instead (see below). |
| `summary` | string or `null` | No | Stored only. |
| `keywords` | list of `{ "keyword": string (max 255), "score": number }` | No | Client-provided keywords, shown in the app. A keyword may appear only once per paper. **Replaced** on every re-import of the paper. The matching pipeline generates its own keywords and does not use these. |
| `researcher_auids` | list of strings | Yes, for matching | Links the paper to researchers. AUIDs not in `researchers[]` are skipped (the import prints how many). A researcher is matched only through their linked papers. |

```json
{ "id": 1000001, "title": "Example Paper Title", "authors_display": "J. Doe; A. Smith",
  "publication_date": "2025-03-14", "published_in": "Example Journal", "total_citations": 12,
  "abstract": null, "summary": null,
  "keywords": [ { "keyword": "Soil Microbiology", "score": 0.82 } ],
  "researcher_auids": ["ABC1234"] }
```

### `opportunities[]`

| Field | Type | Required | Notes |
|---|---|---|---|
| `opp_id` | integer | Yes | Unique opportunity ID. Primary key: re-importing the same `opp_id` updates the opportunity. Must match `opp_id` in the full announcements file. |
| `title` | string | Yes | |
| `agency` | string, max 255 | No | Shown and used for filtering. |
| `category` | string, max 255 | No | |
| `estimated_funding`, `award_floor`, `award_ceiling` | string or number, or `null` | No | Dollar amounts, e.g. `"500000.00"`. Up to 13 digits before the decimal point and 2 after. |
| `due_date` | ISO 8601 date-time string or `null` | No | Include a time zone offset, e.g. `"2026-12-01 17:00:00-05:00"` or `"2026-12-01T17:00:00-05:00"`. Used for the deadline badge. A value in another format is stored as empty. |
| `summary` | string or `null` | No | Stored only. |
| `description` | string | No | Short description, may contain HTML. Shown in the app. Used for matching when there is no full announcement, or when little scientific text is found in it (see below). |
| `topics` | list of `{ "topic": string (max 255), "score": number }` | No | Client-provided topics. **Replaced** on every re-import. Not used by the matching pipeline. |
| `domains` | list of `{ "domain_name": string (max 255), "confidence_score": number, "rationale": string, "is_primary": boolean }` | No | Client-provided domains. **Replaced** on every re-import. |
| `keywords` | list | No | Present in the client file but **not imported**. |

```json
{ "opp_id": 900001, "title": "Example Research Program", "agency": "Example Agency",
  "category": "Discretionary", "estimated_funding": "1000000.00", "award_floor": null,
  "award_ceiling": "250000.00", "due_date": "2026-12-01 17:00:00-05:00", "summary": null,
  "description": "<p>Short description of the program ...</p>",
  "topics": [ { "topic": "Water Quality", "score": 0.9 } ],
  "domains": [ { "domain_name": "Environmental Science", "confidence_score": 0.8,
                 "rationale": "Program focuses on water resources.", "is_primary": true } ],
  "keywords": [] }
```

## `senior_design_full_announcements.json`

Long text that supplements the records above:

```json
{
  "opportunities": [ { "opp_id": 900001, "full_announcement": "Full announcement text ..." } ],
  "papers":        [ { "paper_id": 1000001, "description": "Paper abstract ..." } ]
}
```

| Field | Type | Notes |
|---|---|---|
| `opportunities[].opp_id` | integer | Must already exist (import `senior_design_subset.json` first). Duplicate IDs stop the import. |
| `opportunities[].full_announcement` | string or `null` | Full announcement text (plain text or HTML). Stored in `Opportunity.full_announcement`. |
| `papers[].paper_id` | integer | Must already exist. Duplicate IDs stop the import. |
| `papers[].description` | string or `null` | The paper's **abstract**. Stored in `Paper.abstract`. |

`import_full_announcements` never creates papers or opportunities, is a dry run unless
`--apply` is given, and only fills empty fields unless `--overwrite` is given.

## What the matching pipeline needs

A record is matched only if it has enough text:

- **Papers:** the abstract (`description` in the full announcements file, otherwise
  `abstract` in the subset file) must have at least 40 words. Shorter or missing abstracts
  are skipped. A researcher with no usable papers gets no matches.
- **Opportunities:** with a `full_announcement`, the pipeline keeps only its scientific
  sections (purpose, background, objectives, scope) and adds the short `description` when
  fewer than 300 words are kept. Without a full announcement, the short `description` is
  used if it has at least 40 words. Otherwise the opportunity is shown as not matched
  ("insufficient text").
- Full announcements work best when they keep the original headings on their own lines
  (for example "Section I. Funding Opportunity Description"), because the section
  splitter uses them to separate scientific text from eligibility and application
  instructions. Check `matching_pipeline/runs/opportunities/sections/kept_text.md` after
  `prepare-opportunities` to see exactly what was kept for each new opportunity.

## Checklist for new data

1. Use new, unique IDs (`auid`, paper `id`, `opp_id`); reusing an ID overwrites that record.
2. Add each new paper's abstract and each new opportunity's full announcement to the full
   announcements file under the same IDs.
3. List each paper's researchers in `researcher_auids`, and add those researchers to
   `researchers[]`.
4. Validate the JSON (for example `python -m json.tool data\senior_design_subset.json > $null`)
   and back up the database before importing.
5. Import, rerun the matching pipeline, and import the new matches under a new run name.
