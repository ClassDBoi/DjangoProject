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
| `src/components/common/` | Shared pieces: list toolbar (search, filters, sort), pagination, "Read more" text, college badge, deadline badge, keyword chips, shared styles |
| `src/hooks/` | Data loading (`useList`, `useDetail`, `useFilterOptions`), URL state (`useListParams`) and small UI helpers |
| `src/lib/` | API client (`api.js`) and display formatting (`format.js`) |
| `src/config/collegeImages.js` | Maps college names to images in `public/colleges/` |

## How the list pages work

- **State lives in the URL.** Search text, filters, sort, page and the selected item
  are query parameters (for example `/papers?search=diabetes&sort=citations&order=desc`).
  Refreshing, the back button and shared links keep them. Each page lists its
  parameters and defaults in a `DEFAULTS` object at the top.
- **Searching and sorting happen in the API**, not in the browser, so they keep
  working as the dataset grows.
- **Cross-links:** a paper's researchers link to `/researchers?selected=<AUID>`, and a
  researcher's papers link to `/papers?selected=<id>`.
- **Detail panels** stay beside the list while it scrolls, below the sticky navigation
  bar (`--nav-height` in `src/index.css`). On narrow screens the panel sits below the
  list and the page scrolls to it when an item is selected.

## Adding college images

Put the image files in `public/colleges/`, then map each college name (exactly as in
the database) to its file in `src/config/collegeImages.js`. Colleges without an
image show their initials.
