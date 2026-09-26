# Vinnsýn

Vinnsýn is a public, interactive view of the Icelandic job market. It presents
an observed historical Alfreð archive through filters and views for job area,
provisional profession, skills, geography, advertiser, and time.

The public website is deliberately static: visitors receive a reviewed,
allowlisted data snapshot rather than a connection to the research database.
This makes the site fast, simple to host, and keeps raw source material,
database credentials, and internal research workflow private.

## How it works

```text
PostgreSQL market archive → export_market.py → web/data/market.json → public website
```

The PostgreSQL database and collection scripts run privately on the maintainer's
machine or server. The deployed website does not connect to that database, run
an API, or require an always-on backend.

## What is included

- `web/` — independently deployable Vite + React application and the public,
  allowlisted `market.json` snapshot.
- `src/vinnsyn/` and `scripts/` — the standalone market collection, archive
  recovery and enrichment pipeline.
- `sql/` — only the market archive schema, migrations and views.
- PostgreSQL database `vinnsyn` — the copied public-market archive, including
  source observations and preserved historical page evidence.

The local archive was copied without re-importing: 31,235 market listings,
63,093 enrichments, 34,638 observations, 38,549 discovery records and 31,958
preserved live-page documents. It does not contain private
workflow tables.

## Run locally

```bash
npm install --prefix web
npm run dev --prefix web
```

Open the address Vite reports (normally `http://127.0.0.1:5174`). Create a
production build with:

```bash
npm run build --prefix web
```

The production files are written to `web/dist/`.

## Deploy the public site

The `web/` application is ready for static hosting. For Cloudflare Pages using
Git integration, use these settings:

| Setting | Value |
| --- | --- |
| Root directory | `web` |
| Framework preset | React (Vite) |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Production branch | `main` |

Attach a custom subdomain through **Workers & Pages → your project → Custom
domains**. Do not add a Pages CNAME record before associating the hostname in
the Pages dashboard.

## Refresh the public snapshot

Create `.env` from `.env.example` and configure only the Vinnsýn database:

```text
DATABASE_URL=postgresql://USER:PASSWORD@127.0.0.1:5432/vinnsyn
```

Then export the allowlisted static snapshot:

```bash
PYTHONPATH=src python export_market.py
```

The web application reads only `web/data/market.json`; it does not query the
database in a browser or expose raw titles, descriptions, source payloads, or
connection information. Commit and push the changed snapshot to publish an
update through Cloudflare Pages.

## Database maintenance

To create or update the standalone market schema in a fresh `vinnsyn`
database, run:

```bash
PYTHONPATH=src python scripts/setup_database.py
```

The historical discovery, retry, recovery and enrichment scripts operate only
against the database named in this repository's `.env`.

## Collect and enrich the market

The following standalone scripts maintain Vinnsýn's archive. They never use
any other product's code or tables:

```bash
# Capture and import the current public Alfreð listing inventory.
PYTHONPATH=src python scripts/collect_alfred_market.py
PYTHONPATH=src python scripts/import_alfred_market_browser.py data/market/alfred-current.json

# Discover, retrieve and enrich historical listings.
PYTHONPATH=src python scripts/discover_alfred_history.py
PYTHONPATH=src python scripts/retry_alfred_history.py --run-until-empty
PYTHONPATH=src python scripts/enrich_alfred_archive.py

# Rebuild the static website data after an archive update.
PYTHONPATH=src python export_market.py
```

## Data and licensing

The [MIT License](LICENSE) applies to this repository's original source code.
It does not grant rights to third-party content, including job listings,
trademarks, or source-site material. The included public snapshot is a
restricted, reviewed aggregation; use it responsibly and verify source and
usage terms before redistributing data.
