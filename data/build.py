#!/usr/bin/env python3
"""Build of the findings pipeline: the decision tree of docs/DATA-PIPELINE.md §5 over the files of §2–4, and the fit
tables of §6. Python 3 standard library only. Run from anywhere:

    python3 data/build.py --fit-models catalog              # data/registry + data/findings + data/decisions.json → data/build/
    python3 data/build.py --registry data/findings/examples/registry --findings data/findings/examples --out build/
    python3 data/build.py --previous build/status-report.json ...      # adds the status diff to that report
    python3 data/build.py --cost-method-unstated out ...               # the setting (see data/BUILD.md)
    python3 data/build.py --no-lqm ...                                 # skips the lqm.load step (data/build_lqm.py)

Steps: 1. validate (data/schema/validate.py: schemas + cross-file checks; errors in registries, vocab or decisions stop
the build, errors attributable to a source, fact or measure put the measures concerned out:no-proof); 2. fields of
every measure (run-date interval, model through `names`, configuration through §5.1's steps and the route chain,
campaign, value on the setup's scale, cost at the base price); 3. status per axis (decisions first, then the first
failing step); 4. outputs (data/build/ by default): fit-quality.csv, fit-cost.csv, group-map.json, group-setups.json,
data.csv, status-report.json (the last one not committed: .gitignore); 5. unless --no-lqm, data/build_lqm.py recovers lqm.load's per-row outcome."""
import argparse, collections, csv, datetime as dt, glob, hashlib, json, math, os, re, sys
from decimal import Decimal, InvalidOperation

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "schema"))
import validate as V  # noqa: E402
sys.path.insert(0, HERE)

SETTINGS = {"cost_method_unstated": ("single-per-table", "out")}       # first value = default
LEVELS = ("minimal", "low", "medium", "high", "xhigh", "max")
ACCEPTED = ("written", "read", "computed")
NOT_ESTABLISHED = {"budget-converted", "enabled", "adaptive", "default", "unstated", "priceblend", "ambiguous", "auto",
                   "dynamic"}
FIT_COLUMNS = ["group", "source", "model", "effort", "task_type", "complexity", "harness", "unit", "cost_usd",
               "cost_prec", "tokens_in", "tokens_out", "score", "score_metric", "score_prec", "cached_pct", "confound",
               "ref"]
DATA_COLUMNS = FIT_COLUMNS + ["status_quality", "status_cost"]
MIN, MAX = dt.datetime.min, dt.datetime.max
S12 = math.sqrt(12)
TOKEN_CLASS = {"tokens-in": "input", "tokens-out": "output", "tokens-cache-read": "cache-read",
               "tokens-cache-write-5m": "cache-write-5m", "tokens-cache-write-1h": "cache-write-1h"}
MONTHS = {m: i for i, ms in enumerate((("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"),
                                       ("may",), ("june", "jun"), ("july", "jul"), ("august", "aug"),
                                       ("september", "sep", "sept"), ("october", "oct"), ("november", "nov"),
                                       ("december", "dec")), 1) for m in ms}
LEVEL_ALIASES = {"x-high": "xhigh", "x high": "xhigh", "extra-high": "xhigh", "extra high": "xhigh"}
LABEL_FILLER = {"effort", "level", "setting", "reasoning", "the", "at"}
LEVEL_TOKEN_ALIASES = {"med": "medium"}   # chart legends abbreviate (Anthropic system cards: "Med"; 26 Oct)


class Fatal(Exception):
    pass


class BadInput(Exception):
    """A bad argument or input file: a one-line error, exit 2."""


def read_json_arg(path, what):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError as e:
        raise BadInput(f"{what} {path}: {e.strerror}")
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise BadInput(f"{what} {path}: not JSON ({e})")


def read_class_ratios(path):
    x = read_json_arg(path, "class ratios")
    if not isinstance(x, dict) or not isinstance(x.get("ratios"), list):
        raise BadInput(f"class ratios {path}: expected {{\"ratios\": [...]}}")
    for i, e in enumerate(x["ratios"]):
        ok = isinstance(e, dict) and isinstance(e.get("model"), str) and V.parse_when(e.get("change") or "") \
            and isinstance(e.get("classes"), dict) and all(
                isinstance(c, dict) and isinstance(c.get("factor"), (int, float)) and isinstance(c.get("sd"), (int, float))
                for c in e["classes"].values()) \
            and all(isinstance(e.get(k, {}), dict) for k in ("setups", "measures"))
        if not ok:
            raise BadInput(f"class ratios {path}: ratios[{i}] needs model, change (a date), classes {{cls: {{factor, "
                           f"sd}}}} and optional setups / measures maps")
    return x


# ---------------------------------------------------------------- small helpers
def covers(rec, iv):
    """A dated record {from, to} covers the run interval iv = (lo, hi, ea). lo None = unclamped (early access): only a
    record starting at the release (from_basis release) covers it."""
    lo, hi, ea = iv
    f = MIN if (ea and rec.get("from_basis") == "release") else V.when(rec["from"])
    t = V.when(rec["to"], True) if rec.get("to") is not None else MAX
    return f <= (lo or MIN) and hi <= t


def overlaps(rec, lo, hi):
    f = V.when(rec["from"])
    t = V.when(rec["to"], True) if rec.get("to") is not None else MAX
    return f <= hi and (lo or MIN) <= t


def day_bounds(s):
    """A date / datetime string → (start, end) naive UTC; a date covers its whole day. None when not a date."""
    t = V.parse_when(s) if isinstance(s, str) else None
    if t is None:
        return None
    return (t, t + dt.timedelta(days=1, microseconds=-1)) if len(s) == 10 else (t, t)


def find_date(text):
    """The first date written in a text (ISO, '11 October 2026', 'October 11, 2026') → (start, end), or None."""
    if not text:
        return None
    b = day_bounds(text.strip())
    if b:
        return b
    if re.fullmatch(r"\s*1[6-9]\d{11}(\.0+)?\s*", text):    # epoch milliseconds (a JSON timestamp; convex.dev, 27 Oct)
        t = dt.datetime.utcfromtimestamp(int(float(text)) / 1000)
        return t, t
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})(T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2}))?", text)
    if m:
        return day_bounds(m.group(0)) or day_bounds(m.group(1))
    low = text.casefold()
    m = re.search(r"\b(\d{1,2})\s+([a-z]+)\.?,?\s+(\d{4})\b", low)
    if m and m.group(2) in MONTHS:
        return _ymd(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
    m = re.search(r"\b([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", low)
    if m and m.group(1) in MONTHS:
        return _ymd(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2)))
    m = re.fullmatch(r"\s*(?:([a-z]+)\.?\s+(\d{4})|(\d{4})-(\d{2}))\s*", low)   # a month only ('April 2026',
    if m:                                                # '2026-04'): its first to its last day (28 Oct)
        y, mo = (int(m.group(2)), MONTHS.get(m.group(1))) if m.group(1) else (int(m.group(3)), int(m.group(4)))
        if mo and 1 <= mo <= 12:
            first = dt.datetime(y, mo, 1)
            nxt = dt.datetime(y + (mo == 12), mo % 12 + 1, 1)
            return first, nxt - dt.timedelta(microseconds=1)
    return None


def _ymd(y, mo, d):
    try:
        t = dt.datetime(y, mo, d)
    except ValueError:
        return None
    return t, t + dt.timedelta(days=1, microseconds=-1)


def all_dates(text):
    out = []
    for m in re.finditer(r"\b\d{4}-\d{2}-\d{2}\b", text or ""):
        b = day_bounds(m.group(0))
        if b:
            out.append(b)
    return out


def parse_number(text):
    """A number as the source writes it ('90.2%', '$30.31', '7.25M', '3,000', '0.958333') → (Decimal, step) where step =
    one unit of its last written digit, or None."""
    if text is None:
        return None
    t = str(text).strip()
    t = re.sub(r"^(US\$|USD|CNY|RMB|JPY|\$|¥|€|£|￥)\s*", "", t)
    t = re.sub(r"\s*(USD|CNY|RMB|JPY|yuan|yen|円|元)$", "", t)
    cents = re.search(r"\s*(¢|cents?)$", t)                       # '51¢', '10.017 cents' (US cents, 28 Oct): /100
    if cents:
        t = t[:cents.start()]
    t = t.replace(",", "").replace(" ", "").replace(" ", "").replace(" ", "")
    if t.endswith("%"):
        t = t[:-1]
    m = re.fullmatch(r"([+-]?\d+(?:\.(\d+))?|[+-]?\.(\d+))(?:[eE]([+-]?\d+))?(k|K|M|B|bn)?", t)
    if not m:
        return None
    try:
        d = Decimal(m.group(1))
    except InvalidOperation:
        return None
    decs = len(m.group(2) or m.group(3) or "")
    exp = int(m.group(4) or 0)
    mult = {"k": 3, "K": 3, "M": 6, "B": 9, "bn": 9}.get(m.group(5), 0)
    if cents:
        mult -= 2
    return d.scaleb(exp + mult), Decimal(1).scaleb(exp + mult - decs)


def num_text(d):
    """A Decimal written without exponent and without trailing float noise."""
    s = format(d, "f")
    return s


def fmt_prec(x):
    """A precision column as today (data/precision.py): three significant digits."""
    return "" if x is None else f"{x:.3g}"


def sig_digits(text):
    t = text.strip().lower().split("e")[0].replace("-", "").replace(".", "").lstrip("0")
    return max(len(t), 1)


def fmt_like(v, like):
    """v with the significant digits of the original text (data/precision/repricing_makers.py's rule)."""
    n = sig_digits(like)
    s = f"{v:.{n}g}"
    if "e" in s:
        s = f"{v:.{max(n - 1 - int(math.floor(math.log10(abs(v)))), 0)}f}"
    return s


def norm_version(v):
    v = (v or "").strip().casefold()
    return re.sub(r"^v(?=\d)", "", v)


def kv_value(text):
    """'reasoning_effort: high' / 'effort=high' → 'high' (the value of a key-value setting line), else None."""
    m = re.search(r"[:=]\s*[\"']?([A-Za-z0-9._-]+)[\"']?\s*[,}]?\s*$", text or "")
    return m.group(1) if m else None


# ---------------------------------------------------------------- facts
DECIMAL_COMMA = re.compile(r"[+-]?(?:\d{1,3}(?:[.\s\u00a0\u202f]\d{3})+(?:,\d+)?|\d+,\d+)\s?%?")


class Fact(dict):
    """A cited fact or cell: ref, says (list), value, level, form, where, quote, term, scale, namespace, precision,
    about, file, column, chart, table."""
    __getattr__ = dict.get


class Source:
    def __init__(self, path, doc, ctx):
        self.path, self.doc, self.ctx = path, doc, ctx
        self.id = doc["id"]
        self.publisher = doc["publisher"]
        self.facts = {f["id"]: f for f in doc.get("facts", [])}
        self.tables = {t["id"]: t for t in doc.get("tables", [])}
        self.charts = {c["id"]: c for c in doc.get("charts", [])}
        self.captures = {c["id"]: c for c in doc.get("captures", [])}
        self.faults = []                                  # source-wide validation errors
        self.fact_faults = collections.defaultdict(list)  # fact id → validation errors
        self._sha_ok = {}

    def date(self):
        """When this snapshot appeared: its publication, else its earliest capture, else its harvest."""
        p = (self.doc.get("published") or {}).get("value")
        if p:
            return V.when(p)
        caps = [V.when(c["captured"]) for c in self.captures.values()]
        return min(caps) if caps else V.when(self.doc["harvested_at"])

    def derive(self, x, seen):
        """A computed fact (a derived cell, e.g. input − cache read): recomputed from its inputs by its rule; the stated
        value must agree within one unit of the last digits. Its level is computed when every input is accepted."""
        if x.ref in seen:
            return f"computed fact {x.ref}: its inputs cycle"
        if x.rule == "chart-effort-order":            # 'k/n' and the statement that the points are effort levels
            m = re.fullmatch(r"\s*([0-9]+)\s*/\s*([0-9]+)\s*", x.value or "")
            if not m or not (1 <= int(m.group(1)) <= int(m.group(2))) or len(x.inputs or []) != 1:
                return f"computed fact {x.ref}: chart-effort-order needs 'k/n' and one statement fact"
            f, fault = self.fact(x.inputs[0], seen | {x.ref})
            if fault or f is None:
                return f"computed fact {x.ref}: input {x.inputs[0]}: {fault or 'missing'}"
            if f.level not in ACCEPTED:
                x["level"] = f.level
                return None
            if not re.search(r"effort", " ".join(str(f.get(k) or "") for k in ("quote", "value")), re.I):
                return f"computed fact {x.ref}: its statement {x.inputs[0]} does not say the points are effort levels"
            return None
        if x.rule == "complement-of-percent":         # 100 − a printed rate (the setup holds its complement)
            if len(x.inputs or []) != 1:
                return f"computed fact {x.ref}: complement-of-percent needs one input"
            f, fault = self.fact(x.inputs[0], seen | {x.ref})
            if fault or f is None:
                return f"computed fact {x.ref}: input {x.inputs[0]}: {fault or 'missing'}"
            if f.level not in ACCEPTED:
                x["level"] = f.level
                return None
            p, st = parse_number(f.value), parse_number(x.value)
            if p is None or st is None:
                return f"computed fact {x.ref}: not a number"
            if (f.get("scale") or "") == "fraction":       # a fraction input in percent first (scale-conversion, exact)
                p = (p[0] * 100, p[1] * 100)
            got = 100 - p[0]
            if abs(float(got - st[0])) > float(p[1]) / 2 + float(st[1]) / 2 + 1e-12:
                return f"computed fact {x.ref}: stated {x.value}, 100 − {f.value} gives {num_text(got)}"
            x["precision"] = {"model": "printed", "sd": precision_sd(f, p[1]) or 0.0}
            x["derived"] = dict(rule=x.rule, inputs=list(x.inputs), value=num_text(got))
            return None
        if x.rule not in ("cell-difference", "cell-sum", "metric-mean") or len(x.inputs or []) < 2:
            return f"computed fact {x.ref}: without its rule and two inputs"
        vals, sds, steps = [], [], []
        for ref in x.inputs or []:
            f, fault = self.fact(ref, seen | {x.ref})
            if fault or f is None:
                return f"computed fact {x.ref}: input {ref}: {fault or 'missing'}"
            if f.level not in ACCEPTED:
                x["level"] = f.level
                return None
            p = parse_number(f.value)
            if p is None:
                return f"computed fact {x.ref}: input {ref} {f.value!r} is not a number"
            vals.append(p[0])
            steps.append(p[1])
            sd = precision_sd(f, p[1])
            sds.append(sd or 0.0)
        n = len(vals) if x.rule == "metric-mean" else 1     # metric-mean: the mean of an entry's same-scale metrics,
        got = vals[0] - sum(vals[1:]) if x.rule == "cell-difference" else sum(vals) / n  # no headline designated (29 Oct)
        stated = parse_number(x.value)
        if stated is None:
            return f"computed fact {x.ref}: {x.value!r} is not a number"
        # agreement within the roundings: half a unit of each rounded number (a plain integer is an exact count)
        exact = lambda t: re.fullmatch(r"[0-9]+", (t or "").strip().rstrip("%")) is not None  # noqa: E731
        texts = [self.fact(r, seen | {x.ref})[0].value for r in x.inputs]
        tol = sum(float(st) / 2 for st, t in zip(steps, texts) if not exact(t)) / n + \
            (0.0 if exact(x.value) else float(stated[1]) / 2)
        if abs(float(got - stated[0])) > tol + 1e-12:
            return f"computed fact {x.ref}: stated {x.value}, its inputs give {num_text(got)} ({x.rule})"
        x["precision"] = {"model": "printed", "sd": math.sqrt(sum(v * v for v in sds)) / n}
        x["derived"] = dict(rule=x.rule, inputs=list(x.inputs), value=num_text(got))
        return None

    def decimal(self, x):
        """A source whose numbers use a decimal comma (`decimal_mark: ","`): '12,5' → '12.5', '1.234,5' → '1234.5', '1.234' → '1234'; a
        counts value ('45 из 60') is left as written (27 Oct)."""
        v = x.get("value")
        if self.doc.get("decimal_mark") == "," and isinstance(v, str) and DECIMAL_COMMA.fullmatch(v.strip()) \
                and not x.get("written"):                # a value the agent normalized is read as is (29 Oct)
            x["value"] = re.sub(r"[.\s\u00a0\u202f]", "", v.strip()).replace(",", ".")

    def fact(self, ref, _seen=frozenset()):
        """(Fact, fault or None)."""
        if not ref.startswith("T"):
            f = self.facts.get(ref)
            if f is None:
                return None, f"fact {ref} not found"
            x = Fact(f)
            x["ref"], x["says"] = ref, [f["says"]]
            self.decimal(x)
            fault = "; ".join(self.fact_faults.get(ref, [])) or None
            if f["level"] == "computed" and not fault:
                fault = self.derive(x, _seen)
            return x, fault
        t, row, col = V.split_cell(ref)
        tb = self.tables.get(t)
        if not tb or col not in tb["columns"]:
            return None, f"cell {ref}: table or column not declared"
        spec = tb["columns"][col]
        p = V.saved_path(tb["file"], self.path)
        if not p:
            return None, f"cell {ref}: saved file not reachable here ({tb['file']})"
        if p not in self._sha_ok:
            want = self.doc.get("sha256", {}).get(tb["file"])
            self._sha_ok[p] = want is not None and V.sha256_of(p) == want
        if not self._sha_ok[p]:
            return None, f"cell {ref}: sha256 of {os.path.basename(p)} does not match"
        rows = V.table_rows(tb, self.path)
        if rows is None:
            return None, f"cell {ref}: table format {tb.get('format')} not readable by the build (csv, json)"
        cols, byrow = rows
        if row not in byrow or col not in cols:
            return None, f"cell {ref}: no such row or column in the saved file"
        cell = (byrow[row].get(col) or "").strip()
        if not cell:
            return None, f"cell {ref}: empty"
        says = V.column_says(spec)
        x = Fact(ref=ref, says=says, value=cell, about=row, level=tb.get("level", "written"), form="data-file",
                 where=f"{tb['where']} / row {row} / column {col}", file=tb["file"], table=t, column=col,
                 precision=(spec.get("precision") if isinstance(spec, dict) else None) or tb.get("precision"))
        self.decimal(x)
        if isinstance(spec, dict):
            for k in ("term", "scale", "namespace"):
                if k in spec:
                    x[k] = spec[k]
        return x, None


# ---------------------------------------------------------------- context
class Ctx:
    def __init__(self, args):
        self.args = args
        self.settings = {"cost_method_unstated": args.cost_method_unstated}
        self.rep, self.schemas = V.Report(), V.Schemas(V.HERE)
        self.vocab = self.schemas.doc("vocab.json")
        self.load()

    # -- loading and validation (validate.py's checks, errors routed to what they concern)
    def load(self):
        a, rep, schemas = self.args, self.rep, self.schemas
        fatal = []
        n0 = len(rep.errors)
        V.check_vocab(self.vocab, rep, schemas)
        reg, paths = {}, {}
        for k, name in V.REGISTRY_FILES.items():
            p = os.path.join(a.registry, name)
            paths[k] = p
            if not os.path.isfile(p):
                if k in V.REQUIRED_REGISTRIES:
                    rep.err(V.rel(a.registry), f"no {name}")
                elif k == "prices":
                    rep.err(V.rel(a.registry), "no prices.json: the cost build needs the registered prices "
                                               "(DATA-PIPELINE §8.2; an empty list with its as_of is allowed)")
                continue
            x = V.load_json(p, rep)
            if x is not None and schemas.validate(x, f"{k}.schema.json", V.rel(p), rep):
                reg[k] = x
        self.supplied = self.supply_legacy(reg, a.findings)
        if all(k in reg for k in V.REQUIRED_REGISTRIES):
            V.check_registries(reg, rep, schemas, self.vocab, paths,
                                 a.check_files and not getattr(a, "registry_files_checked", False))
        fatal += rep.errors[n0:]
        self.reg, self.paths = reg, paths
        self.models = (reg.get("models") or {}).get("models", {})
        self.routes = (reg.get("routes") or {}).get("routes", {})
        self.setups = (reg.get("benchmarks") or {}).get("setups", {})
        self.publishers = (reg.get("publishers") or {}).get("publishers", {})
        self.prices = reg.get("prices") or {"as_of": None, "prices": []}
        self.price_tables = (reg.get("price-tables") or {}).get("tables", {})
        self.rules = {r["id"]: r for r in (reg.get("rules") or {}).get("rules", [])}
        cr = a.class_ratios or os.path.join(a.registry, "class-ratios.json")
        self.class_ratios = read_class_ratios(cr) if os.path.isfile(cr) else {"ratios": []}

        # sources
        self.sources, self.measure_files = {}, []
        files = sorted(glob.glob(os.path.join(a.findings, "sources", "*.json")))
        loaded = [(p, V.load_json(p, rep)) for p in files]
        all_ids = {x.get("id") for _, x in loaded if isinstance(x, dict)}
        for p, x in loaded:
            n = len(rep.errors)
            if x is None or not schemas.validate(x, "source.schema.json", V.rel(p), rep):
                fatal += rep.errors[n:]
                continue
            S = Source(p, x, self)
            self.sources[S.id] = S
            V.check_source(x, p, reg, rep, schemas, self.vocab, a.check_files, all_ids)
            L = V.rel(p)
            for e in rep.errors[n:]:
                m = re.match(re.escape(L) + r" (F\d+): (.*)$", e)
                if m:
                    S.fact_faults[m.group(1)].append(m.group(2))
                else:
                    S.faults.append(e)
        # measures
        self.measures = []                  # (Source, measure dict, measure-file faults)
        mvalid = {}
        for p in sorted(glob.glob(os.path.join(a.findings, "measures", "*.json"))):
            n = len(rep.errors)
            x = V.load_json(p, rep)
            if x is None or not schemas.validate(x, "measure.schema.json", V.rel(p), rep):
                fatal += rep.errors[n:]
                continue
            src = self.sources.get(x["source"])
            vsources = {k: (s.path, s.doc) for k, s in self.sources.items()}
            V.check_measures(x, p, vsources, reg, rep, self.vocab, a.check_files)
            L = V.rel(p)
            mf = collections.defaultdict(list)
            for e in rep.errors[n:]:
                m = re.match(re.escape(L) + r" (M\d+): (.*)$", e)
                (mf[m.group(1)] if m else mf["*"]).append(m.group(2) if m else e)
            if src is None:
                fatal.append(f"{L}: source {x['source']} missing or invalid")
                continue
            for m in x["measures"]:
                self.measures.append((src, m, mf.get(m["id"], []) + mf.get("*", [])))
                mvalid[(src.id, m["id"])] = m
        self.mvalid = mvalid
        # decisions
        self.decisions = []
        self.stale = []
        if os.path.isfile(a.decisions):
            n = len(rep.errors)
            x = V.load_json(a.decisions, rep)
            if x is not None and schemas.validate(x, "decisions.schema.json", V.rel(a.decisions), rep):
                vsources = {k: (s.path, s.doc) for k, s in self.sources.items()}
                V.check_decisions(x, a.decisions, vsources, mvalid, reg, rep)
                self.decisions = x["decisions"]
                for d in self.decisions:
                    gone = [r for r in d.get("measures", []) if tuple(r.split("#")) not in mvalid]
                    if gone:
                        self.stale.append(dict(id=d["id"], measures=d["measures"], axis=d["axis"],
                                               why=f"measure(s) not found: {', '.join(gone)}"))
            fatal += rep.errors[n:]
        else:
            for sid, s in self.setups.items():
                if s["headline"].get("decision"):
                    fatal.append(f"setup {sid}: headline decision {s['headline']['decision']} but no decisions file")
        if fatal:
            raise Fatal("\n".join(fatal))
        self.fit_models = self.read_fit_models()
        self.fit_set = set(self.fit_models)
        meth = self.vocab["$defs"]["cost_method"]
        self.method_patterns = [(m, re.compile(meth["x-terms"][m]["legacy_flags"], re.I)) for m in meth["x-order"]]

    @staticmethod
    def supply_legacy(reg, findings):
        """Legacy findings (src-legacy-*) need the placeholder setup `legacy` and the publisher `legacy`: the build
        supplies them when the registry lacks them (data/legacy.py's constants), so a legacy build runs against the
        real registry. → what was supplied."""
        if not glob.glob(os.path.join(findings, "sources", "src-legacy-*.json")):
            return []
        import legacy as LG
        out = []
        bench, pubs = reg.get("benchmarks"), reg.get("publishers")
        if bench is not None:
            if "legacy" not in bench.setdefault("setups", {}):
                bench["setups"].update(LG.LEGACY_SETUP)
                out.append("benchmarks.setups.legacy")
            if "legacy" not in bench.setdefault("families", {}):
                bench["families"]["legacy"] = {"label": "legacy rows"}
                out.append("benchmarks.families.legacy")
        if pubs is not None and "legacy" not in pubs.setdefault("publishers", {}):
            pubs["publishers"].update(LG.LEGACY_PUBLISHER)
            out.append("publishers.legacy")
        return out

    def read_fit_models(self):
        p = self.args.fit_models
        if not p:
            return list(self.models)
        if p == "catalog":
            return read_json_arg(os.path.join(HERE, "catalog", "models.json"), "--fit-models catalog")["order"]
        try:
            with open(p, encoding="utf-8") as f:
                t = f.read()
        except OSError as e:
            raise BadInput(f"--fit-models {p}: {e.strerror}")
        try:
            out = json.loads(t) if t.lstrip().startswith("[") else [w for w in t.split() if w]
        except json.JSONDecodeError as e:
            raise BadInput(f"--fit-models {p}: not a JSON list ({e})")
        if not out or not all(isinstance(x, str) for x in out):
            raise BadInput(f"--fit-models {p}: an empty or malformed model list")
        return out

    # -- registry lookups
    def released(self, key):
        return V.when(self.models[key]["released"]["value"])

    def maker_org(self, key):
        mk = self.models[key]["maker"]
        return self.vocab["$defs"]["maker"]["x-terms"].get(mk, {}).get("org", "~")

    def configs(self, key, iv):
        return {c["id"]: c for c in self.models[key]["configurations"] if covers(c, iv)}


# ---------------------------------------------------------------- the measure
class Measure:
    def __init__(self, ctx, S, m, mfaults):
        self.ctx, self.S, self.m = ctx, S, m
        self.ref = f"{S.id}#{m['id']}"
        self.setup_id = m["setup"]
        self.setup = ctx.setups.get(m["setup"], {})
        self.publisher = S.publisher
        self.faults = [(None, x) for x in S.faults]
        for x in mfaults:                                 # 'slot: …' / 'slot ref: …' → that slot, else the whole measure
            head = re.match(r"([a-z_]+)[ :]", x)
            self.faults.append((head.group(1) if head and head.group(1) in m["facts"] else None, x))
        self.rules = set()
        self.flags = []
        self.fields = {}
        self.status = {"quality": None, "cost": None}
        self.detail = {"quality": "", "cost": ""}
        self.used = []
        self.slots = {}
        for slot, v in m["facts"].items():
            if slot in ("value_seen_in", "other"):
                continue
            refs = v if isinstance(v, list) else ([v] if v else [])
            out = []
            for ref in refs:
                f, fault = S.fact(ref)
                if fault:
                    self.faults.append((slot, f"{slot} {ref}: {fault}"))
                if f is not None:
                    out.append(f)
                    self.used.append(ref)
            self.slots[slot] = out
        self.value = (self.slots.get("value") or [None])[0]
        self.is_cost_only = self.value is not None and "score" not in self.value.says

    def value_is_score(self):
        ref = self.m["facts"].get("value")
        if not ref:
            return False
        if ref.startswith("T"):
            t, _, col = V.split_cell(ref)
            spec = self.S.tables.get(t, {}).get("columns", {}).get(col)
            return spec is not None and "score" in V.column_says(spec)
        return self.S.facts.get(ref, {}).get("says") == "score"

    def axis_faults(self, axis):
        """Step 1 reads every fact *used* on the axis: the score's facts do not take the cost out, nor the reverse."""
        off = {"spend", "usage"} if axis == "quality" else ({"runs", "judge"} | ({"value"} if self.value_is_score()
                                                                                   else set()))
        return [msg for slot, msg in self.faults if slot not in off]

    def slot(self, name, says=None):
        fs = self.slots.get(name, [])
        return [f for f in fs if says is None or set(f.says) & set([says] if isinstance(says, str) else says)]

    def rule(self, r):
        if r:
            self.rules.add(r)


# ---------------------------------------------------------------- run date (§5.1)
def default_upper(M):
    """Earliest of the source's publication, the earliest capture carrying the value, and the commit (end of day for a
    date); the harvest when none is known."""
    S = M.S
    c = []
    p = (S.doc.get("published") or {}).get("value")
    if p:
        c.append(day_bounds(p)[1])
    for cid in M.m["facts"].get("value_seen_in", []):
        cap = S.captures.get(cid)
        if cap:
            c.append(day_bounds(cap["captured"])[1])
    if S.doc.get("commit"):
        for cap in S.captures.values():
            if cap.get("commit") and (cap["commit"].startswith(S.doc["commit"]) or S.doc["commit"].startswith(cap["commit"])):
                c.append(day_bounds(cap["captured"])[1])
    if not c:
        return day_bounds(S.doc["harvested_at"])[1], "harvested_at"
    return min(c), "default"


def shutdown(ctx, key):
    """The last moment a closed model's own maker-API ids served it (every such id ended), else None."""
    m = ctx.models.get(key) or {}
    if m.get("open_weights"):
        return None
    ends = [iv.get("to") for n in m.get("names", []) if n.get("kind") == "api-id" and not n.get("route")
            for iv in n.get("serves", [])]
    if not ends or any(e is None for e in ends):
        return None
    return max(V.when(e, True) for e in ends)


def run_interval(M, key):
    """(lo, hi, ea) for the measure under candidate key; lo None = unclamped (early access). Cached per key."""
    cache = M.__dict__.setdefault("_iv", {})
    if key in cache:
        return cache[key]
    ctx = M.ctx
    days, starts, ends, bad = [], [], [], []
    conv = []
    for f in M.slot("run_date"):
        if f.level not in ACCEPTED:
            continue
        if f.says[0] == "run-date-convention":
            if f.level == "written" and f.pattern:       # a documented convention only
                conv.append(f)
            continue
        b = find_date(f.value)
        if b is None:
            bad.append(f.ref)
            continue
        {"run-date": days, "run-start": starts, "run-end": ends}[f.says[0]].append(b)
    if conv:                                             # ids encoding the run date (documented convention)
        ids = [V.split_cell(M.m["facts"]["value"])[1]] if (M.m["facts"].get("value") or "").startswith("T") else []
        ids += [f.value for f in M.slot("aggregation", "run-id") if f.level in ACCEPTED]
        for f in conv:
            for i in ids:
                mm = re.search(f.pattern, i or "")
                d = mm and re.fullmatch(r"(\d{4})(\d{2})(\d{2})", mm.groupdict().get("date") or "")
                b = _ymd(int(d.group(1)), int(d.group(2)), int(d.group(3))) if d else None
                if b:
                    days.append(b)
                    M.rule("run-date-from-id-convention")
                    break
    hi_default, hi_basis = default_upper(M)
    released = ctx.released(key) if key else None
    lo_c = [b[0] for b in starts] + ([min(b[0] for b in days)] if days else [])
    hi_c = [b[1] for b in ends] + ([max(b[1] for b in days)] if days else [])
    lo = max(lo_c) if lo_c else released
    hi = min(hi_c) if hi_c else hi_default
    basis = {"lo": "stated" if lo_c else "release", "hi": "stated" if hi_c else hi_basis}
    if lo_c and released is not None and lo < released <= hi:  # a stated start before the release: the model ran
        lo, basis["lo"] = released, "release"            # from its release (no early access stated or by date; 28 Oct)
    if key and not hi_c:                                 # a closed model cannot run after its maker API ids stopped
        shut = shutdown(ctx, key)                        # serving it (26 Oct): the default upper bound is capped there
        if shut is not None and shut < hi and (lo is None or lo <= shut):
            hi, basis["hi"] = shut, "shutdown"
            M.rule("run-before-shutdown")
    level = "written" if (lo_c or hi_c) else "computed"
    if lo_c and max(lo_c) > hi:                          # stated bounds contradict: the widest interval, defaults too
        # (a release after the run's upper bound is no contradiction: early access by date, below; 28 Oct)
        lo = min([lo] + lo_c + [b[0] for b in ends] + ([released] if released else []))
        hi = max([hi, hi_default] + hi_c + [b[1] for b in starts])
        level = "not-established:contradictory"
    ea_fact = any(f.level in ACCEPTED for f in M.slot("early_access"))
    ea = bool(ea_fact or (released is not None and hi < released))
    if ea and basis["lo"] == "release":
        lo = None
    out = (lo, hi, ea)
    cache[key] = out
    M.fields.setdefault("run_date_detail", {})[key or "-"] = dict(
        lo=lo.isoformat() if lo else None, hi=hi.isoformat(), early_access=ea, basis=basis, level=level,
        unparsed=bad)
    return out


# ---------------------------------------------------------------- model (§5.1)
def api_matches(ctx, value, ns):
    """[(key, name entry)] an API id resolves to under the name rule, and the route its prefix names (None) and
    whether the route is unknown (a prefix head no route lists)."""
    routes, models = ctx.routes, ctx.models

    def in_ns(v, rid):
        r = routes.get(rid or "maker-api", {})
        for p in sorted(r.get("name_prefixes") or [], key=len, reverse=True):
            if v.casefold().startswith(p.casefold()):
                v = v[len(p):]
                break
        nsr = None if rid in (None, "maker-api") else rid
        return [(k, n) for k, m in models.items() for n in m.get("names", [])
                if n["kind"] == "api-id" and (n.get("route") or None) == nsr and V.same_name(n["name"], v, rid, routes)]
    if ns != "prefix":
        return in_ns(value, ns), ns, False
    head, sep, rest = value.partition("/")
    if sep:
        for rid, r in routes.items():
            if any(p.casefold() == (head + "/").casefold() for p in r.get("name_prefixes") or []):
                return in_ns(value, rid), rid, False
    out = []
    for rid in list(routes) or ["maker-api"]:
        for x in (in_ns(rest, rid) if sep else []) + in_ns(value, rid):
            if x not in out:
                out.append(x)
    return out, None, True


def display_matches(ctx, value):
    n = V.norm_display(value, ctx.vocab)
    return [(k, nm) for k, m in ctx.models.items() for nm in m.get("names", [])
            if nm["kind"] == "display-name" and V.norm_display(nm["name"], ctx.vocab) == n]


def resolve_model(M):
    ctx = M.ctx
    keys_by_fact, ne, selects, modes, quant = [], [], [], [], []
    res = []                                             # per fact: what it resolved to, and why (status report)
    for f in M.slot("model"):
        if f.level not in ACCEPTED:
            ne.append(f.level)
            res.append(dict(fact=f.ref, value=f.value, keys=[], outcome=f"not accepted ({f.level})"))
            continue
        if f.says == ["mode"]:
            modes.append(f)
            continue
        if "quantized-build" in f.says:                  # a stated quantized build: another artefact (29 Oct)
            quant.append(f)
            continue
        if "model-api-id" in f.says:
            matches = api_matches(ctx, f.value, f.namespace or "maker-api")[0]
        elif "model-name" in f.says:
            matches = display_matches(ctx, f.value)
        else:
            continue
        keys = sorted({k for k, _ in matches})
        rule = None
        if len(keys) > 1:                                # an alias: the run must lie in one serves interval
            # no early-access exception here: a name that moved is date-checked against its serves intervals, on
            # one run interval for every candidate (lower bound = the earliest candidate's release, so an interval
            # straddling the switch fits no candidate: never the newer model by default)
            ivs = [run_interval(M, k) for k in keys]
            if any(f.level in ACCEPTED for f in M.slot("early_access")):
                lo = None                                # a stated early-access run: no lower bound
            else:                                        # a candidate released after the run's upper bound has no
                # lower bound of its own (early access by date): the earliest candidate's release is the bound (26 Oct)
                lo = min(x[0] if x[0] is not None else ctx.released(k) for k, x in zip(keys, ivs))
            common = (lo, max(x[1] for x in ivs), False)
            ok = [k for k in keys if any(covers(iv, common) for kk, n in matches if kk == k for iv in n["serves"])]
            if len(ok) == 1:
                keys, rule = ok, "alias-by-date"
            else:
                keys_by_fact.append((f.ref, None, f"alias {f.value!r} serves {keys}: the run interval places it on "
                                                  f"{ok or 'none'}"))
                continue
        if len(keys) == 1:                               # one key, but the name stopped serving it (a stated end, or
            ends = [iv for k, n in matches for iv in n["serves"]]  # a successor build: 29 Oct): the run must lie in
            if ends and all(iv.get("to") is not None and iv.get("to_basis") in ("stated", "successor-release")
                            for iv in ends) and not any(covers(iv, run_interval(M, keys[0])) for iv in ends):
                keys_by_fact.append((f.ref, None, f"{f.value!r} served {keys[0]} only until "
                                                  f"{max(iv['to'] for iv in ends)}: the run interval is not inside"))
                continue
        if not keys:
            keys_by_fact.append((f.ref, None, f"{f.value!r} resolves to no key"))
            continue
        keys_by_fact.append((f.ref, keys[0], rule))
        for k, n in matches:
            if k == keys[0] and n.get("selects"):
                selects.append((f.ref, n["selects"]))
    got = {k for _, k, _ in keys_by_fact if k}
    vals = {r: v for r, v in ((f.ref, f.value) for f in M.slot("model"))}
    out = dict(value=None, level=None, facts=[r for r, _, _ in keys_by_fact], detail="", resolution=res,
               decided_by=None)
    first = next((r for r, k, _ in keys_by_fact if k), None)
    for r, k, d in keys_by_fact:
        res.append(dict(fact=r, value=vals.get(r), keys=[k] if k else [],
                        outcome=("unresolved: " + (d or "no key")) if not k else
                        ("decided" if r == first else "agrees" if k == dict((a, b) for a, b, _ in keys_by_fact)[first]
                         else f"contradicts: gives {k}") + (f" ({d})" if k and d else "")))
    if len(got) > 1:
        mode_of = {md["key"]: k for k in got for md in ctx.models[k].get("modes", [])}
        rel = [f"{k} is a mode of {mode_of[k]}" for k in sorted(got) if mode_of.get(k) in got]
        out.update(level="not-established:contradictory",
                   detail=f"model facts give {sorted(got)}" + (f" ({'; '.join(rel)})" if rel else ""))
    elif not got:
        lv = ne[0] if ne and not keys_by_fact else "not-established:absent"
        out.update(level=lv, detail="; ".join(d for _, k, d in keys_by_fact if not k and d) or "no model fact")
    else:
        key = got.pop()
        rules = {r for _, k, r in keys_by_fact if k and r}
        out.update(value=key, level="computed" if rules else "written", decided_by=first)
        unresolved = [x for x in res if x["outcome"].startswith("unresolved")]
        if quant:                                        # the maker's model, run as a quantized build: out
            out.update(value=None, level="not-established:absent", decided_by=None,
                       detail=f"a quantized build of {key} ({quant[0].ref}: {quant[0].value!r}): another artefact")
            M.fields["model"] = out
            M.selects = selects
            return None
        if unresolved:                                   # doubt → out (the coordinator, 23 Oct)
            out.update(value=None, level="not-established:absent", decided_by=None,
                       detail="; ".join(f"unresolved model fact {x['value']!r} ({x['fact']}): {x['outcome'][12:]}"
                                        for x in unresolved) + f" (the other facts give {key})")
            M.fields["model"] = out
            M.selects = selects
            return None
        for r in rules:
            M.rule(r)
        selected = set()
        for f in modes:                                  # a mode selects its line's key
            iv = run_interval(M, key)
            hit = [md for md in ctx.models[key].get("modes", []) if covers(md, iv) and
                   f.value.strip().casefold() in {md["parameter"].casefold(), (md.get("value") or "").casefold(),
                                                  f"{md['parameter']}={md.get('value', '')}".casefold()}]
            chain, unknown = route_chain_facts(M)
            if unknown:                                  # every candidate route counts
                chain = [r for ch, _ in chains(M, key) for r in ch]
            if not hit:
                out.update(value=None, level="not-established:absent", detail=f"mode {f.value!r} not registered")
                break
            elif any(ctx.routes.get(r, {}).get("class") == "router" for r in chain):
                M.rule("pro-via-router-out")
                out.update(value=None, level="not-established:absent",
                           detail=f"mode {f.value!r} through a router that cannot separate it")
                break
            else:
                M.rule("mode-to-line")
                selected.add(hit[0]["key"])
                res.append(dict(fact=f.ref, value=f.value, keys=[hit[0]["key"]], outcome=f"mode: {key} → {hit[0]['key']}"))
                out.update(value=hit[0]["key"], level="computed", decided_by=f.ref)
        if len(selected) > 1:                            # two mode facts select two keys: a mode contradicted
            out.update(value=None, level="not-established:contradictory",
                       detail=f"mode facts select {sorted(selected)}")
    M.fields["model"] = out
    M.selects = selects
    return out["value"]


# ---------------------------------------------------------------- routes
CLASS_RANK = {"harness": 0, "router": 1, "reseller": 1, "host": 1, "self-hosted": 1, "maker-api": 2}


def route_of_fact(ctx, f):
    if f.level not in ACCEPTED:
        return None
    if f.term and f.term in ctx.routes:
        return f.term
    if "model-api-id" in f.says and f.namespace == "prefix":
        return api_matches(ctx, f.value, "prefix")[1]
    v = f.value.strip().casefold()
    for rid, r in ctx.routes.items():
        if v == rid or v in {s.casefold() for s in r.get("spellings", [])}:
            return rid
    return None


def route_chain_facts(M):
    """(known routes in chain order, route unknown?) from the route slot."""
    ctx = M.ctx
    known, unknown = [], False
    for f in M.slot("route"):
        r = route_of_fact(ctx, f)
        if r is None:
            unknown = True
        elif r not in known:
            known.append(r)
    if not M.slot("route"):
        unknown = True
    known.sort(key=lambda r: CLASS_RANK.get(ctx.routes[r]["class"], 1))
    if any(ctx.routes[r]["class"] != "harness" for r in known):
        unknown = False                                  # a non-harness step is named: the chain is known
    elif known:
        unknown = True                                   # only a harness: what it calls is not stated
    return known, unknown


def route_serves_model(ctx, rid, key, iv):
    e = ctx.routes[rid].get("models", {}).get(key)
    if not e:
        return False
    lo, hi, _ = iv
    recs = e.get("ids") or (e.get("accepts", []) + e.get("mapping", []) + e.get("default", []))
    return any(overlaps(r, lo, hi) for r in recs)


def chains(M, key):
    """Candidate route chains [(chain, how)]: the stated chain, or one per candidate route when the route is unknown."""
    ctx = M.ctx
    known, unknown = route_chain_facts(M)
    iv = run_interval(M, key)

    def close(ch):
        """The maker's API closes a chain only when nothing else serves the run (a harness alone, or nothing): the
        maker's conversions and defaults reach a run only through the maker's API or a reseller, never through a
        router, a host or self-hosting (registry review, 23 Oct)."""
        ch = list(ch)
        if not any(ctx.routes[r]["class"] in ("maker-api", "reseller", "router", "host", "self-hosted") for r in ch):
            ch.append("maker-api")
        return ch
    if not unknown:
        return [(close(known), "stated")]
    harness = [r for r in known if ctx.routes[r]["class"] == "harness"]
    if harness and all(ctx.routes[r].get("label_as_level") for r in harness):
        # a closed harness whose label is the level sent (the maintainer's rule closed-harness-label, 26 Oct): the call
        # reaches the maker's API, so no other candidate route is weighed
        return [(close(harness + ["maker-api"]), "closed harness: label as level")]
    unresolved = any(route_of_fact(ctx, f) is None for f in M.slot("route"))
    if not unresolved:
        # the source names no router, reseller or host (nothing at all, or only a harness): the run is presumed to
        # have gone through the maker's API, flagged (the maintainer's rule route-presumed-maker-api, 26 Oct); a route
        # the source names but the registry cannot resolve stays unknown and weighs every candidate
        M.rule("route-presumed-maker-api")
        if "route-presumed-maker-api" not in M.flags:
            M.flags.append("route-presumed-maker-api")
        return [(close(harness + ["maker-api"]), "presumed maker-api")]
    cands = [r for r in ctx.routes if ctx.routes[r]["class"] not in ("harness", "maker-api")
             and route_serves_model(ctx, r, key, iv)]
    out = [(close(harness + ["maker-api"]), "candidate maker-api")]
    out += [(close(harness + [r]), f"candidate {r}") for r in cands]
    return out


def map_requested(ctx, text):
    """A requested setting as a route or maker document writes it ('none', 'low') → a configuration id or the text."""
    c = map_setting(ctx, text)
    return c[0] if c else text


def serve(M, key, chain, req, iv, configs):
    """Apply the route chain harness → router / reseller / host → maker to a requested configuration.
    → (configuration or None, level, detail)."""
    ctx = M.ctx
    cur = req
    for i, step in enumerate(chain):
        r = ctx.routes[step]
        cls = r["class"]
        on = step_filter(ctx, key, chain, i)
        if cls in ("maker-api", "reseller"):
            conv = [c for c in ctx.models[key].get("conversions", []) if c["route"] == step and covers(c, iv)
                    and map_requested(ctx, c["requested"]) == cur]
            if conv:
                M.rule("maker-conversion-dated")
                M.rule("decision-c-conversions-dated")
                cur = conv[0]["served"]
            elif configs.get(cur, {}).get("served") == "converted":
                return None, "not-established:absent", f"{cur}: converted by the maker, no dated conversion"
            if cur in ("budget-converted", "ambiguous"):
                return None, f"not-established:{'ambiguous' if cur == 'ambiguous' else 'absent'}", cur
            continue
        e = r.get("models", {}).get(key, {})
        mp = [x for x in e.get("mapping", []) + r.get("mapping", []) if on(x) and covers(x, iv)
              and map_requested(ctx, x["requested"]) == cur]
        if mp:
            M.rule("route-mapping-dated")
            cur = mp[0]["served"]
            if cur in ("budget-converted", "ambiguous"):
                return None, f"not-established:{'ambiguous' if cur == 'ambiguous' else 'absent'}", f"{step}: {cur}"
            continue
        acc = [a["configuration"] for a in e.get("accepts", []) if on(a) and covers(a, iv)]
        if cur in acc:
            continue
        lm = [x for x in r.get("level_mapping", []) if on(x) and covers(x, iv)]
        if not lm and cls == "harness" and r.get("label_as_level"):
            M.rule("closed-harness-label")
            if f"harness-label-as-level:{step}" not in M.flags:
                M.flags.append(f"harness-label-as-level:{step}")
            continue
        if not lm:
            return None, "not-established:absent", f"{step} documents nothing for {key} @ {cur} at the run date"
        rule = lm[0]["rule"]
        M.rule("route-mapping-dated")
        if rule == "identity":
            continue
        if rule == "budget":
            return None, "not-established:absent", f"{step}: budget-converted"
        if rule == "nearest-supported":
            lv = [a for a in acc if a in LEVELS]
            if cur not in LEVELS or not lv:
                return None, "not-established:absent", f"{step}: nearest-supported without accepted levels"
            i = LEVELS.index(cur)
            dist = sorted((abs(LEVELS.index(a) - i), a) for a in lv)
            if len(dist) > 1 and dist[0][0] == dist[1][0]:
                return None, "not-established:ambiguous", f"{step}: {cur} ties between {dist[0][1]} and {dist[1][1]}"
            cur = dist[0][1]
            continue
        return None, "not-established:absent", f"{step}: table mapping without an entry for {cur}"
    if not any(ctx.routes[st]["class"] in ("maker-api", "reseller") for st in chain) and \
            configs.get(cur, {}).get("served") == "converted":
        return None, "not-established:absent", (f"{cur}: converted by the maker, and the conversion reaches a run "
                                                f"only through the maker's API or a reseller")
    return cur, "computed" if cur != req else "written", ""


def step_filter(ctx, key, chain, i):
    """A route record applies to this step of the chain when its `via` names the next step (a harness maps a level
    per provider: registry fix, 26 Oct), its `maker` is the model's maker and its `models` list the key (each absent:
    any)."""
    nxt = chain[i + 1] if i + 1 < len(chain) else None
    maker = ctx.models[key].get("maker")

    def on(x):
        return (not x.get("via") or x["via"] == nxt) and (not x.get("maker") or x["maker"] == maker) and \
            (not x.get("models") or key in x["models"])
    return on


def over_chains(M, key, fn):
    """Evaluate fn(chain) over the candidate chains; accepted only if all agree."""
    res = [(how, fn(ch)) for ch, how in chains(M, key)]
    vals = {r[0] for _, r in res}
    if len(res) == 1:
        return res[0][1]
    if len(vals) == 1 and None not in vals:
        return res[0][1][0], "computed", f"all candidate routes agree ({', '.join(h for h, _ in res)})"
    return None, "not-established:absent", "candidate routes disagree: " + "; ".join(
        f"{h} → {r[0] or r[1]}" for h, r in res)


def thinking_requested(M):
    """The call turned thinking on: an accepted thinking-on fact, or a name selecting think."""
    return any(f.level in ACCEPTED and "thinking-on" in f.says for f in M.slot("effort")) or \
        any(sel == "think" for _, sel in M.selects)


def maker_defaults(M, key, iv):
    """The maker's defaults covering the run for this call. A default with `setting` answers for part of the call
    (registry fix, 26 Oct): `thinking` for a call with no thinking field, `effort` for a call that turns thinking on
    but sends no level. A call that turned thinking on gets the effort default (else the whole-call one); a call that
    sent neither gets the whole-call default, else the thinking default."""
    d = [x for x in M.ctx.models[key].get("default", []) if covers(x, iv)]
    call = [x for x in d if not x.get("setting")]
    if thinking_requested(M):
        return [x for x in d if x.get("setting") == "effort"] or call
    return call or [x for x in d if x.get("setting") == "thinking"]


def default_via(M, key, chain, iv, configs):
    """Step 7: the documented default along the chain (a router's or host's own when it is on the chain)."""
    ctx = M.ctx
    for i, step in enumerate(chain):
        r = ctx.routes[step]
        cls = r["class"]
        if cls in ("maker-api", "reseller"):
            d = maker_defaults(M, key, iv)
            if not d:
                return None, "not-established:absent", f"no documented default of {key} covering the run (→ default)"
            M.rule("api-default-documented")
            return serve(M, key, chain[i:], d[0]["configuration"], iv, configs)
        on = step_filter(ctx, key, chain, i)
        d = [x for x in r.get("models", {}).get(key, {}).get("default", []) if on(x) and covers(x, iv)]
        if d:
            M.rule("api-default-documented")
            return serve(M, key, chain[i + 1:], d[0]["configuration"], iv, configs)
        return None, "not-established:absent", f"{step}: no documented default for {key} covering the run (→ default)"
    return None, "not-established:absent", "default"


# ---------------------------------------------------------------- configuration (§5.1 steps 1–8)
def spelling_match(ctx, text, kinds):
    """'nothink' / 'think' when a listed spelling of one of these kinds matches the text, else None."""
    V_ = ctx.vocab["$defs"]
    for cfg, name in (("nothink", "nothink_spelling"), ("think", "think_spelling")):
        for rec in V_[name]["x-terms"].values():
            if rec["kind"] in kinds and re.search(rec["regex"], text or "", re.I):
                return cfg
    return None


def map_setting(ctx, value, column=None):
    """A setting line or value → (configuration, how) or None."""
    v = (value or "").strip().strip("\"'").casefold()
    if v in LEVELS:
        return v, "level"
    if v in LEVEL_ALIASES:
        return LEVEL_ALIASES[v], "level"
    texts = [value] + ([f"{column}: {value}", f"{column}={value}"] if column else [])
    for t in texts:
        c = spelling_match(ctx, t, ("setting",))
        if c:
            return c, "spelling"
    for cid, rec in ctx_vocab_terms(ctx, "configuration").items():   # a configuration with its own spelling
        if rec.get("regex") and re.search(rec["regex"], value or "", re.I):
            return cid, "spelling"
    if re.fullmatch(r"[0-9]+(\.[0-9]+)?", v):
        return f"scalar-{v}", "scalar"
    if v in NOT_ESTABLISHED:
        return v, "not-established"
    inner = kv_value(value)
    if inner and inner.casefold() != v:
        return map_setting(ctx, inner, None)
    return None


def map_label(ctx, value):
    """The label rule first: a label naming one level ('high', 'high (thinking on)') is that level; then the
    thinking spellings ('Non-reasoning', '(Reasoning)')."""
    t = (value or "").casefold()
    for a, lv in LEVEL_ALIASES.items():
        t = t.replace(a, lv)
    toks = [LEVEL_TOKEN_ALIASES.get(w, w) for w in re.findall(r"[a-z0-9]+", t) if w not in LABEL_FILLER]
    levels = {w for w in toks if w in LEVELS}
    if len(levels) == 1:
        return levels.pop()
    c = spelling_match(ctx, value, ("label",))
    if c:
        return c
    if len(toks) == 1 and re.fullmatch(r"[0-9]+(\.[0-9]+)?", toks[0]):
        return f"scalar-{toks[0]}"
    return None


def label_to_ladder(value, configs):
    """'lowest effort setting' → the lowest level when the model's configurations make it unique."""
    t = (value or "").casefold()
    lv = [c for c in LEVELS if c in configs]
    if re.search(r"\b(lowest|least|minimum)\b|最低|最小", t):       # CJK 最低/最小 (lowest), 最大/最高 (highest): 28 Oct
        if not lv:
            return None, "no level in the model's configurations"
        if "nothink" in configs:
            return None, "ambiguous: thinking off or the lowest level"
        return lv[0], ""
    if re.search(r"\b(highest|maximum|most)\b|最大|最高", t):
        return (lv[-1], "") if lv else (None, "no level in the model's configurations")
    return None, "label names no configuration"


def in_list(cfg, configs):
    if cfg in configs:
        return True
    m = re.fullmatch(r"think-([0-9]+)", cfg or "")
    if m:
        n = int(m.group(1))
        for c in configs.values():
            if c["id"] == "think-<budget>" and c.get("budget_min", 1) <= n <= (c.get("budget_max") or 10 ** 12):
                return True
    return False


def configuration(M, key):
    ctx = M.ctx
    iv = run_interval(M, key)
    configs = ctx.configs(key, iv)
    out = dict(value=None, level=None, step=None, facts=[], detail="")
    M.fields["configuration"] = out
    M.fields["configurations_offered"] = sorted(configs)
    if set(configs) == {"solo"}:
        out.update(value="solo", level="computed", step=1, detail="the model's list is [solo]")
        return
    facts = M.slot("effort")
    accepted = [f for f in facts if f.level in ACCEPTED]
    results = []                                         # (step, config or None, level, detail, fact ref, kind)

    def via_chain(req, step, ref, kind):
        # the route chain applies to every requested configuration, also one the model does not list (a router's
        # nearest supported level); what comes out must be one of the model's configurations to match
        cfg, lv, d = over_chains(M, key, lambda ch: serve(M, key, ch, req, iv, configs))
        if cfg and not in_list(cfg, configs):
            d = (d + "; " if d else "") + f"{cfg} is not one of the model's configurations"
        results.append((step if cfg == req or not cfg else 6, cfg, lv, d, ref, kind))

    def think_or_default(step, ref, kind):
        # thinking on with no level, on a model whose list has levels but no `think` (reasoning always on, or thinking
        # only with a level): the maker's documented effort default is the level (the maintainer's judgement, 26 Oct)
        if "think" in configs or not any(c in configs for c in LEVELS):
            via_chain("think", step, ref, kind)
            return
        cfg, lv, d = over_chains(M, key, lambda ch: default_via(M, key, ch, iv, configs))
        if cfg:
            M.rule("thinking-on-default-level")
            if "level-from-default" not in M.flags:
                M.flags.append("level-from-default")
        results.append((7, cfg, lv if cfg else "not-established:absent",
                        d or ("" if cfg else "thinking on, no level, no documented default"), ref, kind + ":default"))

    for f in accepted:
        s = f.says[0] if len(f.says) == 1 else next((x for x in f.says if x in (
            "thinking-budget", "effort-setting", "effort-label", "thinking-on", "thinking-off", "no-effort-sent",
            "config-history", "effort-order")), f.says[0])
        if s == "thinking-budget":
            n = int(f.term) if (f.term or "").isdigit() else None
            if n is None:
                results.append((2, None, "not-established:absent", "budget without a token count", f.ref, s))
            else:
                results.append((2, f"think-{n}", f.level, "", f.ref, s))
        elif s in ("effort-setting", "config-history"):
            if s == "config-history":
                ds = all_dates(f.where)
                if len(ds) < 2 or not (ds[0][0] <= (iv[0] or MIN) and iv[1] <= ds[1][1]):
                    results.append((3, None, "not-established:absent",
                                    "config history does not cover the run interval", f.ref, s))
                    continue
                M.rule("config-unchanged-over-interval")
            got = map_setting(ctx, f.value, f.column)
            if got is None:
                results.append((3, None, "not-established:absent", f"setting {f.value!r} not recognised", f.ref, s))
            elif got[1] in ("scalar",):
                results.append((2, got[0], f.level, "a numeric scale without a mapping", f.ref, s))
            elif got[1] == "not-established":
                results.append((3, got[0], f.level, f"setting {f.value!r}", f.ref, s))
            else:
                via_chain(got[0], 3, f.ref, s)
        elif s == "thinking-on":
            think_or_default(3, f.ref, s)
        elif s == "thinking-off":
            M.rule("thinking-off")
            via_chain("nothink", 3, f.ref, s)
        elif s == "effort-label":
            lab = map_label(ctx, f.value)
            if lab and lab.startswith("scalar-"):
                results.append((2, lab, f.level, "a numeric scale without a mapping", f.ref, s))
            elif lab == "think":
                M.rule("label-rule")
                think_or_default(4, f.ref, s)
            elif lab == "max" and not any(c["id"] == "max" for c in ctx.models[key].get("configurations", [])) \
                    and any(c in configs for c in LEVELS):
                # "max effort" written for a model that has no `max` level at all: its highest level (27 Oct)
                c, d = label_to_ladder("maximum", configs)
                M.rule("label-to-ladder")
                if "max-as-highest" not in M.flags:
                    M.flags.append("max-as-highest")
                via_chain(c, 5, f.ref, s)
            elif lab:
                M.rule("label-rule")
                via_chain(lab, 4, f.ref, s)
            else:
                c, d = label_to_ladder(f.value, configs)
                if c:
                    M.rule("label-to-ladder")
                    via_chain(c, 5, f.ref, s)
                else:
                    results.append((5, None, "not-established:ambiguous" if d.startswith("ambiguous")
                                    else "not-established:absent", f"label {f.value!r}: {d}", f.ref, s))
        elif s == "effort-order":                       # the k-th of n points of an effort chart (the maintainer, 26 Oct)
            k, n = (int(x) for x in f.value.split("/"))
            lv = [c for c in LEVELS if c in configs]
            if len(lv) != n:
                results.append((5, None, "not-established:ambiguous",
                                f"chart point {k} of {n}: the model has {len(lv)} levels ({', '.join(lv) or 'none'})", f.ref, s))
            else:
                M.rule("chart-effort-order")
                if "effort-from-chart-order" not in M.flags:
                    M.flags.append("effort-from-chart-order")
                via_chain(lv[k - 1], 5, f.ref, s)
        elif s == "no-effort-sent":
            M.rule("no-effort-setting")
            cfg, lv, d = over_chains(M, key, lambda ch: default_via(M, key, ch, iv, configs))
            results.append((7, cfg if cfg else "default", lv if cfg else "not-established:absent", d, f.ref, s))
    for ref, sel in M.selects:
        via_chain(sel, 3, ref, "name-selects")

    out["facts"] = [f.ref for f in facts]
    est = [r for r in results if r[1] and r[2] in ACCEPTED]
    if not results:
        if facts:
            out.update(value=None, level=facts[0].level if facts[0].level not in ACCEPTED else
                       "not-established:absent", step=None, detail="effort facts not accepted")
        else:
            out.update(value="unstated", level="not-established:absent", step=8, detail="no effort fact")
        return
    if not est:
        r = sorted(results, key=lambda r: r[0])[0]
        out.update(value=r[1], level=r[2] if r[2] not in ACCEPTED else "not-established:absent", step=r[0],
                   detail=r[3])
        return
    est.sort(key=lambda r: r[0])
    listed = [r for r in est if in_list(r[1], configs)]
    if listed:                                           # a step matches only one of the model's configurations
        est = listed
    vals = {r[1] for r in est}
    if len(vals) > 1:
        kinds = {r[5] for r in est}
        lv = [r for r in est if r[1] in LEVELS and r[5] in ("effort-setting", "config-history", "effort-label",
                                                            "effort-order")]
        others = [r for r in est if r not in lv]
        # thinking on and a level: the level is the more specific; also when thinking on alone would have read the
        # maker's default level (a levels-only model, thinking-on-default-level, 27 Oct)
        if lv and others and len({r[1] for r in lv}) == 1 and all(
                (r[1] == "think" and r[5] in ("thinking-on", "name-selects")) or r[5].endswith(":default") for r in others):
            r = lv[0]
            if any(o[5].endswith(":default") for o in others) and \
                    not any(o[5].endswith(":default") for o in results if o not in others):
                M.rules.discard("thinking-on-default-level")   # the default was not used: the level was stated
                if "level-from-default" in M.flags:
                    M.flags.remove("level-from-default")
            out.update(value=r[1], level=r[2], step=r[0], detail="thinking on with a level: the level")
            return
        specific = [r for r in est if r[5] in ("name-selects", "thinking-on", "thinking-off")]
        # the id selects thinking, the null field says no level was sent → the more specific statement
        if kinds <= {"no-effort-sent", "name-selects", "thinking-on", "thinking-off"} and \
                len({r[1] for r in specific}) == 1 and {r[1] for r in specific} <= {"think", "nothink"}:
            r = specific[0]
            out.update(value=r[1], level=r[2], step=r[0], detail="the more specific statement of the same call")
            return
        out.update(value=None, level="not-established:contradictory", step=est[0][0],
                   detail="effort facts give " + ", ".join(f"{r[1]} ({r[4]})" for r in est))
        return
    r = est[0]
    if r[0] == 7 and r[1] == "default":
        out.update(value="default", level="not-established:absent", step=7, detail=r[3])
        return
    out.update(value=r[1], level="computed" if r[0] in (5, 6, 7) or r[2] == "computed" else r[2], step=r[0],
               detail=r[3])


def budgets_merge(measures):
    """Budgets within 5 % are one value (per model): each think-<n> becomes its cluster's smallest budget."""
    by_model = collections.defaultdict(set)
    for M in measures:
        c = M.fields.get("configuration", {}).get("value") or ""
        k = M.fields.get("model", {}).get("value")
        if k and re.fullmatch(r"think-[0-9]+", c):
            by_model[k].add(int(c[6:]))
    canon = {}
    for k, ns in by_model.items():
        head = None
        for n in sorted(ns):
            if head is None or n > head * 1.05:
                head = n
            canon[(k, n)] = head
    for M in measures:
        c = M.fields.get("configuration", {}).get("value") or ""
        k = M.fields.get("model", {}).get("value")
        if (k, int(c[6:]) if re.fullmatch(r"think-[0-9]+", c) else None) in canon:
            n2 = canon[(k, int(c[6:]))]
            if n2 != int(c[6:]):
                M.fields["configuration"]["detail"] += f" (budget {c[6:]} merged with {n2}: within 5 %)"
                M.fields["configuration"]["value"] = f"think-{n2}"


# ---------------------------------------------------------------- value and cost fields
def precision_sd(f, step, chart=None):
    p = f.precision or {}
    m = p.get("model")
    if m == "printed" and p.get("sd") is not None:        # a computed fact: its inputs' readings propagated
        return float(p["sd"])
    if m == "exact":
        return 0.0
    if m == "chart-pixel":
        if p.get("sd") is not None:
            return float(p["sd"])
        return None
    if m == "printed" and p.get("step") is not None:
        return float(p["step"]) / S12
    return float(step) / S12 if step is not None else None


def score_number(M, f):
    """A score (or run-score) fact on the setup's scale → (number, step, sd, rules) or None when not a number.
    scale-conversion: fraction ↔ percent, exact; percent-from-counts: 'k of N' → 100·k/N (k/N on a fraction metric)."""
    b = M.setup.get("bounds") or [None, None]
    target = "percent" if b[1] == 100 else "fraction" if b[1] == 1 else "raw"
    if f.scale == "counts":
        m = V.COUNTS.fullmatch(f.value or "")
        if not m or int(m.group(2).replace(",", "")) == 0:
            return None
        k, n = Decimal(m.group(1).replace(",", "")), Decimal(m.group(2).replace(",", ""))
        d = k * 100 / n if target == "percent" else k / n if target == "fraction" else k
        d = d.quantize(Decimal("1e-6")).normalize() if target != "raw" else d
        return d, Decimal("1e-6"), 0.0, ["percent-from-counts"]
    parsed = parse_number(f.value)
    if parsed is None:
        return None
    d, step = parsed
    sd = precision_sd(f, step)
    rules = []
    if f.scale == "fraction" and target == "percent":
        d, step, sd, rules = d.scaleb(2), step.scaleb(2), (sd * 100 if sd is not None else None), ["scale-conversion"]
    elif f.scale == "percent" and target == "fraction":
        d, step, sd, rules = d.scaleb(-2), step.scaleb(-2), (sd / 100 if sd is not None else None), ["scale-conversion"]
    return d, step, sd, rules


def score_field(M):
    f = M.value
    if f is None or "score" not in f.says:
        return None
    out = dict(text=f.value, level=f.level, facts=[f.ref], number=None, prec=None, rules=[])
    got = score_number(M, f)
    if got is None:
        out["level"] = "unreadable"
        M.faults.append(("value", f"value {f.ref}: {f.value!r} is not a number"))
        M.fields["score"] = out
        return out
    d, step, sd, rules = got
    for r in rules:
        out["rules"].append(r)
        M.rule(r)
    if rules and f.level == "written":
        out["level"] = "computed"
    if f.level == "read":
        M.rule("chart-reading")
    out.update(number=d, step=step, prec=sd)
    M.fields["score"] = out
    return out


def run_id(f):
    """A per-run fact's run: its `run`, or for a table cell its row key."""
    return f.about if f.ref.startswith("T") else f.run


def mean_of_runs(M, failures):
    """The source's mean includes a failed run: recompute it from the per-run values without the failed runs, once
    the mean of all of them reproduces the source's value. → None when recomputed, else why not."""
    sf = M.fields.get("score")
    runs = [f for f in M.slot("runs") if f.level in ACCEPTED]
    if not runs or not sf or sf.get("number") is None:
        return "no per-run values written"
    vals, steps = {}, []
    for f in runs:
        got = score_number(M, f)
        if got is None or run_id(f) in vals:
            return f"run {run_id(f)!r} unreadable or listed twice"
        vals[run_id(f)] = got
        steps.append(float(got[1]))
    failed = set()
    for a in failures:
        rid = a.run if not a.ref.startswith("T") else (a.about if a.about in vals else None)
        if not rid or rid not in vals:
            return f"failure {a.ref} names no run of the mean"
        failed.add(rid)
    mean_all = sum(float(v[0]) for v in vals.values()) / len(vals)
    if abs(mean_all - float(sf["number"])) > float(sf["step"]) + max(steps):
        return f"the runs' mean {mean_all:.6g} does not reproduce the source's {num_text(sf['number'])}"
    kept = [v for r, v in vals.items() if r not in failed]
    if not kept:
        return "every run failed"
    mean = sum(v[0] for v in kept) / Decimal(len(kept))
    dec = max(0, -Decimal(str(min(steps))).as_tuple().exponent) + 2
    mean = round(mean, dec).normalize()
    sds = [v[2] for v in kept if v[2] is not None]
    sf.update(number=mean, prec=(math.sqrt(sum(x * x for x in sds)) / len(kept)) if sds else None,
              level="computed", source_mean=sf["text"], runs_kept=sorted(r for r in vals if r not in failed),
              runs_failed=sorted(failed))
    sf["rules"].append("mean-of-runs")
    M.rule("mean-of-runs")
    return None


def cost_field(M):
    """The measure's raw cost with currency, unit, basis, method, price date and per-class tokens."""
    spend = M.slot("spend")
    costs = [f for f in spend if "cost" in f.says]
    if M.value is not None and "cost" in M.value.says and M.value not in costs:
        costs.insert(0, M.value)
    if not costs:
        return None
    out = dict(facts=sorted({f.ref for f in costs}), level=None, rules=[])
    vals = {f.value for f in costs}
    if len(vals) > 1:
        out.update(level="not-established:contradictory", detail=f"several costs {sorted(vals)}")
        M.fields["cost"] = out
        return out
    f = costs[0]
    parsed = parse_number(f.value)
    out["level"] = f.level
    if parsed is None:
        out.update(level="unreadable")
        M.faults.append(("spend", f"cost {f.ref}: {f.value!r} is not a number"))
        M.fields["cost"] = out
        return out
    out["number"], out["step"] = parsed
    out["prec"] = precision_sd(f, parsed[1])
    out["scope"] = f.table or f.chart or "facts"

    def terms(says, slot="spend"):
        return sorted({x.term for x in M.slot(slot, says) if x.level in ACCEPTED and x.term})
    cur = terms("currency")
    out["currency"] = cur[0] if len(cur) == 1 else (None if not cur else "contradictory")
    units = terms("unit")
    out["unit"] = units[0] if len(units) == 1 else ("" if not units else "contradictory")
    uunits = terms("unit", "usage")
    out["usage_unit"] = uunits[0] if len(uunits) == 1 else None
    basis, method = terms("cost-basis"), terms("cost-method")
    meth = ctx_vocab_terms(M.ctx, "cost_method")
    out["method"] = method[0] if len(method) == 1 and method[0] != "unstated" else (
        "contradictory" if len(method) > 1 else None)
    out["basis"] = basis[0] if len(basis) == 1 else ("contradictory" if len(basis) > 1 else (
        meth.get(out["method"], {}).get("basis") if out["method"] and out["method"] != "contradictory" else "unknown"))
    pt = [x for x in M.slot("spend", "price-table") if x.level in ACCEPTED]
    out["price_table_date"] = None
    for x in pt:
        b = find_date(x.value) or find_date(x.quote)
        if b:
            out["price_table_date"] = b
            break
    tok = {}
    for x in M.slot("usage"):
        if x.level not in ACCEPTED:
            continue
        s = x.says[0]
        p = parse_number(x.value)
        if p is None:
            continue
        if s in TOKEN_CLASS:
            tok[TOKEN_CLASS[s]] = p
        elif s in ("tokens-reasoning", "tokens-total", "requests", "cached-share", "tokens-in-per-request"):
            tok[s] = p
    out["tokens"] = tok
    ri = {x.term for x in M.slot("usage", "reasoning-included-in-out") if x.level in ACCEPTED and x.term in ("true", "false")}
    out["reasoning_included"] = True if ri == {"true"} else False if ri == {"false"} else None   # None: not stated
    M.fields["cost"] = out
    return out


def reproduce_cost(M, key):
    """A stated cost method with a pinned price table (a price-table fact whose term is a price-tables.json id):
    reproduced from the run's tokens; off by more than its rounding → the cost is contradictory (out); no card or no
    tokens → accepted as written (coordinator, 23 Oct)."""
    from convert import reproduce as RP
    C = M.fields["cost"]
    pins = sorted({x.term for x in M.slot("spend", "price-table") if x.level in ACCEPTED and x.term})
    if not pins or C.get("number") is None or C.get("level") not in ACCEPTED:
        return
    if C.get("method") not in ("tokens×list", "library-table", "publisher-table"):
        C["reproduction"] = "a pinned table but no stated token-based method: not reproduced"
        return
    table = M.ctx.price_tables.get(pins[0])
    if table is None:
        C["reproduction"] = f"price table {pins[0]} not registered: accepted as written"
        return
    cand = [c for c, _ in chains(M, key)]
    route = next((r for r in cand[0] if r != "maker-api"), None) if len(cand) == 1 else None
    card = RP.find_card(table, key, route)
    if card is None or card.get("currency") != C.get("currency"):
        C["reproduction"] = f"no card for {key} in {pins[0]}: accepted as written"
        return
    tok = {k: v[0] for k, v in (C.get("tokens") or {}).items() if k in RP.CLASSES or k == "tokens-reasoning"}
    computed, why = RP.card_cost(tok, card["classes"], table.get("input_includes_cache_read", False),
                                 table.get("reasoning_in_output", True), C.get("reasoning_included"))
    if computed is None:
        C["reproduction"] = f"not reproducible ({why}): accepted as written"
        return
    rel = max([count_rel_rounding(v) for k, v in (C.get("tokens") or {}).items() if k in RP.CLASSES] + [0.0])
    v, gap = RP.verdict(float(C["number"]), float(C["step"]), computed, rel)
    M.rule("cost-reproduction")
    C["reproduction"] = f"{v}: {pins[0]} gives {computed:.6g} for {num_text(C['number'])} ({gap:.2%} apart)"
    if v == "off":
        C["level"] = "not-established:contradictory"
        C["detail"] = f"stated method reproduced and off by more than its rounding: {C['reproduction']}"


def ctx_vocab_terms(ctx, name):
    return ctx.vocab["$defs"][name].get("x-terms", {})


# ---------------------------------------------------------------- prices (§4 prices.json, §5.3.1)
def for_config(p, config):
    """A price entry applies to the configuration: no `configurations` (every one), or the configuration is listed."""
    return not p.get("configurations") or config in p["configurations"]


def std_entries(ctx, key, route="maker-api", currency=None, config=None):
    return [p for p in ctx.prices["prices"] if p["model"] == key and p["route"] == route and p["kind"] == "standard"
            and (currency is None or p["currency"] == currency) and for_config(p, config)]


def base_price(ctx, key, currency=None, config=None):
    """The base price in the cost's currency (and for the measure's configuration, when the maker prices
    configurations differently): the entry marked base, else the standard maker-API price in force on as_of, else
    (a retired model) its last list price."""
    marked = [p for p in ctx.prices["prices"] if p["model"] == key and p.get("base")
              and (currency is None or p["currency"] == currency) and for_config(p, config)]
    if marked:
        return marked[0]
    asof = ctx.prices.get("as_of")
    if not asof:
        return None
    t = V.when(asof)
    on = [p for p in std_entries(ctx, key, currency=currency, config=config)
          if V.when(p["from"]) <= t <= V.when(p["to"], True)]
    if on:
        return on[0]
    promo = [p for p in ctx.prices["prices"] if p["model"] == key and p["route"] == "maker-api" and p["kind"] == "promotion"
             and p.get("list_after") and (currency is None or p["currency"] == currency) and for_config(p, config)
             and V.when(p["from"]) <= t <= V.when(p["to"], True)]
    if promo:                                            # a promotion in force that states the list price after it
        la = promo[0]["list_after"]
        return dict(promo[0], kind="standard", classes=la["classes"], long_context=[], **{"from": la["from"], "to": la["from"]},
                    _scheduled_list=True)
    past = sorted((p for p in std_entries(ctx, key, currency=currency, config=config) if V.when(p["to"], True) < t),
                  key=lambda p: V.when(p["to"], True))
    return dict(past[-1], _last_list=True) if past else None   # a retired model: its last list price


def prices_over(ctx, key, lo, hi, route="maker-api", currency=None, config=None):
    """(distinct class vectors of the prices in the cost's currency that could have applied over [lo, hi], fully
    covered?). A promotion is a price charged over its interval, so it is one of the prices the source may have applied
    (never a base: base_price reads standard records only; coordinator, 26 Oct)."""
    promos = [p for p in ctx.prices["prices"] if p["model"] == key and p["route"] == route and p["kind"] == "promotion"
              and (currency is None or p["currency"] == currency) and for_config(p, config)]
    es = sorted((p for p in std_entries(ctx, key, route, currency, config) + promos if overlaps(p, lo, hi)),
                key=lambda p: V.when(p["from"]))
    if lo is None:
        return [e["classes"] for e in es], False
    cur, covered = lo, True
    for e in es:
        if V.when(e["from"]) > cur + dt.timedelta(microseconds=1):
            covered = False
            break
        cur = max(cur, V.when(e["to"], True))
    covered = covered and bool(es) and cur >= hi
    vecs = []
    for e in es:
        c = price_vector(e)
        if c not in vecs:
            vecs.append(c)
    return vecs, covered


def price_vector(e):
    """Class prices of an entry, its long-context tiers as 'lc><threshold>:<class>'."""
    c = {k: v for k, v in (e.get("classes") or {}).items() if v is not None}
    for t in e.get("long_context", []):
        for k, v in t["classes"].items():
            if v is not None:
                c[f"lc>{t['threshold_input_tokens']}:{k}"] = v
    return c


def tiered(vec):
    return {k for k in vec if k.startswith("lc>")}


def effective_classes(vec, tok):
    """The class prices the run's calls paid under a vector with long-context tiers (per-request thresholds): every
    call at or below the lowest threshold → the standard prices; a single call above → that tier. → (classes, why)."""
    th = sorted({int(k[3:].split(":")[0]) for k in tiered(vec)})
    std = {k: v for k, v in vec.items() if not k.startswith("lc>")}
    if not th:
        return std, ""
    req, per = tok.get("requests"), tok.get("tokens-in-per-request")
    if req is None or per is None:
        return None, "long-context tiers: requests and per-call sizes not stated"
    per, req = float(per[0]), float(req[0])
    if per <= th[0]:
        return std, ""
    if req == 1:
        t = max(x for x in th if x < per)
        return dict(std, **{k.split(":", 1)[1]: v for k, v in vec.items() if k.startswith(f"lc>{t}:")}), ""
    return None, "long-context tiers: calls on both sides of a threshold cannot be split"


def uniform_ratio(new, old):
    if tiered(new) != tiered(old):
        return None
    ks = [k for k in new if new.get(k) is not None and old.get(k) is not None]
    if not ks or any(old[k] == 0 for k in ks):
        return None
    rs = [new[k] / old[k] for k in ks]
    return rs[0] if max(rs) - min(rs) <= 1e-9 * max(abs(rs[0]), 1) else None


def class_ratios(new, old):
    """The per-class price ratios new/old over the classes both price, or None."""
    ks = [k for k in new if new.get(k) is not None and old.get(k) is not None]
    if not ks or any(old[k] == 0 for k in ks):
        return None
    return [new[k] / old[k] for k in ks]


def price_band(M, ref):
    """An unrepriced cost whose price vectors differ from ref in some classes only: its cost at ref lies in
    [raw × min ratio, raw × max ratio] over its own vectors; value = the middle, sd += the band's uniform sd."""
    C = M.fields["cost"]
    rs = [r for v in C.get("price_vectors", []) for r in class_ratios(ref, v)]
    lo, hi = min(rs), max(rs)
    if hi - lo <= 1e-12:
        return
    raw = float(C["number"])
    a, b = raw * lo, raw * hi
    sd0 = float(C.get("prec") or 0.0)
    C["band"] = dict(lo=a, hi=b, ratios=[lo, hi])
    C["number"] = Decimal(repr((a + b) / 2))
    C["prec"] = math.sqrt(sd0 * sd0 + ((b - a) / math.sqrt(12)) ** 2)
    M.flags.append("cost-price-band")
    M.rule("cost-price-band")


def count_rel_rounding(p):
    d, step = p
    return float(step) / float(d) if d else 0.0


def reprice(M, C, key):
    """§5.3 step 1: the cost at the base price, METHODOLOGY's order. Sets C['base'] (value, prec, rule) or None and
    C['price_vectors'] (what could have applied) for the comparability step."""
    ctx = M.ctx
    lo, hi, _ = run_interval(M, key)
    pub = (M.S.doc.get("published") or {}).get("value")
    pub_hi = day_bounds(pub)[1] if pub else hi
    if C["basis"] in ("billed", "router-billed"):
        pd_lo, pd_hi, how = lo, hi, "run date (billed spend)"
    elif C.get("method") == "publisher-table":
        caps = [day_bounds(M.S.captures[c]["captured"]) for c in M.m["facts"].get("value_seen_in", [])
                if c in M.S.captures]
        if caps:
            pd_lo, pd_hi, how = min(c[0] for c in caps), max(c[1] for c in caps), "capture date (recomputed at its price)"
        else:
            pd_lo, pd_hi = day_bounds(M.S.doc["harvested_at"])
            how = "harvest date (recomputed at its price)"
    elif C.get("price_table_date"):
        pd_lo, pd_hi = C["price_table_date"]
        how = "stated price date"
    else:
        pd_lo, pd_hi, how = lo, pub_hi, "[run lower bound, publication]"
    C["price_date"] = dict(lo=pd_lo.isoformat() if pd_lo else None, hi=pd_hi.isoformat(), how=how)
    C["base"] = None
    cur = C.get("currency")
    cfg = (M.fields.get("configuration") or {}).get("value")
    bp = base_price(ctx, key, cur, cfg)
    route = "maker-api"
    if pd_lo is None:                                    # an early-access run: list prices start at the release
        pd_lo = ctx.released(key)
        C["price_date"]["lo"] = pd_lo.isoformat()
        C["price_date"]["how"] += " (early access: from the release)"
    if pd_lo > pd_hi:
        pd_lo = pd_hi
    vecs, covered = prices_over(ctx, key, pd_lo, pd_hi, route, cur, cfg) if cur else ([], False)
    C["price_vectors"], C["price_covered"] = vecs, covered
    tiers = sorted({x.term for x in M.slot("spend", "price-tier") if x.level in ACCEPTED and x.term})
    if tiers:                                            # a Flex / batch cost → standard by its proven uniform factor
        tier_entries = [p for p in ctx.prices["prices"] if p["model"] == key and p["route"] == route
                        and p["kind"] == tiers[0] and p["currency"] == cur and overlaps(p, pd_lo, pd_hi)
                        and for_config(p, cfg)]
        stds = [p for p in std_entries(ctx, key, route, cur, cfg) if overlaps(p, pd_lo, pd_hi)]
        factors = []
        for tp in tier_entries:
            if tp.get("factor"):
                factors.append(float(tp["factor"]))
                continue
            for sp in stds:
                if overlaps(sp, V.when(tp["from"]), V.when(tp["to"], True)):
                    factors.append(uniform_ratio(price_vector(tp), price_vector(sp)))
        if len(tiers) > 1 or not factors or None in factors or max(factors) - min(factors) > 1e-9 * max(factors):
            C["tier_unproven"] = (f"{'/'.join(tiers)} tier: no proven uniform factor to the standard price over the "
                                  f"price date")
            return
        C["tier"] = dict(kind=tiers[0], factor=factors[0])
        C["std_cost"] = float(C["number"]) / factors[0]
        M.rule("cost-tier-factor")
    if bp is None:
        C["reprice_detail"] = f"no base price for {key} in {cur or 'an unstated currency'}"
        return
    if bp.get("_scheduled_list"):
        M.flags.append("base-scheduled-list-price")
        C["base_price"] = f"list price stated after the promotion (from {bp['from']}): no standard price in force on as_of"
    if bp.get("_last_list"):
        M.flags.append("base-last-list-price")
        C["base_price"] = f"last list price ({bp['from']} → {bp['to']}): no maker-API price in force on as_of"
    base = price_vector(bp)
    k_tier = (C.get("tier") or {}).get("factor", 1.0)
    cost, prec = C.get("std_cost", float(C["number"])), (C.get("prec") / k_tier if C.get("prec") is not None else None)
    if not covered or not vecs:
        C["reprice_detail"] = "prices over the price date not registered"
        return class_ratio(M, C, key, pd_hi)
    # 1. the publisher's own figure at the base price
    if all(v == base for v in vecs):
        M.rule("cost-publisher-figure")
        C["base"] = dict(value=cost, prec=prec, rule="cost-publisher-figure")
        return
    # 2. the price change on the source's own tokens, once its formula reproduces the cost
    tok = C.get("tokens", {})
    if tiered(base) or any(tiered(v) for v in vecs):
        eff_base, why = effective_classes(base, tok)
        eff_old = [effective_classes(v, tok) for v in vecs]
        why = why or next((w for _, w in eff_old if w), "")
        if why:
            C["reprice_detail"] = why + ": not re-priceable"
            return
        base, vecs = eff_base, [c for c, _ in eff_old]
        C["long_context"] = "tiers resolved from requests and per-call sizes"
    classes = {k: v for k, v in tok.items() if k in base}
    usage_unit_ok = not C.get("usage_unit") or not C.get("unit") or C["usage_unit"] == C["unit"]
    if len(vecs) == 1 and classes and usage_unit_ok:
        old = vecs[0]
        ri = C.get("reasoning_included")                 # True: inside output; False: added to it; None: both tried
        variants = [False] if ri is True or "tokens-reasoning" not in tok else [True] if ri is False else [False, True]
        for add_reasoning in variants:
            t = {k: float(v[0]) for k, v in classes.items()}
            if add_reasoning:
                t["output"] = t.get("output", 0.0) + float(tok["tokens-reasoning"][0])
            if any(old.get(k) is None for k in t):
                break
            computed = sum(t[k] * old[k] for k in t) / 1e6
            rel = max([count_rel_rounding(v) for v in classes.values()] + [0.0])
            tol = float(C["step"]) + rel * computed
            if abs(computed - cost) <= tol:
                if any(base.get(k) is None for k in t):
                    break
                new = cost + sum(t[k] * (base[k] - old[k]) for k in t) / 1e6
                M.rule("cost-delta-on-source")
                C["base"] = dict(value=new, prec=prec, rule="cost-delta-on-source",
                                 detail=f"formula reproduces {cost} as {computed:.6g}"
                                        + (" (reasoning added to output)" if add_reasoning else ""))
                return
    # 3. a uniform factor
    ks = [uniform_ratio(base, v) for v in vecs]
    if all(k is not None for k in ks) and max(ks) - min(ks) <= 1e-9 * max(ks):
        M.rule("cost-uniform-factor")
        C["base"] = dict(value=cost * ks[0], prec=prec * ks[0] if prec is not None else None,
                         rule="cost-uniform-factor", detail=f"factor {ks[0]:.6g}")
        return
    return class_ratio(M, C, key, pd_hi)


def class_ratio(M, C, key, pd_hi):
    """4. the class-median ratio (METHODOLOGY §2), from the optional registry file class-ratios.json."""
    for e in M.ctx.class_ratios.get("ratios", []):
        if e.get("model") != key or not pd_hi < V.when(e["change"]):
            continue
        cls = e.get("measures", {}).get(M.ref) or e.get("setups", {}).get(M.setup_id)
        if not cls or cls not in e.get("classes", {}):
            continue
        k, sd = e["classes"][cls]["factor"], e["classes"][cls]["sd"]
        cost, prec = C.get("std_cost", float(C["number"])), C.get("prec") or 0.0
        M.rule("cost-class-ratio")
        C["base"] = dict(value=cost * k, prec=math.hypot(prec * k, cost * k * sd), rule="cost-class-ratio",
                         detail=f"class {cls}: factor {k}, spread {sd}")
        return
    return


# ---------------------------------------------------------------- statuses
def decision_for(ctx, M, axis):
    for d in ctx.decisions:
        if d.get("kind") == "headline" or M.ref not in d["measures"]:
            continue
        if d["axis"] not in (axis, "both"):
            continue
        entries = []
        for mref in d["measures"]:
            sid, mid = mref.split("#")
            m = ctx.mvalid.get((sid, mid))
            if m is None:
                entries = None
                break
            entries.append(V.facts_hash(ctx.sources[sid].doc, m, mref))
        if entries is None or V.hash_of(entries) != d["facts_hash"]:
            if d["id"] not in [s["id"] for s in ctx.stale]:
                ctx.stale.append(dict(id=d["id"], measures=d["measures"], axis=d["axis"],
                                      why="facts_hash no longer matches"))
            M.flags.append(f"stale-decision:{d['id']}")
            continue
        return f"{d['status']}:decision:{d['id']}", d["reason"]
    return None


def headline_metric(ctx, M):
    h = M.setup.get("headline", {})
    pub_dec = [d for d in ctx.decisions if d.get("kind") == "headline" and d["setup"] == M.setup_id
               and d.get("publisher") == M.publisher]
    if pub_dec:
        return pub_dec[0]["metric"], pub_dec[0]["id"]
    if h.get("basis") == "decision":
        d = [x for x in ctx.decisions if x.get("kind") == "headline" and x["id"] == h.get("decision")
             and not x.get("publisher")]
        return (d[0]["metric"], d[0]["id"]) if d else (None, None)
    return h.get("metric"), None


PARTIAL_SCORED = re.compile(r"(scored|counted|graded) as (wrong|incorrect|fail(ed|ures?)?)|as failures", re.I)


def value_step(M, field, axis):
    """§5.2 step 4 (and the cost axis' value): → reason or None."""
    if field is None:
        return None
    lv = field.get("level")
    if lv == "source-estimate":
        return "out:estimate"
    failures = []
    for a in M.slot("anomalies"):
        s = a.says[0]
        if a.level == "not-established:assumed":
            return "out:anomaly-assumed"
        if a.level == "not-established:contradictory":
            return "out:contradictory"
        if a.level not in ACCEPTED:
            continue
        if s == "failure":
            failures.append(a)
            continue
        if s == "partial" and not PARTIAL_SCORED.search((a.value or "") + " " + (a.quote or "")):
            return "out:partial"
        if s == "cap":
            M.flags.append("cap")
    if lv == "not-established:contradictory" or field.get("currency") == "contradictory" \
            or field.get("unit") == "contradictory":
        return "out:contradictory"
    if lv not in ACCEPTED:
        return "out:value-not-established"
    if failures:
        why = mean_of_runs(M, failures) if axis == "quality" else "mean-of-runs recomputes scores only"
        if why:
            field["detail"] = f"failed run: {why}"
            return "out:failed-run"
    return None


def early_steps(M, axis, field):
    """Steps 0–4 (both axes) and 5 (quality): → (reason, detail) or (None, '')."""
    ctx = M.ctx
    d = decision_for(ctx, M, axis)
    if d:
        return d
    faults = M.axis_faults(axis)
    if faults:
        return "out:no-proof", "; ".join(faults)
    mf = M.fields["model"]
    if not mf.get("value") or mf.get("level") not in ACCEPTED:
        return "out:model-not-established", mf.get("detail", "")
    key = mf["value"]
    rd = (M.fields.get("run_date_detail") or {}).get(key, {})
    if rd.get("level") == "not-established:contradictory":
        lo, hi = V.when(rd["lo"]) if rd.get("lo") else MIN, V.when(rd["hi"])
        ev = [t for t in model_events(ctx, key) if lo < t < hi]
        if ev:
            return "out:contradictory", (f"run date contradictory, and a dated event of {key} falls inside its "
                                         f"window ({min(ev).date()})")
    cf = M.fields.get("configuration", {})
    c = cf.get("value")
    offered = {x: {"id": x} for x in M.fields.get("configurations_offered", [])}
    key = mf["value"]
    if not c or cf.get("level") not in ACCEPTED or c in NOT_ESTABLISHED or c.startswith(("scalar-", "req-", "app-")):
        return "out:effort-not-established", f"{c or ''} {cf.get('level')}: {cf.get('detail', '')}".strip()
    iv = run_interval(M, key)
    if not in_list(c, ctx.configs(key, iv)):
        return "out:effort-not-established", f"{c} is not in the model's list {sorted(offered)}"
    if re.fullmatch(r"think-[0-9]+", c):
        return "out:budget-config", f"{c}: thinking budgets are recorded, not fitted"
    term = ctx_vocab_terms(ctx, "configuration").get(c) or {}
    if term.get("in_fit") is False:                      # a configuration recorded, not fitted (between-tools)
        return term.get("reason", "out:effort-not-established"), (f"{c}: a configuration recorded, not fitted (vocab "
                                                                  f"x-terms in_fit false; not in lqm.EFFORTS)")
    r = value_step(M, field, axis)
    if r:
        return r, field.get("detail", "") if field else ""
    if axis == "quality":
        hm, did = headline_metric(ctx, M)
        if hm is None or M.setup.get("metric") != hm:
            return "out:not-headline", (f"setup metric {M.setup.get('metric')!r}, headline "
                                        f"{hm!r}" if hm else "headline pending a decision")
    return None, ""


def model_events(ctx, key):
    """Datetimes where something dated about the model changes: its records in models.json, its route entries,
    its prices."""
    docs = [ctx.models[key]] + [r.get("models", {}).get(key, {}) for r in ctx.routes.values()] + \
        [p for p in ctx.prices["prices"] if p["model"] == key]
    out = set()
    for d in docs:
        for _, _, rec in V.walk_intervals(d):
            out.add(V.when(rec["from"]))
            if rec.get("to") is not None:
                out.add(V.when(rec["to"], True))
        if "from" in d and "to" in d:
            out.add(V.when(d["from"]))
            if d.get("to") is not None:
                out.add(V.when(d["to"], True))
    return sorted(t for t in out if MIN < t < MAX)


def couple(M):
    return f"{M.fields['model']['value']}@{M.fields['configuration']['value']}"


# ---------------------------------------------------------------- legacy measures (migration, §8.1)
LEGACY_EFFORTS = {"nothink", "minimal", "low", "medium", "high", "xhigh", "max", "think", "solo"}   # lqm.EFFORTS (acceptance checks the copy)


class LegacyMeasure:
    """A row of today's raw-data.csv carried as it is: today's status (lqm.load's own admission), none of the tree's
    steps, no repricing, no replacement; written to the fit tables verbatim."""
    kind = "legacy"

    def __init__(self, ctx, S, m, mfaults):
        self.ctx, self.S, self.m = ctx, S, m
        self.ref = f"{S.id}#{m['id']}"
        self.setup_id = m["setup"]
        self.faults = list(S.faults) + list(mfaults)
        f, fault = S.fact(m["facts"]["legacy"][0])
        if fault:
            self.faults.append(fault)
        cols = S.doc["legacy"]["columns"]
        self.line = f.value if f else ""
        rec = next(csv.reader([self.line]), []) if f else []
        self.row = dict(zip(cols, rec)) if len(rec) == len(cols) else {c: "" for c in cols}
        m_ = re.search(r"\d+", (f.where if f else "") or "")
        self.order = int(m_.group()) if m_ else 0
        self.publisher = self.row.get("source", "")
        self.row_sha256 = hashlib.sha256(self.line.encode("utf-8")).hexdigest()
        self.status, self.detail = {}, {}
        fit = ctx.fit_set
        for axis, field in (("quality", "score"), ("cost", "cost_usd")):
            why = self.admission(field, fit)
            self.status[axis] = "legacy:in" if why is None else f"legacy:out:{why}"
            self.detail[axis] = "today's admission (lqm.load's filters)" if why is None else why

    def admission(self, field, fit):
        if self.faults:
            return "no-proof"
        r = self.row
        if not r.get("group"):
            return "no-group"
        if r["group"].startswith("#"):
            return "comment"
        if r.get("model") not in fit:
            return "model-not-in-fit-list"
        if r.get("effort") not in LEGACY_EFFORTS:
            return "effort-not-in-efforts"
        try:
            v = float(r.get(field))
        except (TypeError, ValueError):
            return "no-value"
        if field == "cost_usd" and v <= 0:
            return "no-value"
        return None


def tree_would_say(ctx, row):
    """Informative only: what flag-map.json and the vocabularies say this legacy row's configuration and cost method
    would be once its source is converted (never changes its status)."""
    fm = ctx.reg.get("flag-map") or {}
    eff = row.get("effort", "")
    ev = (fm.get("effort_values") or {}).get(eff)
    if ev:
        cfg = ev["to"]
    elif V.in_vocab(ctx.schemas, "configuration", eff):
        cfg = eff if eff not in ("solo",) else "re-read: solo only for a [solo] model"
    elif V.in_vocab(ctx.schemas, "configuration_not_established", eff):
        cfg = "not established"
    else:
        cfg = "re-read (no flag-map entry)"
    out = {"configuration": cfg}
    if (row.get("cost_usd") or "").strip():
        t = row.get("confound") or ""
        e = (fm.get("cost_method_by_source") or {}).get(row.get("source"))
        if e and e.get("groups") and row.get("group") not in e["groups"]:
            e = None
        m = e["method"] if e and e["applies"] == "all" else next((m for m, p in ctx.method_patterns if p.search(t)), None)
        m = m or (e["method"] if e else None)
        out["cost_method"] = m or "unmapped"
        out["cost_basis"] = ctx.vocab["$defs"]["cost_method"]["x-terms"][m]["basis"] if m else "unknown"
    return out


# ---------------------------------------------------------------- the build
def build(ctx):
    legacy = sorted((LegacyMeasure(ctx, S, m, mf) for S, m, mf in ctx.measures if m["facts"].get("legacy")),
                    key=lambda L: (L.order, L.ref))
    measures = [Measure(ctx, S, m, mf) for S, m, mf in ctx.measures if not m["facts"].get("legacy")]
    # a converted measure's legacy_ref replaces its legacy row (the source migrated, its legacy file kept or not)
    claimed = {(M.m["legacy_ref"]["line"], M.m["legacy_ref"]["row_sha256"]): M.ref for M in measures
               if M.m.get("legacy_ref")}
    for L in legacy:
        by = claimed.get((L.order, L.row_sha256))
        if by:
            for ax in ("quality", "cost"):
                L.status[ax], L.detail[ax] = "legacy:out:replaced", f"replaced by {by} (its legacy_ref)"
    for M in measures:
        key = resolve_model(M)
        if key:
            configuration(M, key)
            run_interval(M, key)
        else:
            M.fields["configuration"] = dict(value=None, level="not-established:absent", detail="model not established")
        score_field(M)
        cost_field(M)
        if key and M.fields.get("cost"):
            reproduce_cost(M, key)
        campaign_of(M)
    budgets_merge(measures)
    # campaigns inherited along snapshot_of
    for M in measures:
        M.campaign = inherited_campaign(M, measures)
    quality(ctx, measures)
    residuals = composite_residuals(ctx, measures)
    group_step(ctx, measures + residuals, "quality")
    cost(ctx, measures)
    return measures, residuals, legacy


def campaign_of(M):
    v = (M.slots.get("version") or [None])[0] or next(iter(M.slot("setup", "version")), None)
    M.version = norm_version(v.value) if v is not None and v.level in ACCEPTED else None


def version_key(v):
    """Natural order of versions: '9' < '10', '1.2' < '1.10'."""
    return [(0, int(p), "") if p.isdigit() else (1, 0, p) for p in re.split(r"[.\-_ ]+|(?<=\d)(?=\D)|(?<=\D)(?=\d)", v) if p]


def inherited_campaign(M, measures):
    if M.version:
        return M.version
    seen, S = set(), M.S
    while S.doc.get("snapshot_of") and S.doc["snapshot_of"] not in seen:
        seen.add(S.doc["snapshot_of"])
        prev = M.ctx.sources.get(S.doc["snapshot_of"])
        if prev is None:
            break
        vs = sorted({x.version for x in measures if x.S is prev and x.setup_id == M.setup_id and x.version},
                    key=version_key)
        if vs:
            return vs[-1]
        S = prev
    return ""


def gkey(M):
    return (M.setup_id, M.publisher, M.campaign)


def quality(ctx, measures):
    pending = []
    for M in measures:
        f = M.fields.get("score")
        if f is None and M.value is None and M.m["facts"].get("value") and M.axis_faults("quality"):
            M.status["quality"], M.detail["quality"] = "out:no-proof", "; ".join(M.axis_faults("quality"))
            continue
        if f is None:
            M.status["quality"] = None
            M.detail["quality"] = "no score (cost-only measure)"
            continue
        r, d = early_steps(M, "quality", f)
        if r:
            M.status["quality"], M.detail["quality"] = r, d
        else:
            pending.append(M)
    # 6. uninformative: a score at the floor or the ceiling while the others are not
    by_group = collections.defaultdict(list)
    for M in pending:
        by_group[gkey(M)].append(M)
    for g, ms in by_group.items():
        b = ms[0].setup.get("bounds") or [None, None]
        at = [M for M in ms if M.fields["score"]["number"] is not None and
              any(x is not None and Decimal(str(x)) == M.fields["score"]["number"] for x in b)]
        if at and len(at) < len(ms):
            for M in at:
                M.status["quality"] = "out:uninformative"
                M.detail["quality"] = f"score {num_text(M.fields['score']['number'])} at a bound of {b}; cost kept"
                M.rule("uninformative-scores")
    # 7. campaign: an earlier value of a couple replaced within its campaign; same-runs-as
    candidates = [M for M in pending]
    supersede(ctx, candidates, "quality")
    same_runs(ctx, measures, candidates)


def source_order(M):
    return (M.S.date(), M.S.doc["harvested_at"], M.S.id)


def supersede(ctx, ms, axis):
    by = collections.defaultdict(list)
    for M in ms:
        by[(gkey(M), couple(M))].append(M)
    for k, xs in by.items():
        srcs = sorted({M.S.id for M in xs}, key=lambda s: source_order(next(M for M in xs if M.S.id == s)))
        if len(srcs) < 2:
            continue
        latest = srcs[-1]
        new = [M for M in xs if M.S.id == latest]
        for M in xs:
            if M.S.id != latest and M.status[axis] is None:
                M.status[axis] = "out:superseded"
                M.detail[axis] = f"replaced within campaign {M.campaign or '(one campaign)'} by {new[0].ref}"
                if axis == "quality":
                    v = M.fields["score"]["text"]
                    for N in new:
                        N.flags.append(f"prev={v} ({M.ref})")


def close(v1, d1, s1, v2, d2, s2):
    return abs(v1 - v2) <= 2 * math.hypot(d1 or 0.0, d2 or 0.0) + s1 + s2


def family(ctx, M):
    return M.setup.get("family")


def same_runs(ctx, measures, candidates):
    """same-runs-as, stated (a fact naming the other document) or proven (identical costs on ≥ 2 shared couples, a
    score differing): the later grading replaces the earlier; the cost counts once."""
    links = []
    for M in measures:
        for f in M.slot("same_runs_as"):
            if f.level not in ACCEPTED:
                continue
            other = next((S for S in ctx.sources.values() if S.id != M.S.id and
                          (f.value.strip() == S.id or f.value.strip() in S.doc.get("urls", []))), None)
            if other and (M.S, other) not in links and (other, M.S) not in links:
                links.append((M.S, other))
    ok = [M for M in measures if M.fields["model"].get("value") and M.fields.get("cost", {}) and
          M.fields["cost"].get("number") is not None and M.fields["cost"].get("level") in ACCEPTED]
    by_fam = collections.defaultdict(lambda: collections.defaultdict(dict))
    for M in ok:
        if M.fields["configuration"].get("level") in ACCEPTED:
            by_fam[family(ctx, M)][M.S.id][couple(M)] = M
    for fam, per in by_fam.items():
        ids = sorted(per)
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                shared = sorted(set(per[a]) & set(per[b]))
                if len(shared) < 2:
                    continue
                pairs = [(per[a][c], per[b][c]) for c in shared]
                if not all(x.fields["cost"]["unit"] == y.fields["cost"]["unit"] and
                           x.fields["cost"]["currency"] == y.fields["cost"]["currency"] and
                           close(float(x.fields["cost"]["number"]), x.fields["cost"]["prec"],
                                 float(x.fields["cost"]["step"]), float(y.fields["cost"]["number"]),
                                 y.fields["cost"]["prec"], float(y.fields["cost"]["step"])) for x, y in pairs):
                    continue
                differs = any(x.fields.get("score") and y.fields.get("score") and
                              x.fields["score"].get("number") is not None and y.fields["score"].get("number") is not None
                              and not close(float(x.fields["score"]["number"]), x.fields["score"]["prec"],
                                            float(x.fields["score"]["step"]), float(y.fields["score"]["number"]),
                                            y.fields["score"]["prec"], float(y.fields["score"]["step"]))
                              for x, y in pairs)
                if differs:
                    Sa, Sb = ctx.sources[a], ctx.sources[b]
                    if (Sa, Sb) not in links and (Sb, Sa) not in links:
                        links.append((Sa, Sb))
    for S1, S2 in links:
        later, earlier = sorted((S1, S2), key=lambda S: (S.date(), S.doc["harvested_at"], S.id), reverse=True)
        # only a later measure accepted so far replaces (a refused regrade leaves the earlier grading in)
        lat = {(family(ctx, M), couple(M)): M for M in measures if M.S is later and M in candidates
               and M.status["quality"] is None and M.fields["model"].get("value")
               and M.fields["configuration"].get("value")}
        for M in measures:
            if M.S is not earlier or not M.fields["model"].get("value") or not M.fields["configuration"].get("value"):
                continue
            N = lat.get((family(ctx, M), couple(M)))
            if N is None:
                continue
            M.rules.add("same-runs-as")
            if M.status["quality"] is None and M in candidates:
                M.status["quality"] = "out:superseded"
                M.detail["quality"] = f"same runs as {later.id}: the later grading ({N.ref}) replaces it"
            nc = N.fields.get("cost") or {}
            if nc.get("number") is not None and nc.get("level") in ACCEPTED:
                M.cost_counted_by = N                    # applied only if N's cost is accepted (cost steps 0–4)


def composite_residuals(ctx, measures):
    """§5.2 step 8, phase 1: the build computes the residual of a linear composite for the missing components (the
    composite row itself is dropped by lqm.load's composites rule)."""
    out = []
    inq = [M for M in measures if M.status["quality"] is None]
    by = collections.defaultdict(dict)
    for M in inq:
        by[(M.setup_id, M.publisher, couple(M))][M.S.id] = M
    for M in inq:
        comp = M.setup.get("composite")
        if not comp or comp.get("linear") is not True \
                or comp.get("formula", {}).get("normalisation") not in (None, "", "none"):
            continue                                     # linear false or "unknown": no residual
        w = comp["formula"]["weights"]
        tot = sum(w.values())
        if not tot:
            continue
        names = V.component_names(comp)                  # (weight key, setup id or None: never present)
        present = {n: by[(c, M.publisher, couple(M))] for n, c in names
                   if c is not None and by.get((c, M.publisher, couple(M)))}
        missing = [n for n, _ in names if n not in present]
        if not present or not missing:
            continue
        val = float(M.fields["score"]["number"])
        prec = (M.fields["score"]["prec"] or 0.0) ** 2
        top = (M.setup.get("bounds") or [None, None])[1]
        ok = True
        for c, ms in present.items():
            x = sorted(ms.values(), key=source_order)[-1]
            ctop = (x.setup.get("bounds") or [None, None])[1]
            k = 1.0 if ctop == top else (top / ctop if top in (1, 100) and ctop in (1, 100) else None)
            if k is None:                                # a component on another, unconvertible scale: no residual
                ok = False
                break
            val -= w.get(c, 0) / tot * float(x.fields["score"]["number"]) * k
            prec += (w.get(c, 0) / tot * (x.fields["score"]["prec"] or 0.0) * k) ** 2
        if not ok:
            M.flags.append("composite-residual-refused:scale")
            continue
        wm = sum(w.get(c, 0) for c in missing) / tot
        if wm <= 0:
            continue
        R = Residual(M, missing, val / wm, math.sqrt(prec) / wm)
        out.append(R)
    return out


class Residual:
    """A composite residual row (computed): setup = composite × missing set; its campaign is the composite's capture."""
    def __init__(self, M, missing, value, prec):
        self.ctx, self.S, self.base = M.ctx, M.S, M
        self.ref = f"{M.ref}~resid"
        self.setup_id = f"{M.setup_id}-resid-{'+'.join(sorted(missing))}"
        self.setup = dict(M.setup, composite=None)
        self.publisher = M.publisher
        self.campaign = f"{M.campaign}@{M.S.id}"
        self.fields = dict(M.fields)
        d = Decimal(repr(value))
        self.fields["score"] = dict(text=num_text(d), number=d, step=M.fields["score"]["step"], prec=prec,
                                    level="computed", rules=["composite-residual"], facts=M.fields["score"]["facts"])
        self.fields["cost"] = None
        self.status = {"quality": None, "cost": None}
        self.detail = {"quality": f"residual of {M.ref} for {sorted(missing)}", "cost": "no cost on a residual"}
        self.rules = {"composite-residual", "composite-residual-rule"}
        self.flags = list(M.flags)
        self.used = list(M.used)
        self.faults = []
        self.slots = M.slots
        self.m = M.m
        self.value = M.value
        self.version = None


def group_step(ctx, ms, axis):
    """§5.2 step 10: a group (setup × publisher × campaign; on the cost axis × cost subset) with ≥ 2 accepted couples
    of models in the fit's model list → in; else out:single-couple (cost: out:cost-single-couple)."""
    fit = set(ctx.fit_models)
    by = collections.defaultdict(list)
    for M in ms:
        st = M.status[axis]
        if st is None or st.startswith("in:decision"):
            if axis == "quality" and M.fields.get("score") is None:
                continue
            k = gkey(M) if axis == "quality" else (gkey(M), M.cost_subset)
            by[k].append(M)
    for k, xs in by.items():
        couples = {couple(M) for M in xs if M.fields["model"]["value"] in fit}
        for M in xs:
            if M.status[axis] is not None:
                continue
            if len(couples) >= 2 and M.fields["model"]["value"] in fit:
                M.status[axis] = "in"
            else:
                M.status[axis] = "out:single-couple" if axis == "quality" else "out:cost-single-couple"
                M.detail[axis] = f"{len(couples)} accepted couple(s) of fit models in the group" + (
                    "" if M.fields["model"]["value"] in fit else "; model not in the fit's model list")


def cost(ctx, measures):
    """§5.3: one cost measure per set of spend facts (on the headline measure's setup, else the first)."""
    groups = collections.defaultdict(list)
    for M in measures:
        M.cost_subset = None
        M.cost_carrier = None
        C = M.fields.get("cost")
        if not C and not isinstance(M, Residual) and M.m["facts"].get("spend") and M.axis_faults("cost"):
            M.status["cost"], M.detail["cost"] = "out:no-proof", "; ".join(M.axis_faults("cost"))
            continue
        if not C:
            M.status["cost"] = None
            M.detail["cost"] = "no cost"
            continue
        groups[(M.S.id, tuple(C["facts"]))].append(M)
    carriers = []
    for k, ms in groups.items():
        head = [M for M in ms if headline_metric(ctx, M)[0] == M.setup.get("metric")]
        car = (head or ms)[0]
        carriers.append(car)
        for M in ms:
            if M is not car:
                M.cost_carrier = car.ref
    pending = []
    for M in carriers:
        r, d = early_steps(M, "cost", M.fields["cost"])
        if r:
            M.status["cost"], M.detail["cost"] = r, d
        else:
            pending.append(M)
    supersede(ctx, pending, "cost")
    for M in pending:
        N = getattr(M, "cost_counted_by", None)
        if N is not None and M.status["cost"] is None and N in pending and N.status["cost"] is None:
            M.status["cost"] = "out:superseded"
            M.detail["cost"] = f"same runs as {N.ref}: the cost counts once"
    live = [M for M in pending if M.status["cost"] is None]
    # 1. base-price value; 2. partition; 3. subsets
    for M in live:
        C = M.fields["cost"]
        key = M.fields["model"]["value"]
        if C["basis"] == "subscription":
            M.status["cost"], M.detail["cost"] = "out:cost-basis", "subscription: no per-run price"
            continue
        if C.get("currency") is None:
            C["currency_note"] = "currency not stated"
        reprice(M, C, key)
        if C.get("tier_unproven"):
            M.status["cost"], M.detail["cost"] = "out:cost-not-comparable", C["tier_unproven"]
            continue
        method = C.get("method")
        if not method:
            if ctx.settings["cost_method_unstated"] == "out":
                M.status["cost"] = "out:cost-not-comparable"
                M.detail["cost"] = "no cost-method fact (setting cost_method_unstated = out)"
                continue
            method = f"unstated[{M.S.id}/{C['scope']}]"
            M.flags.append("cost-method-assumed-single")
        cand = [c for c, _ in chains(M, key)]
        rkey = "/".join(cand[0]) if len(cand) == 1 else "unknown"
        C["part"] = (C["basis"], method, C.get("unit") or "", C.get("currency") or "?", rkey)
    parts = collections.defaultdict(list)
    for M in live:
        if M.status["cost"] is None:
            parts[(gkey(M), M.fields["cost"]["part"])].append(M)
    for (g, part), ms in parts.items():
        rep = [M for M in ms if M.fields["cost"].get("base")]
        for M in rep:
            M.cost_subset = (part, "repriced")
        by_model = collections.defaultdict(list)
        for M in ms:
            if not M.fields["cost"].get("base"):
                by_model[M.fields["model"]["value"]].append(M)
        for key, xs in by_model.items():
            vecs, ok = [], True
            for M in xs:
                C = M.fields["cost"]
                if not C.get("price_covered"):
                    ok = False
                for v in C.get("price_vectors", []):
                    if v not in vecs:
                        vecs.append(v)
            uniform = ok and vecs and all(uniform_ratio(v, vecs[0]) is not None for v in vecs)
            # a price change that is not uniform (one class changed, e.g. Sonnet 5.5's cache read on 7 Oct): the true
            # cost at the latest vector lies between raw/max and raw/min of the per-class ratios; the row keeps the
            # middle with that band as its uncertainty (the maintainer, 29 Oct: "la marge d'erreur")
            band = ok and vecs and not uniform and all(tiered(v) == tiered(vecs[-1]) for v in vecs) \
                and all(class_ratios(v, vecs[-1]) for v in vecs)
            for M in xs:
                if uniform or band:
                    M.cost_subset = (part, f"model:{key}")
                    M.flags.append("cost-unrepriced")
                    M.rule("cost-comparability-rule")
                    if band:
                        price_band(M, vecs[-1])
                else:
                    M.status["cost"] = "out:cost-not-comparable"
                    M.detail["cost"] = ("unrepriced, and the price change over the price date is not uniform"
                                        if ok and vecs else "unrepriced, and no registered price covers its price date: "
                                        + M.fields["cost"].get("reprice_detail", ""))
                    M.rule("cost-comparability-rule")
    group_step(ctx, carriers, "cost")
    for M in measures:
        if M.cost_carrier:
            car = next(x for x in measures if x.ref == M.cost_carrier)
            M.status["cost"] = car.status["cost"]
            M.detail["cost"] = f"one cost measure with {car.ref} (same spend facts)"


# ---------------------------------------------------------------- outputs
def group_names(ctx, ms):
    """Fit group names: the setup id (today's group name), + '@<publisher>' when the setup has several publishers in
    this build, + '#<campaign>' when it has several campaigns; cost groups + '~c<n>' when a quality group has several
    cost subsets."""
    pubs, camps = collections.defaultdict(set), collections.defaultdict(set)
    for M in ms:
        pubs[M.setup_id].add(M.publisher)
        camps[(M.setup_id, M.publisher)].add(M.campaign)
    names = {}
    for M in ms:
        n = M.setup_id
        if len(pubs[M.setup_id]) > 1:
            n += f"@{M.publisher}"
        if len(camps[(M.setup_id, M.publisher)]) > 1:
            n += f"#{M.campaign or 'none'}"
        names[gkey(M)] = n
    subsets = collections.defaultdict(set)
    for M in ms:
        if getattr(M, "cost_subset", None):
            subsets[gkey(M)].add(M.cost_subset)
    cnames = {}
    for g, ss in subsets.items():
        for i, s in enumerate(sorted(ss, key=lambda s: json.dumps(s, default=str)), 1):
            cnames[(g, s)] = names[g] + (f"~c{i}" if len(ss) > 1 else "")
    return names, cnames


def base_group(ctx, M):
    lg = (ctx.setups.get(M.setup_id) or {}).get("legacy_groups") or []
    if isinstance(M, Residual):
        return M.setup_id
    return lg[0] if lg else M.setup_id


def confound(ctx, M):
    flags = []
    key = M.fields["model"].get("value")
    iv = M.__dict__.get("_iv", {}).get(key) if not isinstance(M, Residual) else M.base.__dict__.get("_iv", {}).get(key)
    if iv and iv[2]:
        flags.append("EAP-run")
    org = ctx.maker_org(key) if key else "~"
    makers = ctx.vocab["$defs"]["maker"]["x-terms"]
    spellings = {rec["org"]: [rec["org"]] + rec.get("display_prefixes", []) for rec in makers.values() if rec["org"] != "~"}

    def names_org(text):
        t = (text or "").casefold()
        for o, sp in spellings.items():
            if any(re.search(r"\b" + re.escape(s.casefold()) + r"\b", t) for s in sp):
                return o
        return None
    for f in M.slots.get("restated_from", []):
        if f.level in ACCEPTED:
            o = names_org(f.value)
            if o is None and org != "~" and re.search(r"self[- ]reported|providers?'? (own )?(reported|numbers)|as reported by (the )?(provider|vendor|maker)s?",
                                                     f.value or "", re.I):
                o = org                                  # "providers' self reported numbers": the model's own maker (27 Oct)
            flags.append(f"restated-from:{o}" if o else f"restated-from:{f.value}")
    for f in M.slots.get("evaluated_by", []):
        if f.level in ACCEPTED:
            o = names_org(f.value)
            flags.append(f"vendor-reported:{o}" if o and o == org else f"evaluated-by:{f.value}")
    flags += M.flags
    if not isinstance(M, Residual):
        C = M.fields.get("cost") or {}
        if C.get("base"):
            flags.append(f"cost-base-price:{C['base']['rule']}")
    return "; ".join(dict.fromkeys(flags))


def row_of(ctx, M, names, cnames, axis_cost=False):
    S = M.S
    key = M.fields["model"].get("value")
    cfg = M.fields.get("configuration", {})
    sf = M.fields.get("score") or {}
    C = M.fields.get("cost") or {}
    tok = C.get("tokens") or {}
    g = names.get(gkey(M), M.setup_id)
    if axis_cost:
        g = cnames.get((gkey(M), M.cost_subset), g)
    cost_val, cost_prec = "", ""
    if C.get("number") is not None and C.get("level") in ACCEPTED:
        if axis_cost and C.get("base") and (C["base"]["rule"] != "cost-publisher-figure" or C.get("std_cost")):
            cost_val, cost_prec = fmt_like(C["base"]["value"], num_text(C["number"])), fmt_prec(C["base"]["prec"])
        elif axis_cost and C.get("std_cost") is not None:     # a tier cost, unrepriced: at standard all the same
            cost_val = fmt_like(C["std_cost"], num_text(C["number"]))
            cost_prec = fmt_prec(C["prec"] / C["tier"]["factor"] if C.get("prec") is not None else None)
        else:                                            # the cost as the source wrote it
            cost_val, cost_prec = num_text(C["number"]), fmt_prec(C.get("prec"))
    score = num_text(sf["number"]) if sf.get("number") is not None and sf.get("level") in ACCEPTED else ""
    model_cell = key or "?" + ((M.slots.get("model") or [Fact(value="")])[0].value or "")
    cached = tok.get("cached-share")
    where = (M.value.where if M.value is not None else "")
    return dict(group=g, source=M.publisher, model=model_cell,
                effort=cfg.get("value") or cfg.get("level") or "unstated",
                task_type=M.setup.get("task_type", ""), complexity=M.setup.get("complexity", ""),
                harness=M.setup.get("harness") or "", unit=C.get("unit") or "",
                cost_usd=cost_val, cost_prec=cost_prec,
                tokens_in=num_text(tok["input"][0]) if "input" in tok else "",
                tokens_out=num_text(tok["output"][0]) if "output" in tok else "",
                score=score, score_metric=(M.value.term if M.value is not None and M.value.term and
                                           "score" in M.value.says else M.setup.get("metric", "")),
                score_prec=fmt_prec(sf.get("prec")) if score else "",
                cached_pct=num_text(cached[0]) if cached else "", confound=confound(ctx, M),
                ref=f"{(S.doc.get('urls') or [''])[0]} ({where})")


def write_csv(path, rows, columns):
    """Rows are dicts, or a legacy row's verbatim line (written as it is)."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        for r in rows:
            if isinstance(r, str):
                f.write(r + "\n")
            else:
                w.writerow({c: r.get(c, "") for c in columns})


def jsonable(x):
    if isinstance(x, Decimal):
        return num_text(x)
    if isinstance(x, (dt.datetime, dt.date)):
        return x.isoformat()
    if isinstance(x, tuple):
        return list(x)
    if isinstance(x, set):
        return sorted(x)
    raise TypeError(type(x))


def report_entry(ctx, M, names, cnames):
    f = {k: v for k, v in M.fields.items()}
    C = f.get("cost")
    if C:
        C = {k: v for k, v in C.items() if k not in ("price_vectors",)}
        C["price_vectors"] = M.fields["cost"].get("price_vectors")
        f["cost"] = C
    return dict(source=M.S.id, setup=M.setup_id, publisher=M.publisher, campaign=M.campaign,
                group=names.get(gkey(M)), cost_group=cnames.get((gkey(M), getattr(M, "cost_subset", None))),
                status=dict(M.status), reason_detail=dict(M.detail), fields=f, facts_used=sorted(set(M.used)),
                rules_used=sorted(r for r in M.rules if r), flags=list(dict.fromkeys(M.flags)),
                cost_measure=getattr(M, "cost_carrier", None))


def outputs(ctx, measures, residuals, legacy, out_dir, previous=None):
    os.makedirs(out_dir, exist_ok=True)
    allm = measures + residuals
    names, cnames = group_names(ctx, allm)
    fq, fc, data, gm, fit_rows = [], [], [], {}, collections.defaultdict(dict)
    for L in legacy:                                     # first, in the CSV's order (lqm.load's order-dependent rules)
        r = L.row
        if L.status["quality"] == "legacy:in":
            fq.append(L.line)
            gm[r["group"]] = r["group"]
            fit_rows[L.ref]["quality"] = dict(group=r["group"], model=r["model"], effort=r["effort"], value=r["score"])
        if L.status["cost"] == "legacy:in":
            fc.append(L.line)
            gm[r["group"]] = r["group"]
            fit_rows[L.ref]["cost"] = dict(group=r["group"], model=r["model"], effort=r["effort"], value=r["cost_usd"])
        data.append(dict(r, status_quality=L.status["quality"], status_cost=L.status["cost"]))
    for M in allm:
        r = row_of(ctx, M, names, cnames)
        q, c = M.status["quality"], M.status["cost"]
        if q and q.startswith("in"):
            fq.append(r)
            gm[r["group"]] = base_group(ctx, M)
            fit_rows[M.ref]["quality"] = dict(group=r["group"], model=r["model"], effort=r["effort"], value=r["score"])
        if c and c.startswith("in") and not getattr(M, "cost_carrier", None):
            rc = row_of(ctx, M, names, cnames, axis_cost=True)
            fc.append(rc)
            gm[rc["group"]] = base_group(ctx, M)
            fit_rows[M.ref]["cost"] = dict(group=rc["group"], model=rc["model"], effort=rc["effort"],
                                           value=rc["cost_usd"])
        d = dict(r, status_quality=q or "", status_cost=c or "")
        data.append(d)
    write_csv(os.path.join(out_dir, "fit-quality.csv"), fq, FIT_COLUMNS)
    write_csv(os.path.join(out_dir, "fit-cost.csv"), fc, FIT_COLUMNS)
    write_csv(os.path.join(out_dir, "data.csv"), data, DATA_COLUMNS)
    with open(os.path.join(out_dir, "group-map.json"), "w", encoding="utf-8") as f:
        json.dump(dict(sorted(gm.items())), f, indent=1, ensure_ascii=False)
    rep = dict(build=dict(as_of=ctx.prices.get("as_of"), settings=ctx.settings, supplied=ctx.supplied, registry=V.rel(ctx.args.registry),
                          findings=V.rel(ctx.args.findings), decisions=V.rel(ctx.args.decisions),
                          fit_models=ctx.fit_models, benchmarks=os.path.abspath(ctx.paths["benchmarks"]),
                          lqm="pending" if not ctx.args.no_lqm else "skipped"),
               measures={}, counts={}, stale_decisions=ctx.stale,
               validation=dict(warnings=ctx.rep.warnings, errors=ctx.rep.errors))
    for L in legacy:
        r = L.row
        rep["measures"][L.ref] = dict(
            kind="legacy", source=L.S.id, setup=L.setup_id, line=L.order, row_sha256=L.row_sha256, status=dict(L.status),
            reason_detail=dict(L.detail), tree_would_say=tree_would_say(ctx, r), fit_rows=fit_rows.get(L.ref, {}),
            row=dict(source=r.get("source"), group=r.get("group"), base_group=r.get("group"), model=r.get("model"),
                     effort=r.get("effort"), score=r.get("score"), cost_usd=r.get("cost_usd")))
    for M in allm:
        e = report_entry(ctx, M, names, cnames)
        e["fit_rows"] = fit_rows.get(M.ref, {})
        rq = row_of(ctx, M, names, cnames)
        rc = row_of(ctx, M, names, cnames, axis_cost=True) if (M.status["cost"] or "").startswith("in") else rq
        e["row"] = dict(source=rq["source"], group=rq["group"], base_group=base_group(ctx, M), model=rq["model"],
                        effort=rq["effort"], score=rq["score"], cost_usd=rc["cost_usd"])
        if getattr(M, "m", None) is not None and M.m.get("legacy_ref") and not isinstance(M, Residual):
            e["legacy_ref"] = M.m["legacy_ref"]
        rep["measures"][M.ref] = e
    import build_lqm
    with open(os.path.join(out_dir, "group-setups.json"), "w", encoding="utf-8") as f:
        json.dump(build_lqm.group_setups(rep["measures"], gm, rep["build"]["benchmarks"]), f, indent=1, ensure_ascii=False)
    rep["counts"] = counts(rep["measures"])
    if previous:
        rep["diff"] = diff(previous, rep)
    with open(os.path.join(out_dir, "status-report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1, ensure_ascii=False, default=jsonable)
    return rep


def counts(ms):
    """Counts per reason and axis; legacy measures counted apart (they are reported as legacy)."""
    out = {"quality": collections.Counter(), "cost": collections.Counter()}
    leg = {"quality": collections.Counter(), "cost": collections.Counter()}
    for e in ms.values():
        for ax in out:
            if e["status"][ax] is not None and not (ax == "cost" and e.get("cost_measure")):
                (leg if e.get("kind") == "legacy" else out)[ax][e["status"][ax]] += 1
    res = {ax: dict(sorted(c.items())) for ax, c in out.items()}
    if any(leg.values()):
        res["legacy"] = {ax: dict(sorted(c.items())) for ax, c in leg.items()}
    return res


def diff(prev_path, rep):
    with open(prev_path, encoding="utf-8") as f:
        prev = json.load(f)
    pm, nm = prev.get("measures", {}), rep["measures"]
    changed = {}
    for k in sorted(set(pm) & set(nm)):
        d = {ax: [pm[k]["status"].get(ax), nm[k]["status"].get(ax)] for ax in ("quality", "cost")
             if pm[k]["status"].get(ax) != nm[k]["status"].get(ax)}
        if d:
            changed[k] = d
    return dict(previous=prev_path, added=sorted(set(nm) - set(pm)), removed=sorted(set(pm) - set(nm)),
                changed=changed, by_source=diff_by_source(pm, nm), by_legacy_ref=diff_by_legacy_ref(pm, nm))


def diff_by_legacy_ref(pm, nm):
    """The per-row diff of converted sources (DATA-PIPELINE §8.5): each new measure carrying a legacy_ref is paired
    with the legacy row of the previous report it replaces. Per raw-data `source`: the pairs whose status, value,
    group, model key or configuration (effort) changed (with the new reasons; the digits' spelling does not count), the unchanged count, the legacy rows of that source no
    new measure claims (unmatched_old) and the new measures of the same findings sources that claim no row
    (unmatched_new)."""
    old = {(e.get("line"), e.get("row_sha256")): (ref, e) for ref, e in pm.items() if e.get("kind") == "legacy"}
    claims = [(ref, e) for ref, e in nm.items() if e.get("legacy_ref")]
    if not claims:
        return {}
    res = collections.defaultdict(lambda: dict(changed=[], unchanged=0, unmatched_old=[], unmatched_new=[]))
    used, src_of_findings = set(), collections.defaultdict(collections.Counter)
    for ref, e in claims:
        k = (e["legacy_ref"]["line"], e["legacy_ref"]["row_sha256"])
        if k not in old:
            res["(no legacy row)"]["unmatched_new"].append(dict(measure=ref, legacy_ref=e["legacy_ref"],
                                                                 why="its legacy_ref is not a row of the previous build"))
            continue
        oref, oe = old[k]
        used.add(k)
        raw_src = (oe.get("row") or {}).get("source")
        src_of_findings[e["source"]][raw_src] += 1
        d = {}
        fam = lambda st: "in" if st in ("in", "legacy:in") else "out"   # the verdict; the legacy and tree reasons differ in name
        for ax in ("quality", "cost"):
            if fam(oe["status"].get(ax)) != fam(e["status"].get(ax)):
                d[f"status_{ax}"] = [oe["status"].get(ax), e["status"].get(ax)]
        norm = dict(group=lambda v: (v or "").lstrip("#"),                # a comment group is the out verdict, above
                    effort=lambda v: (v or "")[4:] if (v or "").startswith("req-") else v)
        for fld in ("group", "model", "effort", "score", "cost_usd"):     # keys on both sides; the digits' spelling does not count
            a_, b_ = (oe.get("row") or {}).get(fld), (e.get("row") or {}).get(fld)
            if fld in norm:
                a_, b_ = norm[fld](a_), norm[fld](b_)
            if fld in ("score", "cost_usd"):
                try:
                    if float(a_) == float(b_):
                        continue
                except (TypeError, ValueError):
                    pass
            if a_ != b_:
                d[fld] = [a_, b_]
        if d:
            res[raw_src]["changed"].append(dict(line=k[0], legacy=oref, measure=ref, changes=d,
                                                reasons=e.get("reason_detail")))
        else:
            res[raw_src]["unchanged"] += 1
    touched = {s for c in src_of_findings.values() for s in c}
    for k, (oref, oe) in old.items():
        s = (oe.get("row") or {}).get("source")
        if s in touched and k not in used:
            res[s]["unmatched_old"].append(dict(line=k[0], legacy=oref, row=oe.get("row"), status=oe["status"]))
    for ref, e in nm.items():
        if e.get("kind") == "legacy" or e.get("legacy_ref") or e.get("source") not in src_of_findings:
            continue
        s = src_of_findings[e["source"]].most_common(1)[0][0]
        res[s]["unmatched_new"].append(dict(measure=ref, row=e.get("row"), status=e["status"]))
    return dict(res)


def diff_by_source(pm, nm):
    """Per row source (the fit tables' `source`): rows whose status, value or group changes, matched by (base group,
    model, effort) whatever their measure ids (a migrated source replaces its legacy measures), with the reasons."""
    def index(ms):
        out = collections.defaultdict(lambda: collections.defaultdict(list))
        for ref, e in ms.items():
            r = e.get("row") or {}
            out[r.get("source")][(r.get("base_group"), r.get("model"), r.get("effort"))].append((ref, e))
        return out
    old, new = index(pm), index(nm)
    res = {}
    for src in sorted(set(old) | set(new), key=str):
        ch, added, removed = [], [], []
        for k in sorted(set(old[src]) | set(new[src]), key=str):
            a, b = old[src].get(k, []), new[src].get(k, [])
            for i in range(max(len(a), len(b))):
                if i >= len(a):
                    added.append(dict(row=list(k), measure=b[i][0], status=b[i][1]["status"],
                                      reasons=b[i][1].get("reason_detail")))
                elif i >= len(b):
                    removed.append(dict(row=list(k), measure=a[i][0], status=a[i][1]["status"]))
                else:
                    (ra, ea), (rb, eb) = a[i], b[i]
                    d = {}
                    for ax in ("quality", "cost"):
                        if ea["status"].get(ax) != eb["status"].get(ax):
                            d[f"status_{ax}"] = [ea["status"].get(ax), eb["status"].get(ax)]
                    for fld in ("group", "score", "cost_usd"):
                        if (ea.get("row") or {}).get(fld) != (eb.get("row") or {}).get(fld):
                            d[fld] = [(ea.get("row") or {}).get(fld), (eb.get("row") or {}).get(fld)]
                    if d:
                        ch.append(dict(row=list(k), measures=[ra, rb], changes=d, reasons=eb.get("reason_detail")))
        if ch or added or removed:
            res[src] = dict(changed=ch, added=added, removed=removed)
    return res


def check_args(a):
    for opt, p in (("--registry", a.registry), ("--findings", a.findings)):
        if not os.path.isdir(p):
            raise BadInput(f"{opt} {p}: not a folder")
    if a.class_ratios and not os.path.isfile(a.class_ratios):
        raise BadInput(f"--class-ratios {a.class_ratios}: no such file")
    if os.path.exists(a.out) and not os.path.isdir(a.out):
        raise BadInput(f"--out {a.out}: exists and is not a folder")
    if a.previous:
        prev = read_json_arg(a.previous, "--previous")
        if not isinstance(prev, dict) or not isinstance(prev.get("measures"), dict):
            raise BadInput(f"--previous {a.previous}: not a status report (no measures)")
    if a.decisions and os.path.exists(a.decisions) and not os.path.isfile(a.decisions):
        raise BadInput(f"--decisions {a.decisions}: not a file")
    try:
        os.makedirs(a.out, exist_ok=True)
    except OSError as e:
        raise BadInput(f"--out {a.out}: {e.strerror}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--registry", default=os.path.join(REPO, "data", "registry"))
    ap.add_argument("--findings", default=os.path.join(REPO, "data", "findings"))
    ap.add_argument("--decisions", default=os.path.join(REPO, "data", "decisions.json"))
    ap.add_argument("--out", default=os.path.join(REPO, "data", "build"))
    ap.add_argument("--previous", help="a previous status-report.json: its diff goes into the new report")
    ap.add_argument("--cost-method-unstated", choices=SETTINGS["cost_method_unstated"],
                    default=SETTINGS["cost_method_unstated"][0],
                    help="a source's table with no cost-method fact: one method (flagged) or out")
    ap.add_argument("--fit-models", help="the fit's model list: a file (JSON list or one key per word), or 'catalog' "
                                         "(data/catalog/models.json order); default: every models.json key")
    ap.add_argument("--class-ratios", help="class-ratio table for cost-class-ratio (default <registry>/class-ratios.json)")
    ap.add_argument("--no-check-files", dest="check_files", action="store_false",
                    help="skip validate.py's re-hashing of every saved copy (cells read are still hashed)")
    ap.add_argument("--no-lqm", action="store_true", help="skip the lqm.load step (data/build_lqm.py)")
    ap.add_argument("--registry-files-checked", action="store_true",
                    help="skip the saved-copy checks of the registry's evidence only (a converter's loop on an unchanged "
                         "registry copy); the findings' files are still checked")
    a = ap.parse_args(argv)
    try:
        check_args(a)
        ctx = Ctx(a)
    except BadInput as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except Fatal as e:
        print("build stopped: validation errors\n" + str(e), file=sys.stderr)
        return 1
    measures, residuals, legacy = build(ctx)
    rep = outputs(ctx, measures, residuals, legacy, a.out, a.previous)
    if not a.no_lqm:
        import build_lqm
        build_lqm.run(a.out)
        with open(os.path.join(a.out, "status-report.json"), encoding="utf-8") as f:
            rep = json.load(f)
    print(f"{len(rep['measures'])} measure(s); quality {rep['counts']['quality']}; cost {rep['counts']['cost']}")
    if rep["stale_decisions"]:
        print("stale decisions (reported, not applied):", ", ".join(d["id"] for d in rep["stale_decisions"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
