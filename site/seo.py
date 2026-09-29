"""What search engines and assistants read: head tags and JSON-LD, the root files (robots.txt, sitemap.xml, llms.txt,
IndexNow key), and the date of the last change to the page's content."""
import datetime, hashlib, html as htmlmod, json, os, re

from config import HERE, ROOT, SITE_URL, REPO_URL, TITLE, SITE_NAME, DESCRIPTION, SITE_HOST, BING_SITE_VERIFICATION, INDEXNOW_KEY


DATE_FILE = os.path.join(HERE, "content-date.json")   # {fingerprint, date} of the last content change (committed)

def content_date(fingerprint):
    """Date of the last change to what the reader gets: the page text, the figures and the data the charts draw.
    The build fingerprints that content; while it matches the one recorded in site/content-date.json the recorded
    date stands, otherwise today's date is recorded with the new fingerprint (commit the file with the change).
    So code, styles, icons or head tags alone never move the visible "Updated" date, JSON-LD dateModified or the
    sitemap lastmod, and a rebuild of an unchanged page changes nothing. Limits: text that app.js draws only at run
    time (tooltips, interactive labels) and attribute text (alt, aria-label) are not fingerprinted; a content change
    reverted after a build keeps the build day unless site/content-date.json is restored with it."""
    try:
        with open(DATE_FILE, encoding="utf-8") as f:
            rec = json.load(f)
        if rec.get("fingerprint") == fingerprint:
            return datetime.date.fromisoformat(rec["date"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    date = datetime.date.today()
    with open(DATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"fingerprint": fingerprint, "date": date.isoformat()}, f, indent=1)
        f.write("\n")
    return date

def content_fingerprint(body, pre, data):
    """sha256 of the content only: title, description, the visible text of the body (pre-rendered blocks
    included, date placeholder not yet filled), the full answer used by llms.txt, and the data behind the charts."""
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", body, flags=re.S | re.I)
    text = re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", text))).strip()
    blob = json.dumps([TITLE, SITE_NAME, DESCRIPTION, text, pre.get("answer-full", ""), data],
                      ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()

def head_tags(date, anchor_label, counts):
    """Title, description, canonical, icon, Open Graph, Twitter card and the JSON-LD Dataset. Every value is on the page."""
    a = lambda v: htmlmod.escape(v, quote=True)
    dataset = {
        "@context": "https://schema.org", "@type": "Dataset",
        "name": TITLE,
        "description": ("What each recent Claude model actually costs, at every effort level — reconstructed from public "
                        "measurements and reduced to a relative cost by chaining same-task comparisons. Aggregated from "
                        f"{counts}; costs and qualities are relative to {anchor_label} = 1.00."),
        "url": SITE_URL, "sameAs": REPO_URL,
        "creator": {"@type": "Person", "name": "Alexandre Gensse", "url": "https://github.com/alexandregensse-blip"},
        "dateModified": date.isoformat(),
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "isAccessibleForFree": True,
        "keywords": ["Claude", "Claude models", "LLM cost", "effort level", "Fable", "Opus", "Sonnet", "Haiku",
                     "benchmark", "Pareto frontier"],
        "variableMeasured": [f"Relative cost per task ({anchor_label} = 1.00)", f"Relative quality ({anchor_label} = 1.00)"],
        "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": SITE_URL + "raw-data.csv"}],
    }
    website = {"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": SITE_URL}
    ld = json.dumps([website, dataset], ensure_ascii=False, indent=1).replace("</", "<\\/")
    return (
        f"<title>{a(TITLE)}</title>\n"
        f'<meta name="description" content="{a(DESCRIPTION)}">\n'
        f'<link rel="canonical" href="{SITE_URL}">\n'
        '<link rel="icon" href="favicon.svg" type="image/svg+xml">\n'
        '<link rel="icon" href="favicon.png" type="image/png" sizes="96x96">\n'   # Google Search ignores SVG icons
        '<meta property="og:type" content="website">\n'
        f'<meta property="og:url" content="{SITE_URL}">\n'
        f'<meta property="og:title" content="{a(TITLE)}">\n'
        f'<meta property="og:description" content="{a(DESCRIPTION)}">\n'
        f'<meta property="og:image" content="{SITE_URL}og-image.png">\n'
        '<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n'
        f'<meta property="og:image:alt" content="{a(TITLE)} — {a(SITE_HOST)}">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        + (f'<meta name="msvalidate.01" content="{a(BING_SITE_VERIFICATION)}">\n' if BING_SITE_VERIFICATION else "") +
        f'<script type="application/ld+json">\n{ld}\n</script>\n'
    )

def write_root_files(date, pre, anchor_label):
    """robots.txt, sitemap.xml, llms.txt and the IndexNow key file, next to index.html. llms.txt reuses the
    full answer computed by app.js (answerFull), so it states the same conclusions as the page."""
    plain = lambda h: re.sub(r"\s+(?=:)", "", re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", "", h)))).strip()
    files = {
        "robots.txt": f"# All robots allowed, AI robots included.\nUser-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n",
        "sitemap.xml": ('<?xml version="1.0" encoding="UTF-8"?>\n'
                        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                        f"  <url><loc>{SITE_URL}</loc><lastmod>{date.isoformat()}</lastmod></url>\n</urlset>\n"),
        "llms.txt": f"""# {TITLE}

> {DESCRIPTION}

{pre.get("answer-full", "")}

Costs and qualities are relative to {anchor_label} = 1.00. They are fused from measurements taken on the same task by a latent-quality model that estimates each benchmark's own scale (method: docs/METHODOLOGY.md in the source repository), from {plain(pre.get(".nsrc", ""))}. Updated {date.isoformat()}. Figures are indicative, derived from public third-party measurements; not affiliated with Anthropic.

## Report

- [{TITLE}]({SITE_URL}): quality vs cost per model and effort level, Pareto frontier, best pick per task tier, normalized cost matrix, method and sources.

## Data

- [raw-data.csv]({SITE_URL}raw-data.csv): every measured row (source, model, effort, task, harness, cost, tokens, score, reference), CC BY 4.0.

## Optional

- [Source repository]({REPO_URL}): generator, method notes, version history.
""",
    }
    if INDEXNOW_KEY:
        files[f"{INDEXNOW_KEY}.txt"] = INDEXNOW_KEY
    for name, text in files.items():
        with open(os.path.join(ROOT, name), "w", encoding="utf-8") as f:
            f.write(text)

