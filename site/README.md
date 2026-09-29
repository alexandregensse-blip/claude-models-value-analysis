# site — presentation

**Scope:** from the fit's results to the published page. A change of display touches only this part.

Reads `model/fit-cache.json` (never the model's code), `raw-data.csv` and the catalogue; writes the served files at
the repository root (`index.html`, `robots.txt`, `sitemap.xml`, `llms.txt`, the IndexNow key file).

| File | Role |
|---|---|
| `build.py` | the generator: `python3 site/build.py` (Python standard library and Node.js only) |
| `config.py` | where the page is published, its titles, ownership keys, the reference couple of the display |
| `grids.py` | reads the fit's cache, checks its fingerprint and convergence, divides by the reference couple |
| `sources.py` | the sources table from the data file and `data/catalog/groups.json` |
| `seo.py` | head tags and JSON-LD, root files, the date of the last content change (`content-date.json`) |
| `render.py`, `prerender.js` | runs `app.js` at build time in Node so the served HTML carries the figures |
| `app.js`, `body.html`, `style.css` | the page: charts, tables, tiers, interactions (vanilla JS/SVG) |
| `assets/` | `favicon_png.py`, `og_image.py`: redraw the icon and the share image |

**Publishing a fork:** set `SITE_URL`, `REPO_URL`, and the two ownership keys in `config.py` (see the root README).
