"""A small scenario builder for the build's tests: registries, sources, measures and decisions written to a temporary
folder, then data/build.py run on it. Every fact is a data-file fact of one saved file (no quote needed) unless a test
says otherwise; run with --no-check-files (the saved file is a placeholder), except the cell tests, which write a real
CSV with its sha256."""
import hashlib, json, os, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.dirname(HERE)
sys.path.insert(0, DATA)
sys.path.insert(0, os.path.join(DATA, "schema"))
import build  # noqa: E402
import validate as V  # noqa: E402

EV = [{"url": "https://example.org/doc", "where": "fixture"}]


def iv(frm, to=None, **kw):
    d = {"from": frm, "to": to, "evidence": EV}
    d.update(kw)
    return d


def name(n, frm="2026-01-01", to=None, route=None, selects=None, kind="api-id"):
    return {"name": n, "kind": kind, "selects": selects, "route": route,
            "serves": [iv(frm, to, from_basis="release", to_basis="open" if to is None else "stated")]}


def price(model, frm, to, classes, kind="standard", route="maker-api", currency="USD", **kw):
    d = dict(iv(frm, to), model=model, route=route, kind=kind, currency=currency, per="MTok", classes=classes)
    d.update(kw)
    return d


class Sc:
    def __init__(self, as_of="2026-10-01"):
        self.models = {}
        self.routes = {"maker-api": {"class": "maker-api", "label": "maker", "operator": None,
                                     "name_prefixes": ["mk/"], "models": {}}}
        self.setups, self.families = {}, {}
        self.publishers = {"pubx": {"label": "X", "maker": None}, "puby": {"label": "Y", "maker": None}}
        self.prices = {"as_of": as_of, "prices": []}
        self.decisions = []
        self.sources, self.msets = {}, {}
        self.class_ratios = None
        self.cells = {}                     # source id → (file name, csv text)
        self.after_hash = []                # edits applied after the decisions' hashes (stale test)

    # -- registries
    def model(self, key, configs=("low", "medium", "high"), released="2026-01-01", names=None, default=None,
              maker="anthropic", conversions=None, modes=None, line=None):
        cfgs = []
        for c in configs:
            if isinstance(c, dict):
                cfgs.append(c)
            else:
                d = dict(iv(released[:10], None, from_basis="release", to_basis="open"), id=c, served="itself")
                if c == "think-<budget>":
                    d.update(budget_min=1024, budget_max=None)
                cfgs.append(d)
        self.models[key] = dict(label=key.upper(), maker=maker, released={"value": released, "evidence": EV},
                                line=line, open_weights=False, configurations=cfgs,
                                names=names or [name(key, released[:10])], default=default or [],
                                conversions=conversions or [], modes=modes or [])
        return key

    def route(self, rid, cls, spellings=(), prefixes=(), models=None, level_mapping=None):
        self.routes[rid] = {"class": cls, "label": rid, "operator": None, "spellings": list(spellings),
                            "name_prefixes": list(prefixes), "models": models or {}}
        if level_mapping:
            self.routes[rid]["level_mapping"] = level_mapping

    def setup(self, sid, metric="pass%", bounds=(0, 100), kind="runs", headline=None, family="fam", composite=None):
        self.families.setdefault(family, {"label": family})
        self.setups[sid] = dict(family=family, benchmark=sid, metric=metric,
                                headline=headline or {"metric": metric, "basis": "designated", "evidence": EV},
                                bounds=list(bounds) if bounds else None, direction="higher", task_type="coding",
                                complexity="mid", kind=kind, composite=composite)
        return sid

    # -- findings
    def source(self, what, publisher="pubx", published="2026-06-01", snapshot_of=None, captures=None, commit=None,
               harvested="2026-10-01T00:00:00Z"):
        sid = f"src-{publisher}-{what}-{(published or '2026-06-01')[:10]}"
        self.sources[sid] = dict(
            id=sid, publisher=publisher, urls=[f"https://example.org/{what}"], wayback=[], commit=commit,
            sha256={"saved.txt": "0" * 64}, harvested_at=harvested,
            published={"value": published, "where": "head"} if published else None, salvo="tests", agent="tests",
            snapshot_of=snapshot_of, captures=captures or [], facts=[])
        self.msets[sid] = []
        return sid

    def fact(self, sid, says, value, about=None, level="written", form="data-file", **kw):
        doc = self.sources[sid]
        fid = f"F{len(doc['facts']) + 1}"
        f = dict(id=fid, says=says, about=about, value=value, level=level, form=form, where=f"fixture {fid}",
                 file="saved.txt")
        f.update(kw)
        doc["facts"].append(f)
        return fid

    def m(self, sid, setup="s1", model="ma", score="50%", scale="percent", effort=(), cost=None, currency="USD",
          unit="per-task", basis=None, method=None, tokens=None, run_date=(), route=(), anomalies=(), version=None,
          value_level="written", entry=None, value_seen_in=(), price_table=None, model_says="model-api-id",
          namespace="maker-api", early_access=False, same_runs_as=None, restated_from=None, evaluated_by=None,
          mode=None, cost_level="written", value_form="data-file", spend_shared=None):
        n = len(self.msets[sid]) + 1
        entry = entry or f"{model}-{n}"
        F = lambda says, value, about=entry, **kw: self.fact(sid, says, value, about=about, **kw)  # noqa: E731
        kwm = {"namespace": namespace} if model_says == "model-api-id" else {}
        model_f = [F(model_says, model, **kwm)]
        if mode:
            model_f.append(F("mode", mode))
        value = None
        metric = self.setups[setup]["metric"]
        if score is not None:
            extra = {} if value_form == "data-file" else {"form": value_form}
            value = F("score", score, term=metric, scale=scale, level=value_level, **extra)
        eff = []
        for e in effort:
            says, v = e[0], e[1]
            kw = dict(e[2]) if len(e) > 2 else {}
            if says == "thinking-budget":
                kw.setdefault("term", "".join(ch for ch in v if ch.isdigit()))
            eff.append(F(says, v, about=kw.pop("about", entry), **kw))
        spend = []
        if spend_shared is not None:
            spend = list(spend_shared)
        elif cost is not None:
            spend.append(F("cost", cost, level=cost_level))
            if currency:
                spend.append(F("currency", currency, about=None, term=currency))
            if unit:
                spend.append(F("unit", unit, about=None, term=unit))
            if basis:
                spend.append(F("cost-basis", basis, about=None, term=basis))
            if method:
                spend.append(F("cost-method", method, about=None, term=method))
            if price_table:
                spend.append(F("price-table", price_table, about=None))
        if score is None and spend:
            value = spend[0]
        usage = []
        for says, v in (tokens or {}).items():
            usage.append(F(says, v))
        rd = [F(says, v) for says, v in run_date]
        rt = [F("route", v, about=None, **({"term": t} if t else {})) for v, t in route]
        an = [F(says, v, level=lv) for says, v, lv in anomalies]
        facts = {"value": value, "model": model_f, "effort": eff, "run_date": rd, "usage": usage, "spend": spend,
                 "version": F("version", version, about=None) if version else None, "judge": None,
                 "anomalies": an, "restated_from": F("restated-from", restated_from, about=None) if restated_from
                 else None, "same_runs_as": F("same-runs-as", same_runs_as, about=None) if same_runs_as else None,
                 "route": rt, "value_seen_in": list(value_seen_in)}
        if early_access:
            facts["early_access"] = [F("early-access", "early access", about=None)]
        if evaluated_by:
            facts["evaluated_by"] = [F("evaluated-by", evaluated_by, about=None)]
        self.msets[sid].append({"id": f"M{n}", "setup": setup, "facts": facts, "verified": None})
        return f"{sid}#M{n}"

    def decide(self, mref, axis, status, reason="test decision"):
        sid, mid = mref.split("#")
        self.decisions.append(dict(id=f"D{len(self.decisions) + 1}", measures=[mref], axis=axis, status=status,
                                   reason=reason, date="2026-10-22", _ref=(sid, mid)))

    # -- write and run
    def write(self, root):
        reg = os.path.join(root, "registry")
        fnd = os.path.join(root, "findings")
        for d in (reg, os.path.join(fnd, "sources"), os.path.join(fnd, "measures")):
            os.makedirs(d, exist_ok=True)
        dump = lambda p, x: json.dump(x, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)  # noqa: E731
        dump(os.path.join(reg, "models.json"), {"models": self.models})
        dump(os.path.join(reg, "routes.json"), {"routes": self.routes})
        dump(os.path.join(reg, "benchmarks.json"), {"families": self.families, "setups": self.setups})
        dump(os.path.join(reg, "publishers.json"), {"publishers": self.publishers})
        dump(os.path.join(reg, "prices.json"), self.prices)
        if self.class_ratios:
            dump(os.path.join(reg, "class-ratios.json"), self.class_ratios)
        with open(os.path.join(fnd, "sources", "saved.txt"), "w") as f:
            f.write("placeholder\n")
        for doc in self.sources.values():
            doc["sha256"]["saved.txt"] = hashlib.sha256(b"placeholder\n").hexdigest()
        for sid, (fname, text, bad_sha) in self.cells.items():
            p = os.path.join(fnd, "sources", fname)
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            self.sources[sid]["sha256"][fname] = "0" * 64 if bad_sha else hashlib.sha256(text.encode()).hexdigest()
        decs = []
        for d in self.decisions:
            d = dict(d)
            if "_ref" in d:
                sid, mid = d.pop("_ref")
                m = next(x for x in self.msets[sid] if x["id"] == mid)
                d["facts_hash"] = V.hash_of([V.facts_hash(self.sources[sid], m, f"{sid}#{mid}")])
            decs.append(d)
        for fn in self.after_hash:
            fn(self)
        for sid, doc in self.sources.items():
            dump(os.path.join(fnd, "sources", f"{sid}.json"), doc)
            if self.msets[sid]:
                dump(os.path.join(fnd, "measures", f"{sid}.json"), {"source": sid, "measures": self.msets[sid]})
        dec = os.path.join(root, "decisions.json")
        if decs:
            dump(dec, {"decisions": decs})
        return reg, fnd, dec

    def run(self, *extra, lqm=False, check_files=False, keep=None):
        root = tempfile.mkdtemp(prefix="buildtest-")
        try:
            reg, fnd, dec = self.write(root)
            out = os.path.join(root, "build")
            argv = ["--registry", reg, "--findings", fnd, "--decisions", dec, "--out", out, *extra]
            if not check_files:
                argv.append("--no-check-files")
            if not lqm:
                argv.append("--no-lqm")
            import contextlib, io
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                code = build.main(argv)
            if code != 0:
                raise AssertionError(f"build failed:\n{buf.getvalue()}")
            res = Result(out)
            if keep:
                shutil.copytree(out, keep, dirs_exist_ok=True)
            return res
        finally:
            shutil.rmtree(root, ignore_errors=True)


class Result:
    def __init__(self, out):
        with open(os.path.join(out, "status-report.json"), encoding="utf-8") as f:
            self.rep = json.load(f)
        import csv
        self.tables = {}
        for n in ("fit-quality.csv", "fit-cost.csv", "data.csv"):
            with open(os.path.join(out, n), encoding="utf-8") as f:
                self.tables[n] = list(csv.DictReader(f))
        with open(os.path.join(out, "group-map.json"), encoding="utf-8") as f:
            self.group_map = json.load(f)

    def __getitem__(self, ref):
        return self.rep["measures"][ref]

    def q(self, ref):
        return self[ref]["status"]["quality"]

    def c(self, ref):
        return self[ref]["status"]["cost"]

    def cfg(self, ref):
        return self[ref]["fields"]["configuration"]["value"]

    def model(self, ref):
        return self[ref]["fields"]["model"]["value"]

    def rows(self, table, **kw):
        return [r for r in self.tables[table] if all(r.get(k) == v for k, v in kw.items())]
