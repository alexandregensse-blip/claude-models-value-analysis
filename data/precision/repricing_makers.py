#!/usr/bin/env python3
"""Today's prices for the other makers' costs (OpenAI, Google, xAI, DeepSeek, Qwen, GLM, Kimi), 21 Oct 2026.

The fit compares costs at the prices in force now (docs/METHODOLOGY.md §2, "Today's prices"). The user's decisions
of 21 Oct 2026:
  1. the base price is the standard list price in force today, without a temporary promotion, and DeepSeek's peak
     rate (a retired model: its last list price); every cost of the fit is put on that base;
  2. a promotion in force today (and DeepSeek's off-peak rate) is shown on the site as a second point of the couple
     (price_variants.json, written here); the fit does not change for it;
  3. a cost that cannot be put on today's price — only dollars, and no date that tells which price applied, or no
     token counts when the change is not uniform — loses its cost (set aside with a flag, score kept).

For every row of another maker with a cost in the fit, the script finds the price its cost was computed with:
  - the source's own statement of it: Artificial Analysis' payload prices of the capture (it recomputes every cost at
    the price it displays), a price quoted in the row's confound field, or the price that reproduces the cost from
    the row's own token counts;
  - else the price in force over the row's price-basis interval: the date the source computed the cost (a board that
    recomputes at the current price: its reading date) or the run date (a measured spend), bounded below by the
    model's release and above by the source's capture / publication date (confound tags, ARC's first Wayback capture,
    the arXiv month). A period whose price the maker's archives do not show is a doubt: it never changes a cost by
    itself, and an interval that mixes it with a different known price is set aside.
Then, if that price differs from today's base: the publisher's own figure at the new price where it exists; else a
uniform change (every token class by one factor) is applied as that factor; else the token counts re-price the cost
(the class split of AA's index cost, the row's input/output/cache counts that reproduce the old cost, or — when every
non-output class moves by one factor, GPT-5.6 Sol's promotion — the output tokens alone); else decision 3.

Flags (confound): reprice-<change date>:<change>(<method>):was=<old cost> | cost-out:<reason>:was=<old cost>.
Re-runnable: rows carrying these flags are restored from was= before the run (edit repricing_makers.json when a
price changes, then run again). Claude rows are not touched. Run from the repository root:
    python3 data/precision/repricing_makers.py            # rewrites raw-data.csv, the 'rows' of the JSON and
                                                          # the price variants file
    python3 data/precision/repricing_makers.py --check    # reports, writes nothing
then python3 data/precision.py (cost_prec of the changed rows).
"""
import collections, csv, datetime, io, json, math, os, re, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, "raw-data.csv")
SPEC = os.path.join(HERE, "repricing_makers.json")
MODELS = os.path.join(ROOT, "data", "catalog", "models.json")
VARIANTS = os.path.join(HERE, "price_variants.json")             # for the site; also copied to $PRICE_VARIANTS
EXTRA = os.environ.get("PRICE_VARIANTS", "/work/.salvo14/px/apply/price_variants.json")
TODAY = "2026-10-21"
EFFORTS = {"low", "medium", "high", "xhigh", "max", "solo"}
CLAUDE = re.compile(r"^(opus|sonnet|haiku|fable|claude)")
MINE = re.compile(r";?(?:reprice-\d{4}-\d{2}-\d{2}:[^;]*?:was=([0-9.eE+-]+)|cost-out:[^;]*?:was=([0-9.eE+-]+))")
TOL = 0.01                                                    # two prices are equal within 1 % (AA rounds 0.003625)
D = r"(20\d\d-\d\d-\d\d)"


def day(s):
    return datetime.date.fromisoformat(s)


def fnum(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def sig(text):
    t = text.strip().lower().split("e")[0].replace("-", "").replace(".", "").lstrip("0")
    return max(len(t), 1)


def fmt(v, like):
    """v with the significant digits of the original text (same relative reading precision)."""
    n = sig(like)
    s = f"{v:.{n}g}"
    if "e" in s:
        s = f"{v:.{max(n - 1 - int(math.floor(math.log10(abs(v)))), 0)}f}"
    return s


# ---------------------------------------------------------------- prices
class Book:
    def __init__(self, spec):
        self.p = spec["prices"]
        self.alias = spec["alias"]

    def key(self, model):
        k = self.alias.get(model, model)
        return k if k in self.p else None

    @staticmethod
    def full(pr):
        """[in, out, cache_read, cache_write]; a cache write the maker does not bill is priced as input (AA bills
        Gemini's cache writes at the input price, which keeps the factor right)."""
        a, b, c, w = (list(pr) + [None, None])[:4]
        return [a, b, c, w if w is not None or c is None else a]

    def periods(self, k, lo, hi):
        """Periods of key k overlapping [lo, hi] (dates)."""
        out = []
        for f, t, kind, pr, src in self.p[k]["periods"]:
            f, t = day(f), day(t) if t else day(TODAY)
            if f <= hi and t >= lo:
                out.append((kind, pr, src, f, t))
        first = day(self.p[k]["periods"][0][0])
        if lo < first:                                           # before the first archived price: unknown
            out.insert(0, ("unknown", None, "before the first archived price", lo, first))
        return out

    def equal(self, a, b, classes=4):
        for x, y in list(zip(self.full(a), self.full(b)))[:classes]:
            if x is None or y is None:                           # a class one side does not price (Qwen's cache)
                continue
            if abs(x - y) > TOL * max(abs(x), abs(y)):
                return False
        return True

    def factors(self, k, old):
        base = self.full(self.p[k]["base"])
        old = self.full(old)
        return [None if (o is None or b is None or o == 0) else b / o for o, b in zip(old, base)]


def uniform(fs):
    v = [f for f in fs if f is not None]
    return v[0] if v and all(abs(f - v[0]) <= TOL * v[0] for f in v) else None


# ---------------------------------------------------------------- price-basis interval from the row's own tags
MON = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}


def interval(r, release):
    """(lo, hi, how) of the price-basis date, or None when nothing bounds it above."""
    t = (r["confound"] or "") + " | " + (r["ref"] or "")
    m = re.search(r"price[-_]date[:=]\s*(?:file-)?(20\d\d)-?(\d\d)-?(\d\d)", t)
    if m:
        d = day(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
        return d, d, "price-date"
    m = re.search(r"price-date:(20\d\d)-(\d\d)(?![-\d])", t)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        end = (datetime.date(y + (mo == 12), mo % 12 + 1, 1) - datetime.timedelta(days=1))
        return datetime.date(y, mo, 1), end, "price-date(month)"
    if "current price" in t:                                     # a board recomputing at the reading date
        m = re.search(r"board-read-" + D, t) or re.search(r"read " + D, t)
        if m:
            d = day(m.group(1))
            return d, d, "current-price-board-read"
    m = re.search(r"run-dates?[:=]" + D + r"\.\." + D, t)
    if m:
        return day(m.group(1)), day(m.group(2)), "run-dates"
    m = re.search(r"(?:run-date[:=]|run=|eval-date=|measured-on:|date-tested:|run-dates=)" + D, t)
    if m:
        d = day(m.group(1))
        return d, d, "run-date"
    ubs = [day(x) for x in re.findall(r"(?:run-date:<=|run-<=|run-date<=|run-before-|last-run=|board-read-|"
                                      r"board-updated-|read |saved |fetched |capture[: ]|snapshot-)" + D, t)]
    for dd, mm, yy in re.findall(r"(?:fetched|read|saved) (\d{1,2}) ([A-Z][a-z]{2})[a-z]* (20\d\d)", t):
        if mm.lower() in MON:
            ubs.append(datetime.date(int(yy), MON[mm.lower()], int(dd)))
    ax = re.findall(r"(?<![\d.])(2[56])(\d\d)\.\d{4,5}", (r["source"] or "") + " " + (r["ref"] or "") + " " + r["group"])
    for yy, mm in ax:
        y, mo = 2000 + int(yy), int(mm)
        if 1 <= mo <= 12:
            ubs.append(datetime.date(y + (mo == 12), mo % 12 + 1, 1) - datetime.timedelta(days=1))
    for x in re.findall(r"from-timeline;run-date:<=" + D, t):  # a build-dating tag that only repeats the release
        if day(x) == release and day(x) in ubs:                 # date is not a run date
            ubs.remove(day(x))
    ubs = [u for u in ubs if u >= release]
    if ubs:
        return release, min(ubs), "upper-bound"
    return None


def stated_price(r):
    """A price the source states it used, quoted in the confound field: 'list-prices-0.75/3.75-per-MTok',
    '$0.75/$3.75 per M', 'at $2/$12'."""
    t = r["confound"] or ""
    m = re.search(r"list-prices-([0-9.]+)/([0-9.]+)-per-MTok", t) or re.search(r"price/MTok=([0-9.]+)/([0-9.]+)", t) or \
        re.search(r"\$([0-9.]+)\s*/\s*\$([0-9.]+)\s*(?:per|/)\s*(?:1?M|million)", t)
    if m:
        return [float(m.group(1)), float(m.group(2)), None, None]
    return None


# ---------------------------------------------------------------- source evidence
class Sources:
    """Per-source evidence: what each source computed its cost with (repricing_makers.json 'aa', 'sources')."""

    def __init__(self, spec, rows):
        self.aa = spec.get("aa", {})
        self.src = spec.get("sources", {})
        self.oai = collections.defaultdict(list)                 # OpenAI's 9 Jul figures, by (chart, couple)
        for r in rows:
            if r.get("source") == "openai-gpt56-launch":
                self.oai[(self.bench(r["group"]), r["model"], r["effort"], r["unit"])].append(r)

    @staticmethod
    def bench(group):
        g = re.sub(r"^oai(56|-as|-sl)-", "", group)
        return re.sub(r"-(noncode|codefalse|codetrue|code)$", "", g)

    def same_run(self, r):
        """The 9 Jul row of the same run (same chart, couple, unit and score), or None."""
        for x in self.oai.get((self.bench(r["group"]), r["model"], r["effort"], r["unit"]), []):
            a, b = fnum(x["score"]), fnum(r["score"])
            if a is not None and b is not None and abs(a - b) <= 0.01 + 0.0005 * abs(a):
                return x
        return None

    AA_NAME = {"gpt-5.6-sol": "gpt-5.6 sol", "gpt-5.6-terra": "gpt-5.6 terra", "gpt-5.6-luna": "gpt-5.6 luna",
               "gemini-3.6-flash": "gemini 3.6 flash", "gemini-3.7-flash": "gemini 3.7 flash",
               "gemini-3.8-flash": "gemini 3.8 flash", "gemini-4-argon": "gemini 4 argon", "glm-5.3-flash": "glm-5.3-flash",
               "grok-4.5": "grok 4.5", "deepseek-v4-flash-0731": "deepseek v4 flash 0731",
               "deepseek-v4-pro-0813": "deepseek v4 pro 0813", "deepseek-v4-flash-preview": "deepseek v4 flash 0420",
               "deepseek-v4-pro-preview": "deepseek v4 pro 0424", "qwen3.7-max": "qwen3.7 max", "qwen3.7-plus": "qwen3.7 plus"}

    def aa_object(self, r, capture):
        """The AA model object a row was read from: by the name quoted in the row, else (agents, articles) by the
        model's AA name in that capture — the price is the model's, whatever the effort."""
        cap = self.aa.get(capture, {})
        m = re.search(r'name="([^"]+)"', r["confound"] or "")
        if m:
            return cap.get(m.group(1).replace(";", ",").lower())
        pre = self.AA_NAME.get(r["model"])
        if pre:
            for n, o in sorted(cap.items()):
                if not n.startswith("_") and n.startswith(pre):
                    return dict(o, suite=None, task=None, evals={})
        return None

    def rule(self, r, k):
        """A source-level decision: None (generic path) or a dict with 'price' / 'interval' / 'out' / 'new'."""
        s, g = r["source"], r["group"]
        spec = self.src.get(s, {})
        # group or (group, model) overrides written from the evidence in repricing_makers.json 'sources'
        for sel in (f"{g}|{r['model']}", f"*|{r['model']}", g, "*"):
            if sel in spec:
                return dict(spec[sel])
        return None


# ---------------------------------------------------------------- the decision for one row
class Decider:
    def __init__(self, book, sources, release):
        self.b, self.s, self.release = book, sources, release

    def tokens_split(self, r, k, cands):
        """The candidate price that reproduces the cost from the row's own token counts (input, output, cached
        share), within the rounding of the printed cost: (price, split) or None."""
        ti, to, c = fnum(r["tokens_in"]), fnum(r["tokens_out"]), fnum(r["cost_usd"])
        if not (ti and to and c):
            return None
        q = fnum(r["cached_pct"])
        q = q / 100 if q is not None and q > 1 else q
        step = 10.0 ** -(len(r["cost_usd"].split(".")[1]) if "." in r["cost_usd"] else 0)
        tol = max(0.5 * step, 0.002 * c)
        hits = []
        for pr in cands:
            a, o, cr, w = Book.full(pr)
            if a is None or o is None:
                continue
            for qq in ([q] if q is not None else [0.0]):
                if qq and cr is None:
                    continue
                v = (ti * ((1 - qq) * a + qq * (cr or 0)) + to * o) / 1e6
                if abs(v - c) <= tol:
                    hits.append((pr, dict(nc=ti * (1 - qq), cr=ti * qq, out=to)))
        uniq = []
        for h in hits:
            if not any(self.b.equal(h[0], u[0]) for u in uniq):
                uniq.append(h)
        if len(uniq) > 1 and all(h[1]["cr"] == 0 for h in uniq) and \
                all(self.b.equal(h[0], uniq[0][0], classes=2) for h in uniq):
            return uniq[0]                                       # no cache read: prices that differ only there agree
        return uniq[0] if len(uniq) == 1 else None

    def reprice(self, r, k, old, split=None, breakdown=None, out_tokens=None):
        """New cost from the price `old` to today's base, or (None, reason)."""
        c = fnum(r["cost_usd"])
        fs = self.b.factors(k, old)
        u = uniform([f for f, p in zip(fs, Book.full(old)) if p is not None])
        if u is not None:
            return c * u, f"uniform x{u:.4g}"
        base = Book.full(self.b.p[k]["base"])
        oldf = Book.full(old)
        if breakdown:                                            # AA's class split of this very cost
            tot = sum(breakdown.get(x) or 0 for x in ("nonCacheInput", "cacheRead", "cacheWrite", "output"))
            if tot and abs(tot - c) <= 0.002 * c + 1e-9:
                f = dict(nonCacheInput=fs[0], cacheRead=fs[2], cacheWrite=fs[3], output=fs[1])
                if any(f[x] is None and (breakdown.get(x) or 0) > 0 for x in f):
                    return None, "class-split-but-no-price-for-a-class"
                new = sum((breakdown.get(x) or 0) * (f[x] or 0) for x in f)
                return new, "AA-class-split"
        if split:                                                # the row's token counts reproduce the cost
            v_old = (split["nc"] * oldf[0] + split["cr"] * (oldf[2] or 0) + split["out"] * oldf[1]) / 1e6
            v_new = (split["nc"] * base[0] + split["cr"] * (base[2] or 0) + split["out"] * base[1]) / 1e6
            return c * v_new / v_old, "tokens(reproduced)"
        nono = [f for f, p in zip((fs[0], fs[2], fs[3]), (oldf[0], oldf[2], oldf[3])) if p is not None]
        fin = uniform(nono)
        to = out_tokens if out_tokens is not None else fnum(r["tokens_out"])
        if fin is not None and to:                               # every non-output class by one factor
            oc = oldf[1] * to / 1e6
            if oc <= c * 1.002:
                return c * fin + oc * (fs[1] - fin), "tokens(output-share)"
            return None, "output-tokens-exceed-cost"
        return None, "nonuniform-change-no-token-split"

    def decide(self, r):
        model = r["model"]
        k = self.b.key(model)
        if not k:
            return None
        spec = self.b.p[k]
        rel = day(spec["periods"][0][0])
        rule = self.s.rule(r, k) or {}
        if rule.get("out"):
            return ("out", rule["out"], rule.get("evidence", ""))
        if rule.get("unchanged"):
            return ("same", rule["unchanged"], rule.get("evidence", ""))
        ev = rule.get("evidence", "")
        cands = [p[3] for p in spec["periods"] if p[3]] + [spec["base"]]
        if rule.get("astra"):                                    # OpenAI's 3 Sep post: mixed pricing, see JSON
            x = self.s.same_run(r)
            if k in ("gpt-5.6-sol",) and x:
                c, c0 = fnum(r["cost_usd"]), fnum(x["cost_usd"])
                if abs(c - c0) <= 0.002 * c0:
                    return ("same", "same-run-as-9-Jul-at-regular-price", ev)
                promo = [p[3] for p in spec["periods"] if p[2] == "promo"][0]
                new, meth = self.reprice(r, k, promo)
                if new is not None and abs(new - c0) <= 0.005 * c0:
                    return ("new", c0, "publisher-figure(9-Jul-same-run)", "same run priced at the promotion", ev)
            return ("out", "price-basis-unknown(post-mixes-regular-and-promotional-pricing)", ev)
        # 1. the price the source states / used
        price, how, split, breakdown, out_tok = None, None, None, None, None
        if rule.get("aa"):
            obj = self.s.aa_object(r, rule["aa"])
            if obj:
                price = obj["price"]
                if price[3] is None:
                    price = price[:3] + [price[0]]
                how = f"AA payload {rule['aa']}"
                ev = ev or f"AA capture {rule['aa']} ({obj['slug']}): {'/'.join(str(x) for x in obj['price'])}"
                c = fnum(r["cost_usd"])
                for part in ("suite", "task"):
                    bd = obj.get(part)
                    if bd and bd.get("total") and abs(bd["total"] - c) <= 0.002 * c:
                        breakdown = bd
                for es, (ec, eo) in obj.get("evals", {}).items():
                    if ec and abs(ec - c) <= 0.002 * c:
                        out_tok = eo
            else:
                rule.setdefault("price_date", rule["aa"])
        if price is None and rule.get("price"):
            price, how = rule["price"], "stated by the source"
        if price is None:
            sp = stated_price(r)
            if sp:
                for pr in cands:
                    a = Book.full(pr)
                    if abs(a[0] - sp[0]) <= TOL * a[0] and abs(a[1] - sp[1]) <= TOL * a[1]:
                        price, how = pr, f"stated {sp[0]:g}/{sp[1]:g}"
                        break
        if price is None:
            hit = self.tokens_split(r, k, cands)
            if hit:
                price, split = hit
                how = "reproduced from the row's tokens"
        if price is None:
            if rule.get("price_date"):
                lo = hi = day(rule["price_date"])
                how = rule.get("how", "price date (source)")
            elif rule.get("interval"):
                lo, hi = day(rule["interval"][0]), day(rule["interval"][1])
                how = rule.get("how", "interval (source)")
            elif rule.get("slug_run_date") and re.search(r"slug=[^;]*-(20\d\d)(\d\d)(\d\d)(?:;|$)", r["confound"] or ""):
                m = re.search(r"slug=[^;]*-(20\d\d)(\d\d)(\d\d)(?:;|$)", r["confound"])
                lo = hi = day(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
                how = "run date in the run slug"
            else:
                iv = interval(r, rel)
                if not iv:
                    lo, hi, how = rel, day(TODAY), "no-date"
                else:
                    lo, hi, how = iv
            lo = max(lo, rel) if hi >= rel else lo
            per = self.b.periods(k, lo, hi)
            if rule.get("no_promo"):                             # a source that never applies a promotion
                per = [p for p in per if p[0] != "promo"] or [("unknown", None, "promotion only", lo, hi)]
            known = [p for p in per if p[0] != "unknown"]
            unknown = [p for p in per if p[0] == "unknown"]
            if not known:
                return ("same", f"price-at-basis-unarchived({how} {lo}..{hi})", ev)
            diff = [p for p in known if not self.b.equal(p[1], spec["base"])]
            if not diff:
                return ("same", f"base-price-in-force({how} {lo}..{hi})", ev)
            prs = []
            for p in known:
                if not any(self.b.equal(p[1], q) for q in prs):
                    prs.append(p[1])
            if len(prs) > 1 or unknown:
                why = "price-date-unknown" if how == "no-date" else "price-basis-straddles-a-change"
                return ("out", f"{why}({how} {lo}..{hi})", ev)
            price = prs[0]
            how = f"{how} {lo}..{hi}"
            hit = self.tokens_split(r, k, [price])
            if hit:
                split = hit[1]
        if self.b.equal(price, spec["base"]) or (split and split["cr"] == 0 and
                                                 self.b.equal(price, spec["base"], classes=2)):
            return ("same", f"at-base({how}{'; no cache read' if split and split['cr'] == 0 else ''})", ev)
        if rule.get("new") is not None:                          # the publisher's own figure at the new price
            return ("new", fnum(rule["new"]), "publisher-figure", how, ev)
        new, meth = self.reprice(r, k, price, split, breakdown, out_tok)
        if new is None:
            return ("out", f"{meth}({how})", ev)
        return ("new", new, meth, how, ev)


# ---------------------------------------------------------------- main
def main(check=False):
    spec = json.load(open(SPEC))
    models = json.load(open(MODELS))["models"]
    text = open(DATA).read()
    reader = csv.DictReader(io.StringIO(text))
    head, rows = list(reader.fieldnames), list(reader)
    notes = {i: line for i, line in enumerate(text.split("\n")[1:]) if line.startswith("#") and "," not in line}
    # restore the rows of an earlier run
    for r in rows:
        if r.get("confound") and MINE.search(r["confound"]):
            m = MINE.search(r["confound"])
            r["cost_usd"] = m.group(1) or m.group(2)
            r["confound"] = MINE.sub("", r["confound"]).lstrip(";")
    book = Book(spec)
    dec = Decider(book, Sources(spec, rows), None)
    out_rows, stats = [], collections.Counter()
    by_src = collections.defaultdict(collections.Counter)
    for r in rows:
        if not r.get("group") or r["group"].startswith("#") or r["effort"] not in EFFORTS or r["model"] not in models:
            continue
        if CLAUDE.match(r["model"]) or fnum(r["cost_usd"]) is None:
            continue
        d = dec.decide(r)
        if d is None:
            continue
        k = book.key(r["model"])
        old = r["cost_usd"]
        d = tuple(x.replace(";", ",") if isinstance(x, str) else x for x in d)   # ';' separates the flags
        rec = dict(row=[r[x] for x in ("group", "model", "effort", "source", "harness", "unit", "ref")], key=k, was=old)
        if d[0] == "same":
            stats["unchanged"] += 1
            by_src[r["source"]]["unchanged"] += 1
            rec.update(decision="unchanged", why=d[1], evidence=d[2])
        elif d[0] == "out":
            stats["cost-out"] += 1
            by_src[r["source"]]["cost-out"] += 1
            r["confound"] = ((r["confound"] + ";") if r["confound"] else "") + f"cost-out:{d[1]}:was={old}"
            r["cost_usd"], r["cost_prec"] = "", ""
            rec.update(decision="cost-out", why=d[1], evidence=d[2])
        else:
            _, new, meth, how, ev = d
            ratio = new / fnum(old)
            ch = spec["prices"][k]["change"]
            r["cost_usd"] = fmt(new, old)
            dt = change_day(spec, k, how)
            r["confound"] = ((r["confound"] + ";") if r["confound"] else "") + f"reprice-{dt}:{ch}({meth}):was={old}"
            stats["re-priced"] += 1
            by_src[r["source"]]["re-priced"] += 1
            rec.update(decision="re-priced", new=r["cost_usd"], ratio=round(ratio, 5), method=meth, basis=how,
                       evidence=ev)
        if len(rec.get("evidence") or "") > 120:                 # the source's evidence is kept once, in 'sources'
            rec["evidence"] = f"sources[{r['source']!r}]" if r["source"] in spec.get("sources", {}) else rec["evidence"]
        out_rows.append(rec)
    print(json.dumps(dict(stats)))
    if check:
        return out_rows
    spec["rows"] = []
    text = json.dumps(spec, indent=1, ensure_ascii=False)        # one line per row record
    rows_text = ",\n  ".join(json.dumps(x, ensure_ascii=False) for x in out_rows)
    open(SPEC, "w").write(text.replace('"rows": []', '"rows": [\n  ' + rows_text + "\n ]") + "\n")
    with open(DATA, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=head, lineterminator="\n")
        w.writeheader()
        for i, r in enumerate(rows):
            if i in notes:
                f.write(notes[i] + "\n")
            else:
                w.writerow(r)
    variants(spec, rows, models)
    return out_rows


def change_day(spec, k, how):
    """The date of the change applied: the first day of the base price after the period the cost was priced in
    (a cut), or the first day of the promotion removed."""
    per = spec["prices"][k]["periods"]
    base = Book.full(spec["prices"][k]["base"])
    promo = [p for p in per if p[2] == "promo"]
    if promo:
        return promo[0][0]
    for p in per:
        if p[3] and Book.full(p[3]) == base:
            return p[0]
    return per[-1][0]


# ---------------------------------------------------------------- price variants for the site
def variants(spec, rows, models):
    """{couple: [{kind, label, cost_ratio, until, evidence}]} for every couple in the fit of a model whose promotion
    is in force today (the ratio = variant cost / base cost) and for DeepSeek's off-peak rate."""
    book = Book(spec)
    out, notes = {}, {}
    today = day(TODAY)
    by_couple = collections.defaultdict(list)
    for r in rows:
        if not r.get("group") or r["group"].startswith("#") or r["effort"] not in EFFORTS or r["model"] not in models:
            continue
        if CLAUDE.match(r["model"]):
            continue
        k = book.key(r["model"])
        if k and fnum(r["cost_usd"]):
            by_couple[(r["model"], r["effort"], k)].append(r)
    for (model, effort, k), rs in sorted(by_couple.items()):
        p = spec["prices"][k]
        items = []
        promo = [x for x in p["periods"] if not p.get("no_variant") and x[2] == "promo" and day(x[0]) <= today and
                 (x[1] is None or day(x[1]) >= today)]
        if promo:
            f, t, _, pr, src = promo[-1]
            until = p.get("promo_until", t)
            fs = book.factors(k, pr)                              # base / promo per class
            u = uniform([x for x, q in zip(fs, Book.full(pr)) if q is not None])
            url = "https://" + src.split(" ")[0] if not src.startswith("http") else src.split(" ")[0]
            if u is not None:
                ratio, how = 1 / u, "uniform"
            else:                                                 # non-uniform: the couple's median token mix
                base = Book.full(p["base"])
                shares = []
                for r in rs:
                    c, to = fnum(r["cost_usd"]), fnum(r["tokens_out"])
                    if c and to:
                        s = base[1] * to / 1e6 / c                # output share of the cost at the base price
                        if 0 < s <= 1:
                            shares.append(s)
                if not shares:
                    continue
                s = statistics.median(shares)
                pf = Book.full(pr)
                ratio = (1 - s) * (pf[0] / base[0]) + s * (pf[1] / base[1])
                how = f"median output share {s:.3f} of {len(shares)} rows with tokens"
            lab = f"promo until {day(until).strftime('%-d %b %Y')}" if until else "promo (no end date)"
            items.append(dict(kind="promo", label=lab, cost_ratio=round(ratio, 4), until=until, evidence=url))
            notes[f"{model}@{effort}"] = how
        if p.get("offpeak"):
            items.append(dict(kind="offpeak", label="off-peak rate (half price outside peak hours)",
                              cost_ratio=p["offpeak"], until=None,
                              evidence="https://api-docs.deepseek.com/quick_start/pricing"))
        if items:
            out[f"{model}@{effort}"] = items
    json.dump(out, open(VARIANTS, "w"), indent=1)
    if EXTRA and os.path.isdir(os.path.dirname(EXTRA)):
        json.dump(out, open(EXTRA, "w"), indent=1)
    json.dump(notes, open(os.path.join(HERE, "price_variants_notes.json"), "w"), indent=1)
    print(f"variants: {len(out)} couples -> {VARIANTS}")


if __name__ == "__main__":
    main(check="--check" in sys.argv[1:])
