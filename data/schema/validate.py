#!/usr/bin/env python3
"""Validate the pipeline's files against data/schema/*.schema.json and vocab.json, then run the cross-file checks that
need no decision tree (docs/DATA-PIPELINE.md §7, first bullet). Python 3 standard library only.

    python3 data/schema/validate.py                          # data/registry, data/findings, data/decisions.json
    python3 data/schema/validate.py --registry data/findings/examples/registry --findings data/findings/examples
    python3 data/schema/validate.py --check-files ...        # also re-hash the saved copies, find quotes and CSV cells in them
    python3 data/schema/validate.py --hash <source id>#M1 ... # print a decision's facts_hash
    python3 data/schema/validate.py --legacy-coverage raw-data.csv [--flag-map F]  # how far vocab + flag-map map today's flags
    python3 data/schema/validate.py FILE.json ...            # schema check of single files only (kind from name / folder)

JSON Schema subset implemented: $ref (local and cross-file, JSON pointer), type, enum, const, pattern, minLength,
minimum, maximum, minItems, maxItems, items, properties, required, additionalProperties, propertyNames, allOf, anyOf,
format (date, date-time, date-or-date-time: parsed strictly), unevaluatedProperties (properties of the schema, its allOf members and $ref targets). Unknown keywords and x-* are
ignored. Exit code 1 on any error; warnings do not fail."""
import argparse, collections, csv, datetime as dt, glob, hashlib, html, json, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
REGISTRY_FILES = {"models": "models.json", "routes": "routes.json", "benchmarks": "benchmarks.json",
                  "publishers": "publishers.json", "prices": "prices.json", "rules": "rules.json", "flag-map": "flag-map.json",
                  "price-tables": "price-tables.json"}
REQUIRED_REGISTRIES = ("models", "routes", "benchmarks", "publishers")
OPEN_TO = ("configurations", "serves")          # interval lists where to = null (no end known) is allowed
TEXT_EXT = (".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".py", ".ts", ".js", ".mjs", ".toml", ".html", ".htm", ".xml", ".tsv")


# ---------------------------------------------------------------- report
class Report:
    def __init__(self):
        self.errors, self.warnings, self.checked = [], [], []

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")

    registry = None          # the registry folder (relative): its messages are summarised apart
    verbose = False          # every registry warning, and every file checked

    def file_of(self, where):
        return where.split(" ", 1)[0].rstrip(":")

    def done(self):
        """A summary per file: each findings / decisions file with its own errors and warnings, then the registry's
        (its errors in full, its warnings counted by kind unless --verbose)."""
        per = collections.OrderedDict()
        for kind, msgs in (("ERROR", self.errors), ("WARNING", self.warnings)):
            for m in msgs:
                per.setdefault(self.file_of(m), []).append((kind, m))
        reg = self.registry or "\0"
        is_reg = lambda f: f.startswith(reg) or f.endswith("vocab.json")  # noqa: E731
        if self.verbose:
            for f in self.checked:
                print(f"checked  {f}")
        own = [f for f in per if not is_reg(f)]
        for f in own:
            ms = per[f]
            print(f"== {f}: {sum(k == 'ERROR' for k, _ in ms)} error(s), {sum(k == 'WARNING' for k, _ in ms)} warning(s)")
            for k, m in sorted(ms, key=lambda x: x[0] != "ERROR"):
                print(f"{k:8} {m}")
        rf = [f for f in per if is_reg(f)]
        re_ = [m for f in rf for k, m in per[f] if k == "ERROR"]
        rw = [m for f in rf for k, m in per[f] if k == "WARNING"]
        if rf:
            print(f"== registry ({reg}): {len(re_)} error(s), {len(rw)} warning(s)")
            for m in re_:
                print(f"ERROR    {m}")
            if self.verbose:
                for m in rw:
                    print(f"WARNING  {m}")
            else:
                kinds = collections.Counter(re.sub(r"'[^']*'|\b\d[\d.:-]*\b", "…", re.sub(r"\[[^\]]*\]", "[…]",
                                                   m.split(": ", 1)[-1]))[:90] for m in rw)
                for k, n in kinds.most_common(12):
                    print(f"WARNING  ×{n:<5} {k}")
                if len(kinds) > 12:
                    print(f"WARNING  … {len(kinds) - 12} more kinds (--verbose lists every warning)")
        print(f"\n{len(self.checked)} file(s), {len(self.errors)} error(s), {len(self.warnings)} warning(s)"
              f" — findings and decisions: {sum(len(per[f]) for f in own)} message(s) in {len(own)} file(s); "
              f"registry: {len(re_)} error(s), {len(rw)} warning(s)")
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
            elif s.get("format") in ("date", "date-time", "date-or-date-time") and parse_when(x) is None:
                out.append((path, f"{x!r} is not a real {s['format']}"))
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
def parse_when(s):
    """A date / datetime string → naive UTC datetime, or None when it is not a real date."""
    try:
        if len(s) == 10:
            return dt.datetime.strptime(s, "%Y-%m-%d")
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return t.astimezone(dt.timezone.utc).replace(tzinfo=None) if t.tzinfo else t
    except (ValueError, TypeError):
        return None


def when(s, end=False):
    """A date / datetime string → naive UTC datetime; a date as `to` means its whole day (bad dates → open bound)."""
    t = parse_when(s) if s is not None else None
    if t is None:
        return dt.datetime.max if end else dt.datetime.min
    return t + dt.timedelta(days=1, microseconds=-1) if end and len(s) == 10 else t


def overlap(a, b):
    return when(a["from"]) <= when(b["to"], True) and when(b["from"]) <= when(a["to"], True)


def norm(t):
    """Quote matching: NFKC (ligatures: 'ﬁ' → 'fi'), HTML entities, whitespace collapsed, casefolded."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", html.unescape(t or ""))).strip().casefold()


def norm_display(name, vocab):
    """Display-name rule N (models.schema.json): NFKC, casefold, '_' '-' ':' '/' as spaces, spaces collapsed, one leading
    maker spelling (vocab maker x-terms.display_prefixes) dropped."""
    t = re.sub(r"[_\-:/\u2010\u2011\u2012\u2013]", " ", unicodedata.normalize("NFKC", name).casefold())
    t = re.sub(r"(?<=[a-z]) (?=[0-9])", "", re.sub(r"\s+", " ", t).strip())   # 'Qwen 3.6' is 'Qwen3.6' (26 Oct)
    prefixes = [p.casefold() for rec in vocab["$defs"]["maker"]["x-terms"].values() for p in rec.get("display_prefixes", [])]
    cut = True
    while cut:                                       # leading maker spellings ('Anthropic Claude Opus 5' → 'opus 5'; 26 Oct)
        cut = False
        for p in prefixes:
            if t.startswith(p + " ") and len(t) > len(p) + 1:
                t, cut = t[len(p) + 1:], True
                break
    return t


def resolve_api_id(value, namespace, models, routes):
    """Model keys an API id resolves to under the name rule (models.schema.json), ignoring dates."""
    def in_ns(v, route):
        prefixes = sorted((routes.get(route or "maker-api", {}).get("name_prefixes") or []), key=len, reverse=True)
        for p in prefixes:
            if v.casefold().startswith(p.casefold()):
                v = v[len(p):]
                break
        ns = None if route in (None, "maker-api") else route
        return {k for k, m in models.items() for n in m.get("names", [])
                if n["kind"] == "api-id" and (n.get("route") or None) == ns and same_name(n["name"], v, route, routes)}
    if namespace != "prefix":
        return in_ns(value, namespace)
    head, sep, rest = value.partition("/")
    if sep:
        for rid, r in routes.items():
            if any(p.casefold() == (head + "/").casefold() for p in r.get("name_prefixes") or []):
                return in_ns(value, rid)
    keys = set()
    for rid in list(routes) or ["maker-api"]:
        keys |= in_ns(rest, rid) if sep else set()
        keys |= in_ns(value, rid)
    return keys


def same_name(registered, value, route, routes):
    """An API id against a registered name of one namespace: exact, or casefolded in a namespace whose route has
    names_case_insensitive (the Hugging Face namespace: repository ids are case-insensitive)."""
    if (routes.get(route or "maker-api") or {}).get("names_case_insensitive"):
        return registered.casefold() == value.casefold()
    return registered == value


def component_names(comp):
    """(name, setup id or None) of a composite's components: a plain setup id is its own name."""
    return [(c, c) if isinstance(c, str) else (c["name"], c.get("setup")) for c in comp.get("components", [])]


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


def stamp(path):
    """A cache key that changes with the file (several builds in one process)."""
    st = os.stat(path)
    return (path, st.st_mtime_ns, st.st_size)


def file_text(path, cache={}, raw=False):
    key = stamp(path) + (raw,)
    if key not in cache:
        with open(path, encoding="utf-8", errors="replace") as f:
            t = f.read()
        if path.endswith((".html", ".htm", ".xml")) and not raw:
            t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S | re.I)
            t = re.sub(r"<[^>]+>", " ", t)
        cache[key] = norm(t)
    return cache[key]


def quote_in_file(quote, path):
    """A quote is in a saved text file: in its visible text, or, for a saved page, in its raw source (data embedded in
    a script, such as a Next.js payload: the pricing pages of 2024)."""
    q = norm(quote)
    return q in file_text(path) or (path.endswith((".html", ".htm")) and q in file_text(path, raw=True))


def cited(measure):
    """(slot, ref) for every fact the measure cites, in slot order (value_seen_in holds capture ids, not facts)."""
    for slot, v in measure["facts"].items():
        if slot == "value_seen_in":
            continue
        for ref in (v if isinstance(v, list) else [v]):
            if ref is not None:
                yield slot, ref


def facts_hash(source, measure, mref):
    facts = {f["id"]: {k: v for k, v in f.items() if k not in ("note", "translation")} for f in source.get("facts", [])}
    tables = {t["id"]: t for t in source.get("tables", [])}
    items = []
    for slot, ref in cited(measure):
        if ref.startswith("T"):
            t, row, col = split_cell(ref)
            tb = tables.get(t, {})
            items.append({"slot": slot, "cell": ref, "table": tb, "file_sha256": source.get("sha256", {}).get(tb.get("file"))})
        else:
            items.append({"slot": slot, "fact": facts.get(ref)})
    return [mref, measure.get("setup"), items]


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
def walk_intervals(x, key=None, path="$"):
    """(path, container key, record) for every dated record {from, to, evidence} in a registry document."""
    if isinstance(x, dict):
        if "from" in x and "to" in x and "evidence" in x:
            yield path, key, x
        for k, v in x.items():
            yield from walk_intervals(v, k if isinstance(v, list) else key, f"{path}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from walk_intervals(v, key, f"{path}[{i}]")


def walk_evidence(x, path="$"):
    """(path, evidence) for every evidence record of a registry document."""
    if isinstance(x, dict):
        for k, v in x.items():
            if k == "evidence" and isinstance(v, list):
                for i, e in enumerate(v):
                    if isinstance(e, dict):
                        yield f"{path}.evidence[{i}]", e
            else:
                yield from walk_evidence(v, f"{path}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from walk_evidence(v, f"{path}[{i}]")


def check_dated(doc, label, rep):
    """Interval rules of DATA-PIPELINE §4 on every dated record of a registry file."""
    for path, key, r in walk_intervals(doc):
        if r["to"] is None:
            if key not in OPEN_TO:
                rep.err(label, f"{path}: to = null; a dated {key} ends at its stated change or its last capture")
        elif when(r["from"]) > when(r["to"], True):
            rep.err(label, f"{path}: interval {r['from']} → {r['to']} ends before it starts")
        if r.get("from_basis") == "earliest-capture" and len(r["from"]) != 10:
            rep.err(label, f"{path}: a bound taken from a capture is the capture's day (YYYY-MM-DD), not {r['from']}")
        if r.get("to_basis") == "last-capture" and r["to"] is not None and len(r["to"]) != 10:
            rep.err(label, f"{path}: a bound taken from a capture is the capture's day (YYYY-MM-DD), not {r['to']}")
        if r.get("to_basis") == "open" and r["to"] is not None:
            rep.err(label, f"{path}: to_basis open but to = {r['to']}")


def check_evidence_files(doc, path, label, rep):
    """--check-files on registry evidence: sha256 and quote of every saved copy reachable here."""
    for p, e in walk_evidence(doc):
        if not e.get("file"):
            continue
        f = saved_path(e["file"], path)
        if not f:
            rep.warn(label, f"{p}: saved file not reachable here: {e['file']}")
            continue
        if e.get("sha256") and sha256_of(f) != e["sha256"]:
            rep.err(label, f"{p}: sha256 mismatch: {e['file']}")
        if e.get("quote"):
            if f.endswith(".pdf"):
                rep.err(label, f"{p}: a quote in a PDF points at its text extraction")
            elif f.endswith(TEXT_EXT) and not quote_in_file(e["quote"], f):
                rep.err(label, f"{p}: quote not found in {os.path.basename(f)}")


def within_configuration(rec, cid, model, what, L, rep, route_entry=False):
    """A dated record naming a configuration (a default, a conversion's result, a route's accepts or default) lies
    within that configuration's dated intervals: starting before the configuration exists is an error; outlasting it
    is an error for the maker's own records and a warning for a route's (a host may keep serving open weights after
    the maker's API stops)."""
    ivs = [c for c in model.get("configurations", []) if c["id"] == cid or
           (cid.startswith("think-") and cid[6:].isdigit() and c["id"] == "think-<budget>")]
    if not ivs:
        return
    start = when(rec["from"])
    host = [c for c in ivs if when(c["from"]) <= start <= (when(c["to"], True) if c.get("to") is not None else dt.datetime.max)]
    if not host:
        rep.err(L, f"{what} '{cid}' from {rec['from']}: its configuration does not exist then "
                   f"({', '.join(c['from'] + ' → ' + str(c.get('to')) for c in ivs)})")
        return
    end = when(rec["to"], True) if rec.get("to") is not None else dt.datetime.max
    if not any(when(c["from"]) <= start and end <= (when(c["to"], True) if c.get("to") is not None else dt.datetime.max)
               for c in ivs):
        (rep.warn if route_entry else rep.err)(L, f"{what} '{cid}' {rec['from']} → {rec.get('to')} outlasts its "
                                                  f"configuration's dates")


def check_evidence_complete(doc, label, rep):
    """Every evidence record of a registry entry has a saved file and a quote (a findings fact cited by source and
    fact carries its own)."""
    for p, e in walk_evidence(doc):
        if e.get("source"):
            continue
        missing = [k for k in ("file", "quote") if not e.get(k)]
        if missing:
            rep.err(label, f"{p}: evidence without its {' and '.join(missing)}")


def overlapping_defaults(defaults):
    """Two defaults answering for the same call (the whole call and a `thinking` default both answer for a call that
    sends nothing; an `effort` default for a call that turns thinking on) naming different configurations over
    overlapping intervals."""
    side = lambda d: "effort" if d.get("setting") == "effort" else "call"   # noqa: E731
    return [(a["configuration"], b["configuration"]) for i, a in enumerate(defaults) for b in defaults[i + 1:]
            if side(a) == side(b) and a["configuration"] != b["configuration"] and overlap(a, b)]


def check_registries(reg, rep, schemas, vocab, paths, check_files):
    models = (reg.get("models") or {}).get("models", {})
    routes = (reg.get("routes") or {}).get("routes", {})
    bench = reg.get("benchmarks") or {}
    setups, families = bench.get("setups", {}), bench.get("families", {})
    lab = {k: rel(p) for k, p in paths.items()}
    for k, doc in reg.items():
        check_dated(doc, lab[k], rep)
        if k != "flag-map":
            check_evidence_complete(doc, lab[k], rep)
        if check_files:
            check_evidence_files(doc, paths[k], lab[k], rep)

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
            else:
                within_configuration(d, d["configuration"], m, "default", L, rep)
        for c in m.get("conversions", []):
            if c["served"] in ids:
                within_configuration(c, c["served"], m, f"conversion {c['requested']} →", L, rep)
        for a_, b_ in overlapping_defaults(m.get("default", [])):
            rep.err(L, f"defaults '{a_}' and '{b_}' overlap in time")
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
    for maker, keys in by_maker.items():
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                ma, mb = models[a], models[b]
                if norm_display(ma["label"], vocab) == norm_display(mb["label"], vocab):
                    rep.err(lab["models"], f"identity: {a} and {b} ({maker}) have the same display label '{ma['label']}'")
                for na in ma.get("names", []):
                    for nb in mb.get("names", []):
                        same = norm_display(na["name"], vocab) == norm_display(nb["name"], vocab) if na["kind"] == "display-name" \
                            else same_name(na["name"], nb["name"], na.get("route"), routes)
                        if same and na["kind"] == nb["kind"] \
                                and (na.get("route") or "maker-api") == (nb.get("route") or "maker-api") \
                                and any(overlap(x, y) for x in na["serves"] for y in nb["serves"]):
                            rep.err(lab["models"], f"identity: {a} and {b} ({maker}) both serve {na['kind']} '{na['name']}' over overlapping intervals")

    # routes.json
    makers = set(vocab["$defs"]["maker"].get("enum", []))
    for rid, r in routes.items():
        # per-provider records of a harness (registry fix, 26 Oct): via a registered route, a known maker, known keys
        recs = [("level_mapping", x) for x in r.get("level_mapping", [])] + [("mapping", x) for x in r.get("mapping", [])]
        recs += [(f"{k}/{f}", x) for k, rm in r.get("models", {}).items() for f in ("accepts", "mapping", "default")
                 for x in rm.get(f, [])]
        for what, x in recs:
            L = f"{lab['routes']} {rid} {what}"
            if x.get("via") and x["via"] not in routes:
                rep.err(L, f"via '{x['via']}' is not a registered route")
            if x.get("via") == rid:
                rep.err(L, "via names the route itself")
            if x.get("maker") and x["maker"] not in makers:
                rep.err(L, f"maker '{x['maker']}' is not a vocabulary maker")
            for k in x.get("models", []):
                if k not in models:
                    rep.err(L, f"model '{k}' not registered")
                elif what == "mapping" and x["served"] not in config_ids(models[k]) and \
                        not in_vocab(schemas, "mapping_result", x["served"]) and not x["served"].startswith("think-"):
                    rep.err(L, f"maps {x['requested']} to '{x['served']}', not one of {k}'s configurations")
        for key, rm in r.get("models", {}).items():
            L = f"{lab['routes']} {rid}/{key}"
            if key not in models:
                rep.err(L, "model key not registered")
                continue
            ids = config_ids(models[key])
            for a in rm.get("accepts", []):
                if a["configuration"] not in ids:
                    rep.warn(L, f"accepts '{a['configuration']}', not in the model's configurations {sorted(ids)}")
                else:
                    within_configuration(a, a["configuration"], models[key], "accepts", L, rep, route_entry=True)
            for mp in rm.get("mapping", []):
                if mp["served"] not in ids and not in_vocab(schemas, "mapping_result", mp["served"]):
                    rep.err(L, f"maps to '{mp['served']}', not one of the model's configurations")
            for d in rm.get("default", []):
                if d["configuration"] not in ids:
                    rep.err(L, f"default '{d['configuration']}' not one of the model's configurations {sorted(ids)}")
                else:
                    within_configuration(d, d["configuration"], models[key], "route default", L, rep, route_entry=True)
            for a_, b_ in overlapping_defaults(rm.get("default", [])):
                rep.err(L, f"defaults '{a_}' and '{b_}' overlap in time")

    # benchmarks.json
    for sid, s in setups.items():
        L = f"{lab['benchmarks']} {sid}"
        if s["family"] not in families:
            rep.err(L, f"family '{s['family']}' not registered")
        comp = s.get("composite")
        if comp:
            names = component_names(comp)
            for n, c in names:
                if c is not None and c not in setups:
                    rep.err(L, f"composite component '{c}' not registered")
            if len({n for n, _ in names}) != len(names):
                rep.err(L, "composite components with the same name")
            for c in comp["formula"]["weights"]:
                if c not in {n for n, _ in names}:
                    rep.err(L, f"weight for '{c}', not a component")
            if comp["linear"] is True and not comp["formula"]["weights"]:
                rep.err(L, "a linear composite without weights (write linear: \"unknown\" while they are not in hand)")
        if s["headline"]["basis"] == "decision" and not s["headline"].get("decision"):
            rep.warn(L, "headline pending a maintainer decision (the tree gives out:not-headline until then)")
        if s["headline"]["basis"] != "decision" and not s["headline"].get("evidence"):
            rep.err(L, "headline without evidence")

    # publishers.json
    for pid, p in (reg.get("publishers") or {}).get("publishers", {}).items():
        if p.get("maker") == "other":
            rep.err(f"{lab['publishers']} {pid}", "maker 'other' is never a publisher's maker (no home effect)")

    # prices.json
    prices = reg.get("prices")
    if prices:
        base, chosen = set(), collections.Counter()
        for i, p in enumerate(prices["prices"]):
            L = f"{lab['prices']} prices[{i}]"
            if p["model"] not in models:
                rep.err(L, f"model '{p['model']}' not registered")
            else:
                rel_ = models[p["model"]].get("released", {}).get("value")
                if rel_ and when(p["from"]) < when(rel_[:10]):
                    rep.err(L, f"priced from {p['from']}, before {p['model']}'s release {rel_}")
                for c in p.get("configurations", []):
                    if c not in config_ids(models[p["model"]]):
                        rep.err(L, f"price for configuration '{c}', not one of {p['model']}'s configurations")
            if p["route"] not in routes:
                rep.err(L, f"route '{p['route']}' not registered")
            elif p["kind"] == "standard" and routes[p["route"]]["class"] == "maker-api":
                if when(p["from"]) <= when(prices["as_of"]) <= when(p["to"], True):
                    base.add(p["model"])
            if p.get("to") is not None and when(p["to"]) > when(prices["as_of"], True):
                rep.err(L, f"to {p['to']} lies after as_of {prices['as_of']} (a price ends at its last capture)")
            if p["kind"] == "standard" and not p.get("classes"):
                rep.err(L, "standard price without classes")
            if p.get("base"):
                for c in p.get("configurations") or [None]:
                    chosen[(p["model"], c)] += 1
                if p["kind"] in ("promotion", "off-peak"):
                    rep.err(L, f"a {p['kind']} price is never the base")
        for (key, c), n in chosen.items():
            if n > 1 or (c is None and any(k == key and cc is not None for k, cc in chosen)):
                rep.err(lab["prices"], f"{key}: {n} entries marked base" + (f" for {c}" if c else "")
                        + ("" if n > 1 else " (one for every configuration, others per configuration)"))
        # configuration-dependent prices: entries of one model, route, kind and currency that overlap in time must
        # not share a configuration (an entry without `configurations` covers them all)
        groups = collections.defaultdict(list)
        for i, p in enumerate(prices["prices"]):
            groups[(p["model"], p["route"], p["kind"], p["currency"])].append((i, p))
        for g in groups.values():
            if not any(p.get("configurations") for _, p in g):
                continue
            for x, (i, a) in enumerate(g):
                for j, b in g[x + 1:]:
                    ca, cb = a.get("configurations"), b.get("configurations")
                    if overlap(a, b) and (ca is None or cb is None or set(ca) & set(cb)):
                        rep.err(f"{lab['prices']} prices[{i}]", f"overlaps prices[{j}] ({a['model']}, {a['kind']}) on a shared configuration")
        for key in sorted({p["model"] for p in prices["prices"]} - base - {k for k, _ in chosen}):
            rep.warn(lab["prices"], f"{key}: no standard maker-API price in force on as_of {prices['as_of']}")

    # price-tables.json
    for tid, t in ((reg.get("price-tables") or {}).get("tables") or {}).items():
        for i, c in enumerate(t["cards"]):
            if c["model"] not in models:
                rep.err(f"{lab['price-tables']} {tid}.cards[{i}]", f"model '{c['model']}' not registered")
            if c.get("route") and c["route"] not in routes:
                rep.err(f"{lab['price-tables']} {tid}.cards[{i}]", f"route '{c['route']}' not registered")

    # rules.json
    rules = reg.get("rules")
    if rules:
        seen = collections.Counter(r["id"] for r in rules["rules"])
        for k, n in seen.items():
            if n > 1:
                rep.err(lab["rules"], f"rule id {k} defined {n} times")

    # flag-map.json
    fm = reg.get("flag-map")
    if fm:
        meth = vocab["$defs"]["cost_method"]["x-terms"]
        for src, e in fm["cost_method_by_source"].items():
            if meth[e["method"]]["basis"] != e["basis"]:
                rep.err(f"{lab['flag-map']} {src}", f"basis {e['basis']} contradicts method {e['method']} (basis {meth[e['method']]['basis']})")


# ---------------------------------------------------------------- findings checks
def column_says(spec):
    says = spec if isinstance(spec, str) else spec["says"]
    return [says] if isinstance(says, str) else list(says)


# "k of N" in the source's language too: из (ru), von (de), sur (fr), de (es, pt), su / di (it) (27 Oct)
COUNTS = re.compile(r"\s*([0-9][0-9,]*)\s*(?:/|of|out of|из|von|sur|de|su|di)\s*([0-9][0-9,]*)\s*", re.I)


def check_source(src, path, reg, rep, schemas, vocab, check_files, all_ids):
    L = rel(path)
    V = vocab["$defs"]
    publishers = (reg.get("publishers") or {}).get("publishers", {})
    routes = (reg.get("routes") or {}).get("routes", {})
    ptables = (reg.get("price-tables") or {}).get("tables", {})
    if os.path.splitext(os.path.basename(path))[0] != src["id"]:
        rep.err(L, f"file name must be the source id '{src['id']}'")
    if src["publisher"] not in publishers:
        rep.err(L, f"publisher '{src['publisher']}' not registered in publishers.json")
    if src.get("snapshot_of") and src["snapshot_of"] not in all_ids:
        rep.err(L, f"snapshot_of '{src['snapshot_of']}' is not a source file")
    slug = src["publisher"].lower().replace("/", "_")
    if not src["id"].startswith(f"src-{slug}-"):
        rep.warn(L, f"id does not start with src-{slug}-")
    saved = src.get("sha256", {})
    forms = V["fact_form"]["x-terms"]
    closed = V["closed_term_fact_types"]["x-terms"]
    tables = {t["id"]: t for t in src.get("tables", [])}
    charts = {c["id"]: c for c in src.get("charts", [])}
    extracted = {e["from"]: e["file"] for e in src.get("extractions", [])}
    for kind, items in (("table", src.get("tables", [])), ("chart", src.get("charts", [])), ("fact", src.get("facts", [])),
                        ("capture", src.get("captures", []))):
        for k, n in collections.Counter(x["id"] for x in items).items():
            if n > 1:
                rep.err(L, f"{kind} id {k} used {n} times")
    for c in src.get("captures", []):
        if c.get("file") and c["file"] not in saved:
            rep.err(L, f"capture {c['id']}: file '{c['file']}' has no sha256 entry")
    for w in src.get("wayback", []):
        if not any(c.get("url") == w for c in src.get("captures", [])):
            rep.warn(L, f"wayback URL without a capture entry: {w}")
    for e in src.get("extractions", []):
        for k in ("file", "from"):
            if e[k] not in saved:
                rep.err(L, f"extraction: {k} '{e[k]}' has no sha256 entry")
    for t in list(tables.values()) + list(charts.values()):
        if t["file"] not in saved:
            rep.err(L, f"{t['id']}: file '{t['file']}' has no sha256 entry")
    for t in tables.values():
        if t.get("format") == "json" and parse_json_path(t["where"]) is None:
            rep.err(L, f"{t['id']}: a json table's where must be a JSON path ($, .key, ['key'], [n], [*]): {t['where']!r}")
        elif t.get("format") in ("yaml", "html", "other"):
            rep.warn(L, f"{t['id']}: {t['format']} tables are not read by the build yet (csv, json)")
        for col, spec in t["columns"].items():
            for says in column_says(spec):
                if says in closed and (isinstance(spec, str) or "term" not in spec):
                    rep.err(L, f"{t['id']}.{col}: a {says} column needs a term")
                elif says in closed and not in_vocab(schemas, closed[says]["vocab"], spec["term"]):
                    rep.err(L, f"{t['id']}.{col}: term '{spec['term']}' not in vocab {closed[says]['vocab']}")
                if says in ("score", "run-score") and (isinstance(spec, str) or "scale" not in spec):
                    rep.err(L, f"{t['id']}.{col}: a {says} column needs a scale")
                if says == "model-api-id" and (isinstance(spec, str) or "namespace" not in spec):
                    rep.err(L, f"{t['id']}.{col}: a model-api-id column needs a namespace")
                if not isinstance(spec, str) and spec.get("namespace") not in (None, "prefix") and spec["namespace"] not in routes:
                    rep.err(L, f"{t['id']}.{col}: namespace '{spec['namespace']}' not registered in routes.json")
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
        if f.get("quote") and (f.get("file") or "").lower().endswith(".pdf"):
            rep.err(F, "a quote in a PDF points at its text extraction (extractions), where it can be checked"
                       + (f": {extracted[f['file']]}" if f.get("file") in extracted else ""))
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
        if f["form"] in ("data-file", "legacy") and not (f.get("table") or f.get("file") or len(saved) == 1):
            rep.err(F, "a data-file fact names its table or file")
        if f["says"] in closed:
            if "term" not in f:
                rep.err(F, f"a {f['says']} fact needs a term (vocab {closed[f['says']]['vocab']})")
            elif not in_vocab(schemas, closed[f["says"]]["vocab"], f["term"]):
                rep.err(F, f"term '{f['term']}' not in vocab {closed[f['says']]['vocab']}")
        if f["says"] in ("score", "run-score") and "scale" not in f:
            rep.err(F, f"a {f['says']} fact needs its scale (fraction, percent, raw, counts)")
        if "scale" in f and f["says"] not in ("score", "run-score"):
            rep.err(F, "scale is for score facts")
        if f.get("scale") == "counts" and not COUNTS.fullmatch(f["value"]):
            rep.err(F, f"a counts score is written 'k of N', 'k/N' or 'k out of N', not {f['value']!r}")
        if (f["form"] == "legacy") != (f["says"] == "legacy-row"):
            rep.err(F, "a legacy-row fact has the form legacy, and only it")
        elif f["form"] == "legacy":
            leg = src.get("legacy")
            if not leg:
                rep.err(F, "a legacy fact needs the source's legacy block (file, columns)")
            else:
                rec = next(csv.reader([f["value"]]), [])
                if len(rec) != len(leg["columns"]):
                    rep.err(F, f"a legacy row has {len(rec)} fields, the CSV {len(leg['columns'])}")
        if (f["level"] == "computed") != bool(f.get("rule") or f.get("inputs")):
            rep.err(F, "a computed fact has its rule and inputs, and only a computed fact has them")
        elif f["level"] == "computed":
            need = 1 if f.get("rule") in ("chart-effort-order", "complement-of-percent") else 2
            if not f.get("rule") or len(f.get("inputs") or []) < need:
                rep.err(F, f"a computed fact needs its rule and at least {need} input(s)")
            for ref in f.get("inputs") or []:
                if ref == f["id"]:
                    rep.err(F, "a computed fact cannot be its own input")
                elif ref.startswith("T"):
                    t, _, col = split_cell(ref)
                    if t not in tables or col not in tables[t]["columns"]:
                        rep.err(F, f"input {ref}: table or column not declared")
                elif ref not in {x["id"] for x in src.get("facts", [])}:
                    rep.err(F, f"input {ref}: no such fact")
        if f["says"] == "run-date-convention":
            pat = f.get("pattern")
            try:
                ok = pat and "date" in re.compile(pat).groupindex
            except re.error:
                ok = False
            if not ok:
                rep.err(F, "a run-date-convention fact needs a pattern (regex) with a named group 'date' (YYYYMMDD)")
            if f["level"] == "written" and not forms.get(f["form"], {}).get("quote"):
                rep.err(F, "a run-date convention counts only as the source documents it (prose, code or label, quoted)")
        elif f.get("pattern"):
            rep.err(F, "pattern is for run-date-convention facts")
        if f["says"] == "price-tier" and f.get("term") == "standard":
            rep.err(F, "a price-tier fact names a tier other than standard")
        if f["says"] == "price-table" and f.get("term") is not None and f["term"] not in ptables:
            rep.err(F, f"price table '{f['term']}' is not registered in price-tables.json")
        if f["says"] == "run-score" and not f.get("run"):
            rep.err(F, "a run-score fact names its run (run)")
        if f.get("run") and f["says"] not in ("run-score", "failure", "partial"):
            rep.err(F, "run is for run-score, failure and partial facts")
        if f["says"] == "thinking-budget" and not re.fullmatch(r"[1-9][0-9]*", f.get("term", "")):
            rep.err(F, "a thinking-budget fact needs its token count as term (digits)")
        if f["says"] == "model-api-id":
            if "namespace" not in f:
                rep.err(F, "a model-api-id fact needs a namespace (a routes.json id, or prefix)")
            elif f["namespace"] != "prefix" and f["namespace"] not in routes:
                rep.err(F, f"namespace '{f['namespace']}' not registered in routes.json")
        if f["says"] == "route" and "term" in f and f["term"] not in routes:
            rep.err(F, f"route term '{f['term']}' not registered in routes.json")
    leg = src.get("legacy")
    if leg and leg["file"] not in saved:
        rep.err(L, f"legacy: file '{leg['file']}' has no sha256 entry")
    if check_files:
        check_saved(src, path, rep)


def check_saved(src, path, rep, lines_cache={}):
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
    leg = src.get("legacy")
    if leg and reach.get(leg["file"]):
        p = reach[leg["file"]]
        if stamp(p) not in lines_cache:
            with open(p, encoding="utf-8", newline="") as f:
                lines_cache[stamp(p)] = set(f.read().split("\n"))
        for f in src.get("facts", []):
            if f["form"] == "legacy" and f["value"] not in lines_cache[stamp(p)]:
                rep.err(f"{L} {f['id']}", "the legacy row is not a line of its CSV")
    for f in src.get("facts", []):
        p = reach.get(f.get("file")) if f.get("file") else only
        if f.get("quote") and p and p.endswith(TEXT_EXT) and not quote_in_file(f["quote"], p):
            rep.err(f"{L} {f['id']}", f"quote not found in the saved file {os.path.basename(p)}")


JSON_PATH_TOKEN = re.compile(r"\.([A-Za-z_$][A-Za-z0-9_$-]*)|\[([0-9]+)\]|\['([^']*)'\]|\[\"([^\"]*)\"\]|(\[\*\]|\.\*)")


def parse_json_path(path):
    """A JSON path of the subset $ . key ['key'] [n] [*] → its steps (str key, int index, '*'), or None."""
    if not isinstance(path, str) or not path.startswith("$"):
        return None
    steps, i, rest = [], 0, path[1:]
    while i < len(rest):
        m = JSON_PATH_TOKEN.match(rest, i)
        if not m:
            return None
        k, n, q1, q2, star = m.groups()
        steps.append("*" if star else int(n) if n is not None else (k if k is not None else q1 if q1 is not None else q2))
        i = m.end()
    return steps


def json_path(node, steps):
    """Nodes at the parsed JSON path."""
    nodes = [node]
    for st in steps:
        out = []
        for x in nodes:
            if st == "*":
                out += list(x.values()) if isinstance(x, dict) else list(x) if isinstance(x, list) else []
            elif isinstance(st, int):
                if isinstance(x, list) and st < len(x):
                    out.append(x[st])
            elif isinstance(x, dict) and st in x:
                out.append(x[st])
        nodes = out
    return nodes


def json_text(x):
    """A JSON scalar as text (numbers verbatim: the file is parsed with numbers kept as written)."""
    if x is None:
        return ""
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, (dict, list)):
        return json.dumps(x, ensure_ascii=False, sort_keys=True)
    return str(x)


def json_cell(row, column):
    """A column of a JSON row object: its key, else a dotted / JSON path inside it."""
    if isinstance(row, dict) and column in row:
        return json_text(row[column])
    steps = parse_json_path(column if column.startswith("$") else "$." + column)
    got = json_path(row, steps) if steps is not None else []
    return json_text(got[0]) if len(got) == 1 else None


def json_rows(table, p):
    """(columns found, {row key: {column: text}}) of a JSON table, or None when its path finds no rows."""
    steps = parse_json_path(table["where"])
    if steps is None:
        return None
    with open(p, encoding="utf-8") as f:
        doc = json.load(f, parse_float=str, parse_int=str)
    nodes = json_path(doc, steps)
    if len(nodes) == 1 and isinstance(nodes[0], (list, dict)) and not (steps and steps[-1] == "*"):
        nodes = list(nodes[0].items()) if isinstance(nodes[0], dict) else [(None, x) for x in nodes[0]]
    else:
        nodes = [(None, x) for x in nodes]
    rows, cols = {}, set()
    for key, obj in nodes:
        if not isinstance(obj, dict):
            continue
        rk = key if table["row_key"] == "$key" else json_cell(obj, table["row_key"])
        cells = {}
        for col in table["columns"]:
            v = json_cell(obj, col)
            if v is not None:
                cells[col] = v
                cols.add(col)
        if rk is not None:
            rows[rk] = cells
    return cols, rows


def table_rows(table, path, file=None, cache={}):
    """Rows of a CSV or JSON table keyed by its row_key, or None when not readable here."""
    p = saved_path(file or table["file"], path)
    fmt = table.get("format") or ("csv" if (p or "").endswith(".csv") else "json" if (p or "").endswith(".json") else None)
    if not p or fmt not in ("csv", "json"):
        return None
    key = (stamp(p), table["id"], table["row_key"])
    if key not in cache:
        if fmt == "json":
            cache[key] = json_rows(table, p)
        else:
            with open(p, encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
            cache[key] = (rows[0].keys() if rows else set(), {r.get(table["row_key"]): r for r in rows})
    return cache[key]


def ref_info(ref, facts, tables):
    """(fact types, about, metric term, record) of a cited fact or cell, or None."""
    if ref.startswith("T"):
        t, row, col = split_cell(ref)
        spec = tables.get(t, {}).get("columns", {}).get(col)
        if spec is None:
            return None
        return column_says(spec), row, (None if isinstance(spec, str) else spec.get("term")), spec
    f = facts.get(ref)
    return None if f is None else ([f["says"]], f["about"], f.get("term"), f)


def check_measures(ms, path, sources, reg, rep, vocab, check_files):
    L = rel(path)
    setups = (reg.get("benchmarks") or {}).get("setups", {})
    models = (reg.get("models") or {}).get("models", {})
    routes = (reg.get("routes") or {}).get("routes", {})
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
    captures = {c["id"]: c for c in src.get("captures", [])}
    slots = vocab["$defs"]["measure_slot"]["x-terms"]
    for k, n in collections.Counter(m["id"] for m in ms["measures"]).items():
        if n > 1:
            rep.err(L, f"measure id {k} used {n} times")
    values = collections.defaultdict(list)
    for m in ms["measures"]:
        if m["facts"].get("value"):
            values[m["facts"]["value"]].append(m["id"])
    for ref, ids in values.items():
        if len(ids) > 1:
            rep.err(L, f"value {ref} is cited by several measures: {', '.join(ids)}")
    for k, n in collections.Counter((m["legacy_ref"]["line"], m["legacy_ref"]["row_sha256"]) for m in ms["measures"]
                                    if m.get("legacy_ref")).items():
        if n > 1:
            rep.err(L, f"legacy_ref line {k[0]} is claimed by {n} measures")
    for m in ms["measures"]:
        M = f"{L} {m['id']}"
        if m["setup"] not in setups:
            rep.err(M, f"setup '{m['setup']}' not registered in benchmarks.json")
        if m["facts"].get("legacy"):
            if len(m["facts"]["legacy"]) != 1 or m["facts"].get("value") or m["facts"].get("model") or \
                    any(v for k, v in m["facts"].items() if k not in ("legacy", "value", "model")):
                rep.err(M, "a legacy measure cites its one legacy row and nothing else")
        elif m["facts"].get("value") is None and not m["facts"].get("spend"):
            rep.err(M, "a measure needs a value or a spend")
        for cid in m["facts"].get("value_seen_in", []):
            if cid not in captures:
                rep.err(M, f"value_seen_in: capture {cid} not defined in the source")
        info = {}
        for slot, ref in cited(m):
            allowed = slots[slot]["fact_types"]
            got = ref_info(ref, facts, tables)
            if got is None:
                if ref.startswith("T"):
                    t, row, col = split_cell(ref)
                    rep.err(M, f"{slot}: {ref}: " + (f"table {t} not defined" if t not in tables else f"column '{col}' not declared in {t}.columns"))
                else:
                    rep.err(M, f"{slot}: fact {ref} does not exist in {ms['source']}")
                continue
            says, about, term, rec = got
            info[(slot, ref)] = got
            if ref.startswith("T") and check_files:
                t, row, col = split_cell(ref)
                rows = table_rows(tables[t], spath)
                if rows:
                    cols, byrow = rows
                    if col not in cols:
                        rep.err(M, f"{ref}: column '{col}' not in the saved file")
                    elif row not in byrow:
                        rep.err(M, f"{ref}: no row '{row}' in the saved file")
                    elif not (byrow[row].get(col) or "").strip():
                        rep.err(M, f"{ref}: the cell is empty")
            if allowed is not None and not set(says) & set(allowed):
                rep.err(M, f"{slot}: {ref} is a '{'/'.join(says)}' fact, not one of {allowed}")
            if slot == "value" and not set(says) & {"score", "cost"}:
                rep.err(M, f"value {ref} is a '{'/'.join(says)}' fact")
        # the value and per-entry facts are about an entry a model fact names
        model_abouts = {g[1] for (slot, _), g in info.items() if slot == "model" and g[1] is not None}
        for (slot, ref), (says, about, term, rec) in info.items():
            if slot in ("value", "runs", "spend", "usage", "judge", "anomalies") and about is not None and model_abouts \
                    and about not in model_abouts:
                rep.err(M, f"{slot}: {ref} is about '{about}', not an entry the measure's model facts name {sorted(model_abouts)}")
        # the value's metric is the setup's metric
        v = m["facts"].get("value")
        if v and ("value", v) in info and m["setup"] in setups:
            says, about, term, rec = info[("value", v)]
            if "score" in says and term != setups[m["setup"]]["metric"]:
                rep.err(M, f"value {v} is on metric '{term}', the setup '{m['setup']}' on '{setups[m['setup']]['metric']}'")
        # per-run values: on the setup's metric; a failure or partial naming a run names one of them
        run_ids = set()
        for (slot, ref), (says, about, term, rec) in info.items():
            if slot != "runs":
                continue
            run_ids.add(split_cell(ref)[1] if ref.startswith("T") else rec.get("run"))
            if m["setup"] in setups and term != setups[m["setup"]]["metric"]:
                rep.err(M, f"runs: {ref} is on metric '{term}', the setup on '{setups[m['setup']]['metric']}'")
        for (slot, ref), (says, about, term, rec) in info.items():
            run = split_cell(ref)[1] if (slot == "anomalies" and ref.startswith("T") and run_ids) else \
                (rec.get("run") if not ref.startswith("T") else None)
            if slot == "anomalies" and run and run not in run_ids:
                rep.err(M, f"anomalies: {ref} names run {run!r}, not one of the runs cited {sorted(r for r in run_ids if r)}")
        # model facts resolve under the name rule (any date: the run date is the build's)
        for (slot, ref), (says, about, term, rec) in info.items():
            if slot != "model":
                continue
            value = rec.get("value") if not ref.startswith("T") else split_cell(ref)[1]
            if "model-api-id" in says:
                ns = rec.get("namespace")
                cell = None
                if ref.startswith("T") and check_files:
                    t, row, col = split_cell(ref)
                    rows = table_rows(tables[t], spath)
                    cell = rows[1].get(row, {}).get(col) if rows else None
                if ref.startswith("T") and cell is None:
                    continue
                keys = resolve_api_id(cell if cell is not None else value, ns, models, routes)
                if len(keys) != 1:
                    rep.warn(M, f"model {ref} ({cell or value!r}, namespace {ns}) resolves to {sorted(keys) or 'no key'}")
            elif "model-name" in says and not ref.startswith("T"):
                n = norm_display(value, vocab)
                keys = {k for k, mm in models.items() for nm in mm.get("names", [])
                        if nm["kind"] == "display-name" and norm_display(nm["name"], vocab) == n}
                if len(keys) != 1:
                    rep.warn(M, f"model {ref} ({value!r}) resolves to {sorted(keys) or 'no key'} under the display-name rule")
        # with the files: a value cell must read the same in every capture said to carry it
        if check_files and v and v.startswith("T"):
            t, row, col = split_cell(v)
            base = table_rows(tables[t], spath)
            for cid in m["facts"].get("value_seen_in", []):
                c = captures.get(cid)
                if not c or not c.get("file") or c["file"] == tables[t]["file"]:
                    continue
                other = table_rows(tables[t], spath, c["file"])
                if base and other and (other[1].get(row) or {}).get(col) != (base[1].get(row) or {}).get(col):
                    rep.err(M, f"value_seen_in {cid}: {row}/{col} reads {(other[1].get(row) or {}).get(col)!r} there, "
                               f"{(base[1].get(row) or {}).get(col)!r} in {os.path.basename(tables[t]['file'])}")


def check_decisions(dec, path, sources, measures, reg, rep):
    L = rel(path)
    setups = (reg.get("benchmarks") or {}).get("setups", {})
    for d in dec["decisions"]:
        if d.get("kind") == "headline":
            if d["setup"] not in setups:
                rep.err(f"{L} {d['id']}", f"setup '{d['setup']}' not registered")
            continue
        entries, ok = [], True
        for mref in d["measures"]:
            sid, mid = mref.split("#")
            m = measures.get((sid, mid))
            if not m:                                    # renumbered or retired: reported, not applied
                rep.warn(f"{L} {d['id']}", f"measure {mref} not found: the decision is reported, not applied")
                ok = False
                continue
            entries.append(facts_hash(sources[sid][1], m, mref))
        if ok and hash_of(entries) != d["facts_hash"]:
            rep.warn(f"{L} {d['id']}", "facts_hash no longer matches: the decision is reported, not applied")
    heads = {d["id"]: d for d in dec["decisions"] if d.get("kind") == "headline"}
    for sid, s in setups.items():
        h = s["headline"]
        if h.get("decision"):
            d = heads.get(h["decision"])
            if not d:
                rep.err(f"{L}", f"setup {sid}: headline decision {h['decision']} not found (kind headline)")
            elif d["setup"] != sid or d["metric"] != h["metric"]:
                rep.err(f"{L} {d['id']}", f"decides {d['setup']} / {d['metric']}, the setup says {sid} / {h['metric']}")


# ---------------------------------------------------------------- legacy coverage
def legacy_coverage(csv_path, vocab, flag_map):
    V = vocab["$defs"]
    meth = V["cost_method"]
    order = [(m, re.compile(meth["x-terms"][m]["legacy_flags"], re.I)) for m in meth["x-order"]]
    subs = re.compile(V["cost_basis"]["x-terms"]["subscription"]["legacy_flags"], re.I)
    by_source = (flag_map or {}).get("cost_method_by_source", {})
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    cost = [r for r in rows if (r.get("cost_usd") or "").strip()]
    per, unmapped_src, unmapped_flags = collections.Counter(), collections.Counter(), collections.Counter()
    for r in cost:
        t = r.get("confound") or ""
        e = by_source.get(r["source"])
        if e and e.get("groups") and r["group"] not in e["groups"]:
            e = None
        m = e["method"] if e and e["applies"] == "all" else next((m for m, p in order if p.search(t)), None)
        if m is None and e:
            m = e["method"]
        per[m or ("(subscription basis only)" if subs.search(t) else None)] += 1
        if m is None:
            unmapped_src[r["source"]] += 1
            for tok in re.split(r";\s*", t):
                head = re.split(r"[:=(]", tok.strip())[0].strip()[:50]
                if re.search(r"cost|price|bill|spend|usd", head, re.I):
                    unmapped_flags[head] += 1
    print(f"rows with a cost: {len(cost)}; flag-map per-source entries: {len(by_source)}")
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
    ap.add_argument("--registry-files-checked", action="store_true",
                    help="with --check-files: check the findings' saved copies, not the registry's evidence (unchanged registry)")
    ap.add_argument("--hash", nargs="+", metavar="MEASURE_REF", help="print the facts_hash of these measures (one decision)")
    ap.add_argument("--legacy-coverage", metavar="RAW_DATA_CSV", help="report how vocab's legacy patterns (and --flag-map) map today's flags")
    ap.add_argument("--verbose", action="store_true", help="list every file checked and every registry warning")
    ap.add_argument("--flag-map", help="flag-map.json for --legacy-coverage (default: <registry>/flag-map.json when present)")
    a = ap.parse_args()
    rep, schemas = Report(), Schemas(HERE)
    rep.registry, rep.verbose = rel(a.registry), a.verbose
    vocab = schemas.doc("vocab.json")
    if a.legacy_coverage:
        fmp = a.flag_map or os.path.join(a.registry, "flag-map.json")
        fm = load_json(fmp, rep) if os.path.isfile(fmp) else None
        if fm is not None and not schemas.validate(fm, "flag-map.schema.json", rel(fmp), rep):
            return rep.done()
        return legacy_coverage(a.legacy_coverage, vocab, fm)
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
            if k != "price-tables":                     # optional, and usually absent
                (rep.err if k in REQUIRED_REGISTRIES else rep.warn)(rel(a.registry), f"no {name}")
            continue
        x = load_json(p, rep)
        if x is not None and schemas.validate(x, schema_of[k], rel(p), rep):
            reg[k] = x
        rep.checked.append(rel(p))
    if all(k in reg for k in REQUIRED_REGISTRIES):
        check_registries(reg, rep, schemas, vocab, paths, a.check_files and not a.registry_files_checked)

    sources, measures = {}, {}
    files = sorted(glob.glob(os.path.join(a.findings, "sources", "*.json")))
    loaded = [(p, load_json(p, rep)) for p in files]
    all_ids = {x.get("id") for _, x in loaded if isinstance(x, dict)}
    for p, x in loaded:
        rep.checked.append(rel(p))
        if x is not None and schemas.validate(x, "source.schema.json", rel(p), rep):
            if x["id"] in sources:
                rep.err(rel(p), f"source id {x['id']} also in {rel(sources[x['id']][0])}")
            sources[x["id"]] = (p, x)
            check_source(x, p, reg, rep, schemas, vocab, a.check_files, all_ids)
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
            check_decisions(x, a.decisions, sources, measures, reg, rep)
    else:
        for sid, s in (reg.get("benchmarks") or {}).get("setups", {}).items():
            if s["headline"].get("decision"):
                rep.err(rel(paths["benchmarks"]), f"setup {sid}: headline decision {s['headline']['decision']} but no decisions file")
    return rep.done()


if __name__ == "__main__":
    sys.exit(main())
