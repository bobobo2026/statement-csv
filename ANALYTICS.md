# Analytics (free funnel)

No third-party analytics account required.

## What is counted

Aggregate counters only (in `tmp/stats.json`, override with `STATS_PATH`):

- `page_view` — `/` and `/pricing`
- `file_selected` — client ping when a PDF is chosen
- `parse_ok` / `parse_fail`
- `download_csv` / `download_xlsx`
- `balance_pass` / `balance_fail` / `balance_unknown`

No filenames, PDF bytes, or account numbers are stored.

## Endpoints

- `GET /api/stats` — public JSON counters
- `POST /api/event` — `{ "event": "file_selected" }` (allowed events only)

## Optional later

To add Plausible/Umami/GA4, set a script snippet in templates and document the site ID here.
Leave `PADDLE_CHECKOUT_ENABLED` unset (checkout stays off).

## SEO endpoints (shipped)

- `GET /robots.txt` — allows public pages; disallows `/api/`
- `GET /sitemap.xml` — home, pricing, privacy, guides
- Open Graph + Twitter card + canonical on HTML templates

