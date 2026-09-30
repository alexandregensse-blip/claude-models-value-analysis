"""Site settings: where it is published, its titles and ownership keys."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT  = os.path.join(ROOT, "index.html")   # the served files are generated at the repository root

# Publication: every absolute URL derives from SITE_URL (canonical root, trailing slash).
SITE_URL    = "https://claude-models.agensse.com/"
REPO_URL    = "https://github.com/alexandregensse-blip/claude-models-value-analysis"
TITLE       = "Claude cost vs quality: Fable, Opus, Sonnet, Haiku compared"
SITE_NAME   = "Claude cost vs quality"   # site name suggested to Google (JSON-LD WebSite) instead of the bare domain
DESCRIPTION = ("What each Claude model (Fable, Opus, Sonnet, Haiku) costs at every effort level, and which gives "
               "the best quality for the price. Open data, CC BY 4.0.")
SITE_HOST   = SITE_URL.split("://", 1)[1].rstrip("/")   # shown in the share image and its alt text
# Both belong to this site: a fork sets them to "" (no tag, no key file) or to its own values.
BING_SITE_VERIFICATION = "F362761CB53AA11BE0A561143021D184"   # Bing Webmaster Tools ownership (msvalidate.01); keep it
INDEXNOW_KEY = "b3573dbc1da690e66e9ef05b081b7abe"   # public by design: served as /<key>.txt, proves ownership to IndexNow (Bing…)

EFFORT_ORDER = ["low", "medium", "high", "xhigh", "max", "solo"]
