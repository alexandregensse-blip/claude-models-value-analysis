#!/usr/bin/env python3
"""Validate the pipeline's files against data/schema/*.schema.json and vocab.json, then run the cross-file checks that
need no decision tree (docs/DATA-PIPELINE.md §7, first bullet). Python 3 standard library only.

    python3 data/schema/validate.py                          # data/registry, data/findings, data/decisions.json
    python3 data/schema/validate.py --registry data/findings/examples/registry --findings data/findings/examples
    python3 data/schema/validate.py --check-files ...        # also re-hash the saved copies, find quotes and CSV cells in them
    python3 data/schema/validate.py --hash <source id>#M1 ... # print a decision's facts_hash
    python3 data/schema/validate.py --legacy-coverage raw-data.csv   # how far vocab's legacy patterns map today's flags
    python3 data/schema/validate.py FILE.json ...            # schema check of single files only (kind from name / folder)

JSON Schema subset implemented: $ref (local and cross-file, JSON pointer), type, enum, const, pattern, minLength,
minimum, maximum, minItems, maxItems, items, properties, required, additionalProperties, propertyNames, allOf, anyOf,
unevaluatedProperties (properties of the schema, its allOf members and $ref targets). Unknown keywords and x-* are
ignored. Exit code 1 on any error; warnings do not fail."""
import argparse, collections, csv, datetime as dt, glob, hashlib, html, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
REGISTRY_FILES = {"models": "models.json", "routes": "routes.json", "benchmarks": "benchmarks.json",
                  "publishers": "publishers.json", "prices": "prices.json", "rules": "rules.json"}
REQUIRED_REGISTRIES = ("models", "routes", "benchmarks", "publishers")
TEXT_EXT = (".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".py", ".ts", ".js", ".mjs", ".toml", ".html", ".htm", ".xml", ".tsv")


# ---------------------------------------------------------------- report
class Report:
    def __init__(self):
        self.errors, self.warnings, self.checked = [], [], []

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")

    def done(self):
        for f in self.checked:
            print(f"checked  {f}")
        for w in self.warnings:
            print(f"WARNING  {w}")
        for e in self.errors:
            print(f"ERROR    {e}")
        print(f"\n{len(self.checked)} file(s), {len(self.errors)} error(s), {len(self.warnings)} warning(s)")
        return 1 if self.errors else 0


def rel(p):
    try:
        return os.path.relpath(p, REPO)
    except ValueError:
        return p


def load_json(path, rep):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        rep.err(rel(path), f"cannot read JSON: {e}")
        return None


# ---------------------------------------------------------------- schema engine
class Schemas:
    TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}

    def __init__(self, folder):
        self.folder, self.docs, self.regex = folder, {}, {}

    def doc(self, name):
        if name not in self.docs:
            with open(os.path.join(self.folder, name), encoding="utf-8") as f:
                self.docs[name] = json.load(f)
        return self.docs[name]

    def resolve(self, ref, base):
        file, _, pointer = ref.partition("#")
        file = file or base
        node = self.doc(file)
        for part in [p for p in pointer.split("/") if p]:
            node = node[part.replace("~1", "/").replace("~0", "~")]
        return node, file

    def _type_ok(self, x, t):
        if t == "integer":
            return isinstance(x, int) and not isinstance(x, bool)
        if t == "number":
            return isinstance(x, (int, float)) and not isinstance(x, bool)
        return isinstance(x, self.TYPES[t])

    def _re(self, p):
        if p not in self.regex:
            self.regex[p] = re.compile(p)
        return self.regex[p]

    def evaluated(self, s, base):
        """Property names a schema evaluates (its properties, allOf members, $ref targets)."""
        names = set(s.get("properties", {}))
        if "$ref" in s:
            t, b = self.resolve(s["$ref"], base)
            names |= self.evaluated(t, b)
        for sub in s.get("allOf", []):
            names |= self.evaluated(sub, base)
        return names

    def check(self, x, s, base, path, out):
        """Append (path, message) for each violation of schema s by instance x."""
        if s is True or s == {}:
            return
        if s is False:
            out.append((path, "not allowed"))
            return
        if "$ref" in s:
            t, b = self.resolve(s["$ref"], base)
            sub = []
            self.check(x, t, b, path, sub)
            if sub and s["$ref"].startswith("vocab.json#/$defs/") and not isinstance(x, (dict, list)):
                out.append((path, f"{x!r} is not a term of vocab '{s['$ref'].rsplit('/', 1)[1]}'"))
            else:
                out.extend(sub)
        for sub in s.get("allOf", []):
            self.check(x, sub, base, path, out)
        if "anyOf" in s:
            tries = []
            for sub in s["anyOf"]:
                o = []
                self.check(x, sub, base, path, o)
                if not o:
                    break
                tries.append(o)
            else:
                best = min(tries, key=len)
                if len(best) == 1 or all(len(t) == 1 for t in tries):
                    msgs = sorted({m for t in tries for _, m in t})
                    out.append((path, " / ".join(msgs[:4])))
                else:
                    out.extend(best)
        if "type" in s:
            ts = s["type"] if isinstance(s["type"], list) else [s["type"]]
            if not any(self._type_ok(x, t) for t in ts):
                out.append((path, f"expected {'/'.join(ts)}, got {type(x).__name__} {json.dumps(x, ensure_ascii=False)[:60]}"))
                return
        if "enum" in s and x not in s["enum"]:
            out.append((path, f"{x!r} not in {s['enum'][:12]}{'…' if len(s['enum']) > 12 else ''}"))
        if "const" in s and x != s["const"]:
            out.append((path, f"must be {s['const']!r}"))
        if isinstance(x, str):
            if "pattern" in s and not self._re(s["pattern"]).search(x):
                out.append((path, f"{x!r} does not match {s['pattern']}"))
            if len(x) < s.get("minLength", 0):
                out.append((path, "empty string"))
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            if "minimum" in s and x < s["minimum"]:
                out.append((path, f"{x} < {s['minimum']}"))
            if "maximum" in s and x > s["maximum"]:
                out.append((path, f"{x} > {s['maximum']}"))
        if isinstance(x, list):
            if len(x) < s.get("minItems", 0):
                out.append((path, f"needs at least {s['minItems']} item(s)"))
            if "maxItems" in s and len(x) > s["maxItems"]:
                out.append((path, f"at most {s['maxItems']} item(s)"))
            if "items" in s:
                for i, y in enumerate(x):
                    self.check(y, s["items"], base, f"{path}[{i}]", out)
        if isinstance(x, dict):
            for k in s.get("required", []):
                if k not in x:
                    out.append((path, f"missing required '{k}'"))
            props = s.get("properties", {})
            for k, y in x.items():
                if k in props:
                    self.check(y, props[k], base, f"{path}.{k}", out)
                elif "additionalProperties" in s:
                    self.check(y, s["additionalProperties"], base, f"{path}.{k}", out)
                if "propertyNames" in s:
                    o = []
                    self.check(k, s["propertyNames"], base, f"{path}.{k}", o)
                    out.extend((p, f"key: {m}") for p, m in o)
            if s.get("unevaluatedProperties") is False and "additionalProperties" not in s:
                allowed = self.evaluated(s, base)
                for k in x:
                    if k not in allowed:
                        out.append((f"{path}.{k}", "unknown field"))

    def validate(self, x, schema_name, label, rep):
        out = []
        self.check(x, self.doc(schema_name), schema_name, "$", out)
        for p, m in out:
            rep.err(label, f"{p}: {m}")
        return not out


# ---------------------------------------------------------------- helpers
def when(s, end=False):
    """A date / datetime string → naive UTC datetime; a date as `to` means its whole day."""
    if s is None:
        return dt.datetime.max if end else dt.datetime.min
    if len(s) == 10:
        d = dt.datetime.strptime(s, "%Y-%m-%d")
        return d + dt.timedelta(days=1, microseconds=-1) if end else d
    t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return t.astimezone(dt.timezone.utc).replace(tzinfo=None) if t.tzinfo else t


def overlap(a, b):
    return when(a["from"]) <= when(b["to"], True) and when(b["from"]) <= when(a["to"], True)


def norm(t):
    return re.sub(r"\s+", " ", html.unescape(t or "")).strip().casefold()


def vocab_terms(vocab, name):
    d = vocab["$defs"][name]
    return set(d.get("enum", [])) | {t for alt in d.get("anyOf", []) for t in alt.get("enum", [])}


def in_vocab(schemas, name, value):
    out = []
    schemas.check(value, {"$ref": f"vocab.json#/$defs/{name}"}, "vocab.json", "$", out)
    return not out


def config_ids(model):
    return {c["id"] for c in model.get("configurations", [])}


def split_cell(ref):
    table, rest = ref.split("/", 1)
    row, column = rest.rsplit("/", 1)
    return table, row, column


def saved_path(path, source_file):
    """A saved file key → a readable path (absolute, or relative to the repository / the source file), or None."""
    for p in (path, os.path.join(REPO, path), os.path.join(os.path.dirname(source_file), path)):
        if os.path.isfile(p):
            return p
    return None


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def file_text(path, cache={}):
    if path not in cache:
        with open(path, encoding="utf-8", errors="replace") as f:
            t = f.read()
        if path.endswith((".html", ".htm", ".xml")):
            t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S | re.I)
            t = re.sub(r"<[^>]+>", " ", t)
        cache[path] = norm(t)
    return cache[path]


def cited(measure):
    """(slot, ref) for every fact the measure cites, in slot order."""
    for slot, v in measure["facts"].items():
        for ref in (v if isinstance(v, list) else [v]):
            if ref is not None:
                yield slot, ref


def facts_hash(source, measure, mref):
    facts = {f["id"]: f for f in source.get("facts", [])}
    tables = {t["id"]: t for t in source.get("tables", [])}
    items = []
    for slot, ref in cited(measure):
        if ref.startswith("T"):
            t, row, col = split_cell(ref)
            tb = tables.get(t, {})
            items.append({"slot": slot, "cell": ref, "table": tb, "file_sha256": source.get("sha256", {}).get(tb.get("file"))})
        else:
            items.append({"slot": slot, "fact": facts.get(ref)})
    return [mref, items]


def hash_of(entries):
    return hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


# ---------------------------------------------------------------- vocab checks
def check_vocab(vocab, rep, schemas):
    label = "data/schema/vocab.json"
    schemas.validate(vocab, "vocab.schema.json", label, rep)
    V = vocab["$defs"]
    for name, d in V.items():
        terms = d.get("x-terms")
        if "enum" in d and isinstance(terms, dict) and set(terms) != set(d["enum"]):
            rep.err(label, f"{name}: enum and x-terms differ: {sorted(set(terms) ^ set(d['enum']))[:6]}")
        for t, rec in (terms or {}).items():
            for key in ("legacy_flags", "regex"):
                if isinstance(rec, dict) and rec.get(key):
                    try:
                        re.compile(rec[key])
                    except re.error as e:
                        rep.err(label, f"{name}.{t}.{key}: bad regex: {e}")
    facts, slots = set(V["fact_type"]["enum"]), V["measure_slot"]["x-terms"]
    for t, rec in V["fact_type"]["x-terms"].items():
        for s in rec["slots"]:
            if s not in slots:
                rep.err(label, f"fact_type {t}: unknown slot {s}")
    for s, rec in slots.items():
        for t in rec["fact_types"] or []:
            if t not in facts:
                rep.err(label, f"measure_slot {s}: unknown fact type {t}")
    for t, rec in V["closed_term_fact_types"]["x-terms"].items():
        if t not in facts or rec["vocab"] not in V:
            rep.err(label, f"closed_term_fact_types {t}: bad mapping {rec}")
    for m, rec in V["cost_method"]["x-terms"].items():
        if rec["basis"] not in V["cost_basis"]["enum"]:
            rep.err(label, f"cost_method {m}: unknown basis {rec['basis']}")
    units = set(V["unit"]["enum"])
    for pub, m in V["unit"].get("x-aliases", {}).items():
        for a, u in m.items():
            if a not in units or u not in units:
                rep.warn(label, f"unit alias {pub}: {a} → {u} not both in the unit list")


# ---------------------------------------------------------------- registry checks
def check_registries(reg, rep, schemas, vocab, paths):
    models = (reg.get("models") or {}).get("models", {})
    routes = (reg.get("routes") or {}).get("routes", {})
    bench = reg.get("benchmarks") or {}
    setups, families = bench.get("setups", {}), bench.get("families", {})
    lab = {k: rel(p) for k, p in paths.items()}

    # models.json: references and the identity checks of DATA-PIPELINE §4
    by_maker = collections.defaultdict(list)
    for key, m in models.items():
        L = f"{lab['models']} {key}"
        ids = config_ids(m)
        by_maker[m.get("maker")].append(key)
        if m.get("line") and m["line"] not in models:
            rep.err(L, f"line '{m['line']}' is not a registered key")
        if "solo" in ids:
            solo = [c for c in m["configurations"] if c["id"] == "solo"]
            others = [c for c in m["configurations"] if c["id"] != "solo"]
            if any(overlap(a, b) for a in solo for b in others):
                rep.err(L, "solo is offered alongside other configurations over an overlapping interval (solo only for a [solo] model)")
        for c in m.get("configurations", []):
            if c["id"] == "think-<budget>" and "budget_min" not in c:
                rep.err(L, "think-<budget> needs budget_min")
        released = m.get("released", {}).get("value")
        for c in m.get("configurations", []):
            if released and c.get("served") == "itself" and when(c["from"]) < when(released) - dt.timedelta(days=1):
                rep.warn(L, f"configuration {c['id']} starts {c['from']}, before the release {released}")
        for d in m.get("default", []):
            if d["configuration"] not in ids:
                rep.err(L, f"default '{d['configuration']}' is not one of its configurations {sorted(ids)}")
        for n in m.get("names", []):
            if n.get("selects") and n["selects"] not in ids:
                rep.err(L, f"name {n['name']} selects '{n['selects']}', not one of its configurations")
            if n.get("route") and n["route"] not in routes:
                rep.err(L, f"name {n['name']}: route '{n['route']}' not registered")
        for c in m.get("conversions", []):
            if c["route"] not in routes:
                rep.err(L, f"conversion: route '{c['route']}' not registered")
            if c["served"] not in ids and not in_vocab(schemas, "mapping_result", c["served"]):
                rep.err(L, f"conversion serves '{c['served']}', not one of its configurations")
        for md in m.get("modes", []):
            if md["key"] not in models:
                rep.err(L, f"mode {md['parameter']} → '{md['key']}' not registered")
        for rec in m.get("configurations", []) + m.get("default", []) + m.get("conversions", []) + m.get("modes", []) + \
                [s for n in m.get("names", []) for s in n["serves"]]:
            if when(rec["from"]) > when(rec["to"], True):
                rep.err(L, f"interval {rec['from']} → {rec['to']} ends before it starts")
    for maker, keys in by_maker.items():
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                ma, mb = models[a], models[b]
                if ma["label"].strip().casefold() == mb["label"].strip().casefold():
                    rep.err(lab["models"], f"identity: {a} and {b} ({maker}) have the same display label '{ma['label']}'")
                for na in ma.get("names", []):
                    for nb in mb.get("names", []):
                        if na["name"].casefold() == nb["name"].casefold() and na["kind"] == nb["kind"] \
                                and (na.get("route") or "maker-api") == (nb.get("route") or "maker-api") \
                                and any(overlap(x, y) for x in na["serves"] for y in nb["serves"]):
                            rep.err(lab["models"], f"identity: {a} and {b} ({maker}) both serve {na['kind']} '{na['name']}' over overlapping intervals")

    # routes.json
    for rid, r in routes.items():
        for key, rm in r.get("models", {}).items():
            L = f"{lab['routes']} {rid}/{key}"
            if key not in models:
                rep.err(L, "model key not registered")
                continue
            ids = config_ids(models[key])
            for a in rm.get("accepts", []):
                if a["configuration"] not in ids:
                    rep.warn(L, f"accepts '{a['configuration']}', not in the model's configurations {sorted(ids)}")
            for mp in rm.get("mapping", []):
                if mp["served"] not in ids and not in_vocab(schemas, "mapping_result", mp["served"]):
                    rep.err(L, f"maps to '{mp['served']}', not one of the model's configurations")
            for d in rm.get("default", []):
                if d["configuration"] not in ids:
                    rep.err(L, f"default '{d['configuration']}' not one of the model's configurations {sorted(ids)}")

    # benchmarks.json
    for sid, s in setups.items():
        L = f"{lab['benchmarks']} {sid}"
        if s["family"] not in families:
            rep.err(L, f"family '{s['family']}' not registered")
        comp = s.get("composite")
        if comp:
            for c in comp["components"]:
                if c not in setups:
                    rep.err(L, f"composite component '{c}' not registered")
            for c in comp["formula"]["weights"]:
                if c not in comp["components"]:
                    rep.err(L, f"weight for '{c}', not a component")
        if s["headline"]["basis"] == "decision" and not s["headline"].get("decision"):
            rep.warn(L, "headline pending a maintainer decision (the tree gives out:not-headline until then)")
        if s["headline"]["basis"] != "decision" and not s["headline"].get("evidence"):
            rep.err(L, "headline without evidence")

    # prices.json
    prices = reg.get("prices")
    if prices:
        base = set()
        for i, p in enumerate(prices["prices"]):
            L = f"{lab['prices']} prices[{i}]"
            if p["model"] not in models:
                rep.err(L, f"model '{p['model']}' not registered")
            if p["route"] not in routes:
                rep.err(L, f"route '{p['route']}' not registered")
            elif p["kind"] == "standard" and routes[p["route"]]["class"] == "maker-api":
                if when(p["from"]) <= when(prices["as_of"]) <= when(p["to"], True):
                    base.add(p["model"])
            if p["kind"] == "standard" and not p.get("classes"):
                rep.err(L, "standard price without classes")
        for key in sorted({p["model"] for p in prices["prices"]} - base):
            rep.warn(lab["prices"], f"{key}: no standard maker-API price in force on as_of {prices['as_of']}")

    # rules.json
    rules = reg.get("rules")
    if rules:
        seen = collections.Counter(r["id"] for r in rules["rules"])
        for k, n in seen.items():
            if n > 1:
                rep.err(lab["rules"], f"rule id {k} defined {n} times")


# ---------------------------------------------------------------- findings checks
def check_source(src, path, reg, rep, schemas, vocab, check_files):
    L = rel(path)
    V = vocab["$defs"]
    publishers = (reg.get("publishers") or {}).get("publishers", {})
    routes = (reg.get("routes") or {}).get("routes", {})
    if os.path.splitext(os.path.basename(path))[0] != src["id"]:
        rep.err(L, f"file name must be the source id '{src['id']}'")
    if src["publisher"] not in publishers:
        rep.err(L, f"publisher '{src['publisher']}' not registered in publishers.json")
    slug = src["publisher"].lower().replace("/", "_")
    if not src["id"].startswith(f"src-{slug}-"):
        rep.warn(L, f"id does not start with src-{slug}-")
    saved = src.get("sha256", {})
    forms = V["fact_form"]["x-terms"]
    closed = V["closed_term_fact_types"]["x-terms"]
    tables = {t["id"]: t for t in src.get("tables", [])}
    charts = {c["id"]: c for c in src.get("charts", [])}
    for kind, items in (("table", src.get("tables", [])), ("chart", src.get("charts", [])), ("fact", src.get("facts", []))):
        for k, n in collections.Counter(x["id"] for x in items).items():
            if n > 1:
                rep.err(L, f"{kind} id {k} used {n} times")
    for t in list(tables.values()) + list(charts.values()):
        if t["file"] not in saved:
            rep.err(L, f"{t['id']}: file '{t['file']}' has no sha256 entry")
    for t in tables.values():
        for col, spec in t["columns"].items():
            says = spec if isinstance(spec, str) else spec["says"]
            if says in closed and (isinstance(spec, str) or "term" not in spec):
                rep.err(L, f"{t['id']}.{col}: a {says} column needs a term")
            elif says in closed and not in_vocab(schemas, closed[says]["vocab"], spec["term"]):
                rep.err(L, f"{t['id']}.{col}: term '{spec['term']}' not in vocab {closed[says]['vocab']}")
    for f in src.get("facts", []):
        F = f"{L} {f['id']}"
        if f.get("file") and f["file"] not in saved:
            rep.err(F, f"file '{f['file']}' has no sha256 entry")
        if not f.get("file") and not f.get("table") and not f.get("chart") and len(saved) > 1:
            rep.err(F, "the source has several saved files: name the fact's file")
        if f.get("table") and f["table"] not in tables:
            rep.err(F, f"table {f['table']} not defined")
        if f.get("chart") and f["chart"] not in charts:
            rep.err(F, f"chart {f['chart']} not defined")
        if forms.get(f["form"], {}).get("quote") and not f.get("quote"):
            rep.err(F, f"a {f['form']} fact needs a quote")
        if f.get("quote") and norm(f["value"]) not in norm(f["quote"]):
            rep.err(F, f"the quote does not contain the value {f['value']!r}")
        if f["form"] == "chart":
            c = charts.get(f.get("chart"))
            if not c:
                rep.err(F, "a chart fact names its chart")
            elif c["kind"] == "raster" and f["level"] == "written":
                rep.err(F, "a point of a raster chart is read, not written")
            if f["level"] == "read" and (f.get("precision") or {}).get("model") != "chart-pixel":
                rep.err(F, "a read fact needs a chart-pixel precision")
        elif f["level"] == "read":
            rep.err(F, "only chart facts are read")
        if f["form"] == "data-file" and not (f.get("table") or f.get("file") or len(saved) == 1):
            rep.err(F, "a data-file fact names its table or file")
        if f["says"] in closed:
            if "term" not in f:
                rep.err(F, f"a {f['says']} fact needs a term (vocab {closed[f['says']]['vocab']})")
            elif not in_vocab(schemas, closed[f["says"]]["vocab"], f["term"]):
                rep.err(F, f"term '{f['term']}' not in vocab {closed[f['says']]['vocab']}")
        if f["says"] == "route" and "term" in f and f["term"] not in routes:
            rep.err(F, f"route term '{f['term']}' not registered in routes.json")
    if check_files:
        check_saved(src, path, rep)


def check_saved(src, path, rep):
    L = rel(path)
    reach = {}
    for key, h in src.get("sha256", {}).items():
        p = saved_path(key, path)
        if not p:
            rep.warn(L, f"saved file not reachable here: {key}")
            continue
        reach[key] = p
        if sha256_of(p) != h:
            rep.err(L, f"sha256 mismatch: {key}")
    only = next(iter(reach.values())) if len(src.get("sha256", {})) == 1 and reach else None
    for f in src.get("facts", []):
        p = reach.get(f.get("file")) if f.get("file") else only
        if f.get("quote") and p and p.endswith(TEXT_EXT) and norm(f["quote"]) not in file_text(p):
            rep.err(f"{L} {f['id']}", f"quote not found in the saved file {os.path.basename(p)}")


def table_rows(src, table, path, cache={}):
    """Rows of a CSV table keyed by its row_key, or None when not readable here."""
    p = saved_path(table["file"], path)
    if not p or table.get("format", "csv") != "csv" and not p.endswith(".csv"):
        return None
    if p not in cache:
        with open(p, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        cache[p] = (rows[0].keys() if rows else set(), rows)
    cols, rows = cache[p]
    return cols, {r.get(table["row_key"]): r for r in rows}


def check_measures(ms, path, sources, reg, rep, vocab, check_files):
    L = rel(path)
    setups = (reg.get("benchmarks") or {}).get("setups", {})
    stem = os.path.splitext(os.path.basename(path))[0]
    if stem != ms["source"]:
        rep.err(L, f"file name must be the source id '{ms['source']}'")
    src = sources.get(ms["source"])
    if not src:
        rep.err(L, f"source {ms['source']} not found among the source files, or invalid")
        return
    spath, src = src
    facts = {f["id"]: f for f in src.get("facts", [])}
    tables = {t["id"]: t for t in src.get("tables", [])}
    slots = vocab["$defs"]["measure_slot"]["x-terms"]
    for k, n in collections.Counter(m["id"] for m in ms["measures"]).items():
        if n > 1:
            rep.err(L, f"measure id {k} used {n} times")
    for m in ms["measures"]:
        M = f"{L} {m['id']}"
        if m["setup"] not in setups:
            rep.err(M, f"setup '{m['setup']}' not registered in benchmarks.json")
        if m["facts"].get("value") is None and not m["facts"].get("spend"):
            rep.err(M, "a measure needs a value or a spend")
        for slot, ref in cited(m):
            allowed = slots[slot]["fact_types"]
            if ref.startswith("T"):
                t, row, col = split_cell(ref)
                if t not in tables:
                    rep.err(M, f"{slot}: {ref}: table {t} not defined")
                    continue
                spec = tables[t]["columns"].get(col)
                if spec is None:
                    rep.err(M, f"{slot}: {ref}: column '{col}' not declared in {t}.columns")
                    continue
                says = spec if isinstance(spec, str) else spec["says"]
                if check_files:
                    got = table_rows(src, tables[t], spath)
                    if got:
                        cols, rows = got
                        if col not in cols:
                            rep.err(M, f"{ref}: column '{col}' not in the saved file")
                        elif row not in rows:
                            rep.err(M, f"{ref}: no row '{row}' in the saved file")
                        elif not (rows[row].get(col) or "").strip():
                            rep.err(M, f"{ref}: the cell is empty")
            else:
                if ref not in facts:
                    rep.err(M, f"{slot}: fact {ref} does not exist in {ms['source']}")
                    continue
                says = facts[ref]["says"]
            if allowed is not None and says not in allowed:
                rep.err(M, f"{slot}: {ref} is a '{says}' fact, not one of {allowed}")
            if slot == "value" and says not in ("score", "cost"):
                rep.err(M, f"value {ref} is a '{says}' fact")


def check_decisions(dec, path, sources, measures, rep):
    L = rel(path)
    for d in dec["decisions"]:
        entries, ok = [], True
        for mref in d["measures"]:
            sid, mid = mref.split("#")
            m = measures.get((sid, mid))
            if not m:
                rep.err(f"{L} {d['id']}", f"measure {mref} not found")
                ok = False
                continue
            entries.append(facts_hash(sources[sid][1], m, mref))
        if ok and hash_of(entries) != d["facts_hash"]:
            rep.warn(f"{L} {d['id']}", "facts_hash no longer matches: the decision is reported, not applied")


# ---------------------------------------------------------------- legacy coverage
def legacy_coverage(csv_path, vocab):
    V = vocab["$defs"]
    meth = V["cost_method"]
    order = [(m, re.compile(meth["x-terms"][m]["legacy_flags"], re.I)) for m in meth["x-order"]]
    subs = re.compile(V["cost_basis"]["x-terms"]["subscription"]["legacy_flags"], re.I)
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    cost = [r for r in rows if (r.get("cost_usd") or "").strip()]
    per, unmapped_src, unmapped_flags = collections.Counter(), collections.Counter(), collections.Counter()
    for r in cost:
        t = r.get("confound") or ""
        m = next((m for m, p in order if p.search(t)), None)
        per[m or ("(subscription basis only)" if subs.search(t) else None)] += 1
        if m is None:
            unmapped_src[r["source"]] += 1
            for tok in re.split(r";\s*", t):
                head = re.split(r"[:=(]", tok.strip())[0].strip()[:50]
                if re.search(r"cost|price|bill|spend|usd", head, re.I):
                    unmapped_flags[head] += 1
    print(f"rows with a cost: {len(cost)}")
    for m, n in per.most_common():
        print(f"  {n:6d}  {m or 'UNMAPPED'}" + (f"  (basis {meth['x-terms'][m]['basis']})" if m in meth['x-terms'] else ""))
    print("unmapped, by source:", ", ".join(f"{s} {n}" for s, n in unmapped_src.most_common(15)))
    print("unmapped cost-ish flag prefixes:", ", ".join(f"{s} {n}" for s, n in unmapped_flags.most_common(20)))
    for name, efforts in (("nothink_spelling", {"nothink", "req-nothink"}), ("think_spelling", {"solo", "req-enabled", "req-thinking", "think-unstated"})):
        pats = [re.compile(rec["regex"], re.I) for rec in V[name]["x-terms"].values()]
        rs = [r for r in rows if r.get("effort") in efforts]
        hit = sum(1 for r in rs if any(p.search((r.get("confound") or "") + " " + (r.get("ref") or "")) for p in pats))
        print(f"{name}: {hit} of {len(rs)} rows ({'/'.join(sorted(efforts))}) carry a listed spelling")
    return 0


# ---------------------------------------------------------------- main
def kind_of(path):
    b, parent = os.path.basename(path), os.path.basename(os.path.dirname(path))
    if parent == "sources":
        return "source"
    if parent == "measures":
        return "measure"
    if b == "decisions.json":
        return "decisions"
    if b == "vocab.json":
        return "vocab"
    stem = b.split(".")[0]
    return stem if stem in REGISTRY_FILES else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="single files: schema check only")
    ap.add_argument("--registry", default=os.path.join(REPO, "data", "registry"))
    ap.add_argument("--findings", default=os.path.join(REPO, "data", "findings"))
    ap.add_argument("--decisions", default=os.path.join(REPO, "data", "decisions.json"))
    ap.add_argument("--check-files", action="store_true", help="re-hash reachable saved copies, look for quotes and CSV cells in them")
    ap.add_argument("--hash", nargs="+", metavar="MEASURE_REF", help="print the facts_hash of these measures (one decision)")
    ap.add_argument("--legacy-coverage", metavar="RAW_DATA_CSV", help="report how vocab's legacy patterns map today's flags")
    a = ap.parse_args()
    rep, schemas = Report(), Schemas(HERE)
    vocab = schemas.doc("vocab.json")
    if a.legacy_coverage:
        return legacy_coverage(a.legacy_coverage, vocab)
    check_vocab(vocab, rep, schemas)
    rep.checked.append("data/schema/vocab.json")
    schema_of = {"source": "source.schema.json", "measure": "measure.schema.json", "decisions": "decisions.schema.json",
                 "vocab": "vocab.schema.json", **{k: f"{k}.schema.json" for k in REGISTRY_FILES}}
    if a.files:
        for p in a.files:
            k, x = kind_of(p), load_json(p, rep)
            if x is None:
                continue
            if not k:
                rep.err(rel(p), "cannot tell the file's kind from its name or folder")
                continue
            schemas.validate(x, schema_of[k], rel(p), rep)
            rep.checked.append(rel(p))
        return rep.done()

    reg, paths = {}, {}
    for k, name in REGISTRY_FILES.items():
        p = os.path.join(a.registry, name)
        paths[k] = p
        if not os.path.isfile(p):
            (rep.err if k in REQUIRED_REGISTRIES else rep.warn)(rel(a.registry), f"no {name}")
            continue
        x = load_json(p, rep)
        if x is not None and schemas.validate(x, schema_of[k], rel(p), rep):
            reg[k] = x
        rep.checked.append(rel(p))
    if all(k in reg for k in REQUIRED_REGISTRIES):
        check_registries(reg, rep, schemas, vocab, paths)

    sources, measures = {}, {}
    for p in sorted(glob.glob(os.path.join(a.findings, "sources", "*.json"))):
        x = load_json(p, rep)
        rep.checked.append(rel(p))
        if x is not None and schemas.validate(x, "source.schema.json", rel(p), rep):
            if x["id"] in sources:
                rep.err(rel(p), f"source id {x['id']} also in {rel(sources[x['id']][0])}")
            sources[x["id"]] = (p, x)
            check_source(x, p, reg, rep, schemas, vocab, a.check_files)
    for p in sorted(glob.glob(os.path.join(a.findings, "measures", "*.json"))):
        x = load_json(p, rep)
        rep.checked.append(rel(p))
        if x is not None and schemas.validate(x, "measure.schema.json", rel(p), rep):
            for m in x["measures"]:
                if x["source"] in sources:
                    measures[(x["source"], m["id"])] = m
            check_measures(x, p, sources, reg, rep, vocab, a.check_files)
    for sid in sources:
        if not any(s == sid for s, _ in measures):
            rep.warn(rel(sources[sid][0]), "no measure file cites this source")

    if a.hash:
        entries = []
        for mref in a.hash:
            sid, mid = mref.split("#")
            if (sid, mid) not in measures:
                rep.err("--hash", f"measure {mref} not found")
                return rep.done()
            entries.append(facts_hash(sources[sid][1], measures[(sid, mid)], mref))
        print(hash_of(entries))
        return 0
    if os.path.isfile(a.decisions):
        x = load_json(a.decisions, rep)
        rep.checked.append(rel(a.decisions))
        if x is not None and schemas.validate(x, "decisions.schema.json", rel(a.decisions), rep):
            check_decisions(x, a.decisions, sources, measures, rep)
    return rep.done()


if __name__ == "__main__":
    sys.exit(main())
