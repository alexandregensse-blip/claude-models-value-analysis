"""Pre-rendering: runs app.js at build time in Node (fake DOM) and puts its output into the served HTML, so that the
figures and tables are there for crawlers that do not run JavaScript."""
import json, os, re, subprocess, sys

from config import HERE


def prerender(app, css):
    """Runs app.js at build time (site/prerender.js, Node, fake DOM) and returns the HTML it writes into the text
    blocks, so crawlers that do not run JavaScript read the conclusions. The browser redraws them on load."""
    try:
        r = subprocess.run(["node", os.path.join(HERE, "prerender.js")], input=json.dumps({"app": app, "css": css}),
                           capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        sys.exit(f"!! PRE-RENDER FAILED (Node is required to build): {getattr(e, 'stderr', '') or e}")
    return json.loads(r.stdout)

def inject(body, pre):
    """Writes the pre-rendered blocks into their empty placeholders in body.html."""
    for key, html in pre.items():
        if key in ("answer-full", "duel-data"):      # data for llms.txt and the head-to-head page, not a block of the page
            continue
        put = lambda m: m.group(1) + html + m.group(m.lastindex)
        if key == ".nsrc":
            pat = r'(<span class="nsrc">)…(</span>)'
        elif key.endswith(" tbody"):
            pat = rf'(<table id="{key[1:-6]}">.*?<tbody>)(</tbody>)'
        else:
            pat = rf'(<(\w+)[^>]*\bid="{key}"[^>]*>)…?(</\2>)'
        body, n = re.subn(pat, put, body, flags=re.S)
        if not n:
            sys.exit(f"!! PRE-RENDER: no empty placeholder for {key!r} in body.html")
    return body

