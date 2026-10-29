# site — presentation

**Scope:** from the fit's results to the published page. A change of display touches only this part.

Reads `model/fit-cache.json` (never the model's code), the build's `data/build/data.csv` and group map, the catalogue, and
(for the effort-ladder report) `data/registry/models.json` with the makers of `data/schema/vocab.json`; writes the served files at
the repository root (`index.html`, `claude-models-head-to-head.html`, `robots.txt`, `sitemap.xml`, `llms.txt`, the IndexNow key file).

| File | Role |
|---|---|
| `build.py` | the generator: `python3 site/build.py` (Python standard library and Node.js only) |
| `config.py` | where the page is published, its titles, ownership keys, the data file's URL (`DATA_URL`), the configurations' order and labels |
| `grids.py` | reads the fit's cache, checks its fingerprint and convergence; the effort-ladder report (thinking off a rung below the levels, or a switch compared with thinking on only: vocab maker `thinking`) |
| `sources.py` | the sources table from the rows of `data/build/data.csv` in the fit, their groups through `data/build/group-map.json` to `data/catalog/groups.json` |
| `seo.py` | head tags and JSON-LD, root files, the date of the last content change (`content-date.json`) |
| `duels.py` | the head-to-head page: a comparator for any two models shown, and the current pairs written out (rules: `docs/DISPLAY-METHODOLOGY.md` § 15) |
| `render.py`, `prerender.js` | runs `app.js` at build time in Node so the served HTML carries the figures |
| `app.js`, `body.html`, `style.css` | the page: charts, tables, tiers, interactions (vanilla JS/SVG) |
| `assets/` | `favicon_png.py`, `og_image.py`: redraw the icon and the share image |

**Publishing a fork:** set `SITE_URL`, `REPO_URL`, and the two ownership keys in `config.py` (see the root README).
