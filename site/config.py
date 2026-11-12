"""Site settings: where it is published, its titles and ownership keys; the models shown and their colours."""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT  = os.path.join(ROOT, "index.html")   # the served files are generated at the repository root
sys.path.insert(0, os.path.join(ROOT, "data"))
import catalog

# The models the site shows, in legend order (DISPLAY_ORDER), with their label and colour variable (MODELS): the
# catalogue's (data/catalog/models.json), with the site's own additions below. data/catalog/models.json is one of the
# fit's inputs (model/fit.py INPUTS, fingerprinted in model/fit-cache.json): editing its display_order or a colour
# there makes the cached fit stale and the site refuses to build. A model added to the page between two fits goes
# here — SHOW_BEFORE {model: the shown model it is placed before}, COLOUR {model: its colour variable, site/style.css}
# — and moves into models.json at the next fit (Fable 5.2, 12 Nov 2026).
SHOW_BEFORE = {"fable-5.2": "fable-5.1"}
COLOUR = {"fable-5.2": "--fable52"}
DISPLAY_ORDER = list(catalog.DISPLAY_ORDER)
for _m, _b in SHOW_BEFORE.items():
    if _m not in DISPLAY_ORDER:
        DISPLAY_ORDER.insert(DISPLAY_ORDER.index(_b), _m)
MODELS = {m: dict(v, **({"colour": COLOUR[m]} if m in COLOUR else {})) for m, v in catalog.MODELS.items()}

# Publication: every absolute URL derives from SITE_URL (canonical root, trailing slash).
SITE_URL    = "https://claude-models.agensse.com/"
REPO_URL    = "https://github.com/alexandregensse-blip/claude-models-value-analysis"
TITLE       = "Claude models compared: cost vs quality at every effort level"
SITE_NAME   = "Claude cost vs quality"   # site name suggested to Google (JSON-LD WebSite) instead of the bare domain
DESCRIPTION = ("What each Claude model (Fable, Opus, Sonnet, Haiku) costs at every effort level, and which gives "
               "the best quality for the price. Open data, CC BY 4.0.")
# The public data file is the build's data.csv (data/build/data.csv: every measure, today's columns plus its status on
# each axis). The served root files are a whitelist on the server, which data.csv is not in: the page links the file
# on the repository's main branch (raw-data.csv, still served at the root, is the frozen legacy input of 21 Oct).
DATA_URL    = REPO_URL.replace("https://github.com/", "https://raw.githubusercontent.com/") + "/main/data/build/data.csv"
SITE_HOST   = SITE_URL.split("://", 1)[1].rstrip("/")   # shown in the share image and its alt text
# Both belong to this site: a fork sets them to "" (no tag, no key file) or to its own values.
BING_SITE_VERIFICATION = "F362761CB53AA11BE0A561143021D184"   # Bing Webmaster Tools ownership (msvalidate.01); keep it
INDEXNOW_KEY = "b3573dbc1da690e66e9ef05b081b7abe"   # public by design: served as /<key>.txt, proves ownership to IndexNow (Bing…)

# The configurations of a model, in the order the page lists them: thinking off, then the levels from the lowest up,
# then 'think' (the one "on" position of an on/off model, which has no level) and 'solo' (no setting at all). The model
# puts no order between them; the page uses this one to read a model's ladder (docs/DISPLAY-METHODOLOGY.md § 3).
EFFORT_ORDER = ["nothink", "minimal", "low", "medium", "high", "xhigh", "max", "think", "solo"]
LEVELS = ["minimal", "low", "medium", "high", "xhigh", "max"]       # the rungs of a ladder; 'nothink' is the rung below
# How a configuration is written: CAP as a label (a column head, a tooltip), EFF inside a sentence. '' = no setting.
CAP = {"nothink": "Thinking off", "minimal": "Minimal", "low": "Low", "medium": "Medium", "high": "High",
       "xhigh": "xHigh", "max": "Max", "think": "Thinking on", "solo": ""}
EFF = {"nothink": "thinking off", "minimal": "minimal", "low": "low", "medium": "medium", "high": "high",
       "xhigh": "xHigh", "max": "max", "think": "thinking on", "solo": "its only setting"}
