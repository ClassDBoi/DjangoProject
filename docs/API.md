# REST API

Base URL in development: `http://127.0.0.1:8000/api/` (the Vite dev server also
proxies `/api` there). All endpoints are read-only `GET` requests returning JSON.

## Common list parameters

| Parameter | Meaning |
|---|---|
| `search` | Case-insensitive text search (fields differ per endpoint, see below) |
| `sort` | Sort key (allowed values per endpoint; unknown values use the default) |
| `order` | `asc` (default) or `desc`. Empty values always sort last. |
| `page`, `page_size` | Paginated endpoints only. `page_size` max 100. |

Invalid numbers are ignored rather than causing errors.

## Researchers

`GET /api/researchers/` returns a plain list (not paginated).

| Parameter | Values |
|---|---|
| `search` | name, AUID, title, department or college |
| `college`, `department` | exact value (see `/api/filters/`) |
| `sort` | `name` (default), `auid`, `department`, `college`, `papers` |

Each item: `auid`, `name`, `title`, `department`, `college`, `paper_count`.

`GET /api/researchers/<auid>/` returns the researcher and their papers (with abstracts and keywords).

## Papers

`GET /api/papers/` is paginated (20 per page by default).

| Parameter | Values |
|---|---|
| `search` | title, authors, journal or keyword |
| `researcher` | AUID of an associated researcher |
| `year_from`, `year_to` | publication year range (inclusive) |
| `min_citations` | minimum total citations |
| `sort` | `title` (default), `date`, `citations`, `journal` |

Response: `{count, total_pages, current_page, results: [...]}`.

`GET /api/papers/<id>/` returns one paper with its researchers, abstract and keywords.

## Funding opportunities

`GET /api/opportunities/` is paginated (10 per page by default).

| Parameter | Values |
|---|---|
| `search` | title, agency, category or description |
| `agency`, `category` | exact value (see `/api/filters/`) |
| `status` | `open` (due date today or later) or `closed` |
| `min_funding`, `max_funding` | estimated total funding range (USD) |
| `sort` | `title` (default), `due_date`, `funding`, `ceiling`, `agency` |

`GET /api/opportunities/<opp_id>/` returns one opportunity with its description,
full announcement, topics and domains.

## Filter options

`GET /api/filters/` returns the values used by the frontend dropdowns:
colleges, departments (with their college), agencies, categories, the range of
publication years and the range of estimated funding.

## Dashboard

`GET /api/dashboard/` returns record counts and text-length statistics for the dashboard charts.
