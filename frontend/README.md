# AUSME frontend

React 19 + Vite. Pages talk to the Django REST API described in `../docs/API.md`.

## Commands

```powershell
npm ci          # install exact dependency versions from package-lock.json
npm run dev     # development server on http://localhost:5173 (proxies /api to Django)
npm run lint    # ESLint
npm run build   # production build into dist/
```

`VITE_API_BASE` in `frontend/.env` can point at another API server. When it is not
set, requests go to `/api` and the dev server proxies them to `http://127.0.0.1:8000`
(see `vite.config.js`).

## Structure

| Path | Purpose |
|---|---|
| `src/App.jsx` | Routes: `/dashboard`, `/researchers`, `/papers`, `/opportunities` |
| `src/components/dashboard/` | The four pages and the navigation bar |
| `src/components/common/` | Shared pieces: list toolbar (search, filters, sort, applied-filter chips), pagination, match carousel, researcher photo, college badge, deadline badge, field grid, "Read more" text, keyword chips, shared styles |
| `src/hooks/` | Data loading (`useList`, `useDetail`, `useFilterOptions`), URL state (`useListParams`) and small UI helpers |
| `src/lib/` | API client (`api.js`), display formatting (`format.js`) and applied-filter chips (`filters.js`) |
| `src/config/collegeImages.js` | Maps college names to images in `public/colleges/` |
| `src/config/researcherPhotos.js` | Maps researcher AUIDs to headshots in `public/headshots/` |
| `src/config/matchStrength.js` | Where a match counts as "Strong" vs "Possible" (from the team's review of matches) |

## How the list pages work

- **State lives in the URL.** Search text, filters, sort, page and the selected item
  are query parameters (for example `/papers?search=diabetes&sort=citations&order=desc`).
  Refreshing, the back button and shared links keep them. Each page lists its
  parameters and defaults in a `DEFAULTS` object at the top.
- **Searching and sorting happen in the API**, not in the browser, so they keep
  working as the dataset grows.
- **Cross-links:** a paper's researchers link to `/researchers?selected=<AUID>`, and a
  researcher's papers link to `/papers?selected=<id>`.
- **The first result is shown automatically** when a page opens and after every search,
  filter, sort or page change (`useAutoSelectFirst`; `useListParams` clears the
  selection when the list changes). A selection already in the URL, from a shared
  link, a cross-link or the back button, is kept.
- **Applied filters** appear as chips next to the result count; each chip removes its
  filter, and "Clear all" resets search, filters and sort.
- **Detail panels** stay beside the list while it scrolls, below the sticky navigation
  bar (`--nav-height` in `src/index.css`). Short values (department, agency, dates,
  amounts) sit side by side (`FieldGrid`) to keep the panels short. On narrow screens
  the panel sits below the list, and the page scrolls to it when the user picks an
  item (not for the automatic first selection).

## How matches are shown

Matches appear one at a time in a carousel (`MatchCarousel`): researchers on an
opportunity, and opportunities on a researcher, best first. The arrows, the dots or
the left/right arrow keys move between them. Each match shows basic information
(photo or icon, name or title, department and college or agency, funding and due
date) and its strength. Clicking a match opens the evidence ("Matched because ...")
and a button to the matched record; the open/closed choice is kept while moving
between matches. The API's default number of matches (3 per researcher, 5 per
opportunity) is unchanged.

### Match strength

Matches show words, not numbers: a "Strong match" or "Possible match" badge, and
evidence lines that read "closely matches" or "is related to". Raw semantic
similarity scores are easy to misread as percentages or probabilities, so they appear
only when the user hovers over, clicks or taps a badge or evidence line
(`ScoreReveal`). Keyword chips reveal their client-supplied scores the same way.

## Adding college images and researcher photos

- **College images:** put the files in `public/colleges/`, then map each college name
  (exactly as in the database) to its file in `src/config/collegeImages.js`.
- **Researcher photos:** put the files in `public/headshots/` (square, named after the
  AUID, e.g. `ABC1234.jpg`), then map each AUID to its file in
  `src/config/researcherPhotos.js`.

Anything without an image (or whose image fails to load) shows initials instead.
