"""Tests of the fixes after the ObviousBench pilot conversion (/work/.salvo14/mig/convert-obviousbench/report.md §4–6)
and the coordinator's build rules of 23 Oct: legacy setup and publisher supplied, legacy_ref and the diff keyed by it,
the boolean reasoning-included-in-out, precision per column, computed facts, model contradictions and their report,
validate.py's per-file summary, the converter toolkit (data/convert/), cost reproduction, run dates from a documented
id convention, and Flex / batch tier costs. data/tests/run.py runs them."""
import contextlib, csv, hashlib, io, json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fixtures import Sc, iv, name, price, EV, build, DATA  # noqa: E402
sys.path.insert(0, DATA)
import legacy as LG  # noqa: E402
from convert import mapping, rules, reproduce, precheck, gaps  # noqa: E402

TESTS = []


def test(f):
    f.__name__ = "pilot_" + f.__name__
    TESTS.append(f)
    return f


def eq(got, want, what=""):
    if got != want:
        raise AssertionError(f"{what}: got {got!r}, want {want!r}")


LOW, HIGH, MED = ("effort-setting", "low"), ("effort-setting", "high"), ("effort-setting", "medium")
WIN = dict(from_basis="earliest-capture", to_basis="last-capture")
HEAD = ("group,source,model,effort,task_type,complexity,harness,unit,cost_usd,cost_prec,tokens_in,tokens_out,score,"
        "score_metric,score_prec,cached_pct,confound,ref")


def base(as_of="2026-10-01"):
    sc = Sc(as_of)
    sc.model("ma")
    sc.model("mb")
    sc.setup("s1")
    return sc


def same_price(sc, *models, classes=None):
    for k in models:
        sc.prices["prices"].append(price(k, "2026-01-01", "2026-10-01", classes or {"input": 1, "output": 5}))


def write_csv(root, rows):
    p = os.path.join(root, "raw.csv")
    with open(p, "w") as f:
        f.write(HEAD + "\n" + "\n".join(rows) + "\n")
    return p


# ---------------------------------------------------------------- 1, 2: legacy setup supplied, legacy_ref, diff
@test
def legacy_ref_replaces_and_diff():
    rows = ["g1,srcR,ma,low,coding,mid,h,per-task,,,,,50.0,pass%,,,,r1",
            "g1,srcR,mb,low,coding,mid,h,per-task,,,,,60.0,pass%,,,,r2",
            "g1,srcR,ma,high,coding,mid,h,per-task,,,,,70.0,pass%,,,,r3"]
    root = tempfile.mkdtemp(prefix="pilot-")
    try:
        csvp = write_csv(root, rows)
        sha = lambda line: hashlib.sha256(line.encode()).hexdigest()  # noqa: E731
        sc1 = base()
        sc1.before_build.append(lambda fnd: LG.convert(csvp, fnd))
        prev = os.path.join(root, "prev")
        r1 = sc1.run(keep=prev)
        eq(sorted(r1.rep["build"]["supplied"]), ["benchmarks.families.legacy", "benchmarks.setups.legacy",
                                                 "publishers.legacy"], "the build supplies the legacy setup/publisher")
        eq(len(r1.rows("fit-quality.csv")), 3, "legacy rows in")
        sc2 = base()
        sc2.before_build.append(lambda fnd: LG.convert(csvp, fnd))
        s = sc2.source("conv")
        m1 = sc2.m(s, model="ma", effort=[LOW], score="55.0%", measure_keys={"legacy_ref": {"line": 2, "row_sha256": sha(rows[0])}})
        m2 = sc2.m(s, model="mb", effort=[LOW], score="60.0%", measure_keys={"legacy_ref": {"line": 3, "row_sha256": sha(rows[1])}})
        m3 = sc2.m(s, model="ma", effort=[MED], score="58.0%")
        r2 = sc2.run("--previous", os.path.join(prev, "status-report.json"))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    leg = {e["line"]: e["status"]["quality"] for e in r2.rep["measures"].values() if e.get("kind") == "legacy"}
    eq(leg, {2: "legacy:out:replaced", 3: "legacy:out:replaced", 4: "legacy:in"}, "rows claimed by a legacy_ref")
    eq(len(r2.rows("fit-quality.csv", model="ma", effort="low")), 1, "the row counts once")
    d = r2.rep["diff"]["by_legacy_ref"]["srcR"]
    ch = {c["line"]: c["changes"] for c in d["changed"]}
    eq(ch[2]["score"], ["50.0", "55.0"], "value change on the replaced row")
    eq(ch[2]["group"], ["g1", "s1"], "group change")
    eq(ch[3]["status_quality"], ["legacy:in", "in"], "status change")
    eq([x["line"] for x in d["unmatched_old"]], [4], "a legacy row no measure claims")
    eq([x["measure"] for x in d["unmatched_new"]], [m3], "a converted measure claiming no row")


@test
def legacy_build_against_real_registry():
    """The legacy findings add no error of their own against data/registry (the build supplies the legacy setup and
    publisher); the build runs when the registry itself validates, and otherwise stops on the registry's own errors
    only (the registry review's items, 23 Oct)."""
    root = tempfile.mkdtemp(prefix="pilot-")
    try:
        csvp = write_csv(root, ["obvbench,github-obviousbench,opus-5.5,low,coding,mid,h,per-task,0.3,,,,95.8,answer_pass3%,,,,r"])
        fnd = os.path.join(root, "f")
        LG.convert(csvp, fnd)
        out = os.path.join(root, "b")
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = build.main(["--registry", os.path.join(DATA, "registry"), "--findings", fnd, "--decisions",
                               os.path.join(root, "none.json"), "--out", out, "--no-check-files", "--no-lqm"])
        lines = [l for l in err.getvalue().splitlines()[1:] if l.strip()]
        eq([l for l in lines if not l.startswith(os.path.relpath(os.path.join(DATA, "registry"), build.REPO))], [],
           "no error outside the registry's own files")
        if code == 0:
            e = next(iter(json.load(open(os.path.join(out, "status-report.json")))["measures"].values()))
            eq(e["kind"], "legacy", "legacy measure")
        reg = {k: json.load(open(os.path.join(DATA, "registry", f))) for k, f in (("benchmarks", "benchmarks.json"),
                                                                                  ("publishers", "publishers.json"))}
        sup = build.Ctx.supply_legacy(reg, fnd)
        eq(("legacy" in reg["benchmarks"]["setups"], "legacy" in reg["publishers"]["publishers"]), (True, True),
           f"supplied: {sup}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------- 3: reasoning-included-in-out as a boolean
@test
def reasoning_included_boolean():
    old, new = {"input": 1, "output": 5, "cache-read": 0.1}, {"input": 1, "output": 5, "cache-read": 0.05}
    out = {}
    for term in ("false", "true"):
        sc = base()
        for k in ("ma", "mb"):
            sc.prices["prices"] += [price(k, "2026-01-01", "2026-06-30", old), price(k, "2026-07-01", "2026-10-01", new)]
        s = sc.source("a")
        tok = {"tokens-in": "1000000", "tokens-out": "100000", "tokens-reasoning": "100000", "tokens-cache-read": "2000000"}
        more = {"usage": [("reasoning-included-in-out", "output (thinking included)" if term == "true" else
                           "reasoning billed apart", {"term": term, "about": None})]}
        m1 = sc.m(s, model="ma", effort=[LOW], cost="2.20", tokens=tok, price_table="list prices of 1 June 2026", more=more)
        sc.m(s, model="mb", effort=[LOW], cost="2.20", tokens=tok, price_table="list prices of 1 June 2026", more=more)
        out[term] = sc.run()[m1]["fields"]["cost"]
    eq(round(out["false"]["base"]["value"], 6), 2.1, "false: reasoning added to output, the formula reproduces 2.20")
    eq(out["true"]["base"], None, "true: inside output, the formula gives 1.70, not 2.20: not re-priced by delta")
    eq((out["false"]["reasoning_included"], out["true"]["reasoning_included"]), (False, True), "read as booleans")


# ---------------------------------------------------------------- 4: precision per column
@test
def precision_per_column():
    sc = base()
    s = sc.source("t")
    sc.prices["prices"] += [price(k, "2026-01-01", "2026-10-01", {"input": 1, "output": 5}) for k in ("ma", "mb")]
    sc.cells[s] = ("saved/t.csv", "id,model,eff,score,cost\ne1,ma,low,72,0.31\ne2,mb,low,80,0.42\n", False)
    sc.sources[s]["tables"] = [{"id": "T1", "file": "saved/t.csv", "where": "t.csv", "format": "csv", "row_key": "id",
                                "precision": {"model": "printed", "step": 1},
                                "columns": {"model": {"says": "model-api-id", "namespace": "maker-api"},
                                            "eff": "effort-setting",
                                            "score": {"says": "score", "term": "pass%", "scale": "percent",
                                                      "precision": {"model": "exact"}},
                                            "cost": "cost"}}]
    cur = sc.fact(s, "currency", "$", term="USD")
    for i, e in enumerate(("e1", "e2"), 1):
        sc.msets[s].append({"id": f"M{i}", "setup": "s1", "verified": None, "facts": {
            "value": f"T1/{e}/score", "model": [f"T1/{e}/model"], "effort": [f"T1/{e}/eff"],
            "spend": [f"T1/{e}/cost", cur]}})
    r = sc.run(check_files=True)
    row = r.rows("fit-quality.csv", model="ma")[0]
    eq(row["score_prec"], "0", "the score column is exact")
    eq(r.rows("fit-cost.csv", model="ma")[0]["cost_prec"], "0.289", "the cost column takes the table's (step 1)")


# ---------------------------------------------------------------- 5: computed facts
@test
def computed_fact():
    for stated, want in (("75%", "in"), ("74%", "out:no-proof")):
        sc = base()
        s = sc.source("a")
        fa = sc.fact(s, "items", "80", about="ma-1")
        fb = sc.fact(s, "items", "5", about="ma-1")
        m1 = sc.m(s, model="ma", effort=[LOW], score=stated, value_level="computed",
                  value_kw={"rule": "cell-difference", "inputs": [fa, fb]})
        sc.m(s, model="mb", effort=[LOW], score="60%")
        r = sc.run()
        eq(r.q(m1), want, f"stated {stated}, inputs 80 − 5")
    eq(r[m1]["reason_detail"]["quality"].count("its inputs give 75"), 1, "why")
    sc = base()
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], score="75%", value_level="computed")       # no rule, no inputs
    r = sc.run()
    eq((r.q(m1), any("a computed fact has its rule and inputs" in e for e in r.rep["validation"]["errors"])),
       ("out:no-proof", True), "validate.py: a computed fact names its rule and inputs")


# ---------------------------------------------------------------- 6: model contradictions and the report
@test
def model_contradictions_reported():
    sc = base()
    sc.model("mp", modes=[dict(iv("2026-01-01", "2026-12-31", **WIN), parameter="pro", key="mp-pro"),
                          dict(iv("2026-01-01", "2026-12-31", **WIN), parameter="deep", key="mp-deep")])
    sc.model("mp-pro", line="mp")
    sc.model("mp-deep", line="mp")
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], model_facts=[("model-api-id", "mb", {"namespace": "maker-api"})])
    m2 = sc.m(s, model="ma", effort=[LOW], model_facts=[("model-api-id", "ma-pro-x", {"namespace": "maker-api"})])
    m3 = sc.m(s, model="mp", effort=[LOW], mode="pro", model_facts=[("mode", "deep", {})],
              route=[("Maker API", "maker-api")])
    m4 = sc.m(s, model="mp", effort=[LOW], mode="pro", route=[("Maker API", "maker-api")])
    r = sc.run()
    f1 = r[m1]["fields"]["model"]
    eq(f1["level"], "not-established:contradictory", "two facts, two keys")
    eq([x["outcome"] for x in f1["resolution"]], ["decided", "contradicts: gives mb"], "which fact said what")
    f2 = r[m2]["fields"]["model"]
    eq((f2["value"], f2["level"]), (None, "not-established:absent"), "a second fact resolving to no key: refused")
    eq(f2["detail"].startswith("unresolved model fact 'ma-pro-x'"), True, "the reason names it")
    eq(f2["resolution"][1]["outcome"].startswith("unresolved"), True, "the other: why it did not decide")
    eq(r.q(m2), "out:model-not-established", "doubt → out")
    eq(r[m3]["fields"]["model"]["level"], "not-established:contradictory", "two modes selecting two keys")
    eq(r.model(m4), "mp-pro", "one mode: its line's key")


@test
def router_chain_has_no_maker_step():
    sc = base()
    conv = [dict(iv("2026-01-01", "2026-12-31", **WIN), route="maker-api", requested="max", served="high")]
    sc.model("mc", configs=("low", "high", {"id": "max", "served": "converted", **iv("2026-01-01", None)}),
             conversions=conv, default=[dict(iv("2026-01-01", "2026-12-31", **WIN), configuration="high")])
    acc = [dict(iv("2026-01-01", "2026-12-31", **WIN), configuration=c) for c in ("low", "high", "max")]
    sc.route("orx", "router", spellings=["ORX"], models={"mc": {"accepts": acc}})
    s = sc.source("a")
    nes = [("no-effort-sent", "default")]
    m1 = sc.m(s, model="mc", effort=[("effort-setting", "max")], route=[("Maker API", "maker-api")])
    m2 = sc.m(s, model="mc", effort=[("effort-setting", "max")], route=[("ORX", None)])
    m3 = sc.m(s, model="mc", effort=nes, route=[("ORX", None)])
    m4 = sc.m(s, model="mc", effort=nes, route=[("Maker API", "maker-api")])
    r = sc.run()
    eq(r.cfg(m1), "high", "the maker's API: its dated conversion max → high")
    eq(r.q(m2), "out:effort-not-established", "through a router: the maker's conversion does not reach the run")
    eq(r.q(m3), "out:effort-not-established", "through a router without its own default: no maker default")
    eq(r.cfg(m4), "high", "the maker's API: its documented default")


@test
def gaps_name_to_register():
    sc = base()
    s = sc.source("a")
    sc.m(s, model="ma", effort=[LOW], model_facts=[("model-api-id", "ma-pro-x", {"namespace": "maker-api"})])
    root = tempfile.mkdtemp(prefix="pilot-")
    try:
        reg, fnd, dec = sc.write(root)
        out = os.path.join(root, "b")
        with contextlib.redirect_stdout(io.StringIO()):
            build.main(["--registry", reg, "--findings", fnd, "--decisions", dec, "--out", out, "--no-check-files",
                        "--no-lqm"])
        g = gaps.gaps(json.load(open(os.path.join(out, "status-report.json"))))[s]
    finally:
        shutil.rmtree(root, ignore_errors=True)
    eq([k.split("  ")[0] for k in g["ids"]], ["ma-pro-x"], "the name to register")


def validate_messages(sc):
    root = tempfile.mkdtemp(prefix="pilot-")
    try:
        reg, fnd, dec = sc.write(root)
        p = subprocess.run([sys.executable, os.path.join(DATA, "schema", "validate.py"), "--registry", reg,
                            "--findings", fnd, "--verbose"], capture_output=True, text=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return p.stdout


@test
def validate_registry_dates_and_evidence():
    win = dict(from_basis="earliest-capture", to_basis="last-capture")
    cases = []
    sc = base()                                           # a default before its configuration exists
    sc.model("mx", configs=[dict(iv("2026-03-01", None, from_basis="stated", to_basis="open"), id="high", served="itself"),
                            dict(iv("2026-01-01", None, from_basis="release", to_basis="open"), id="low", served="itself")],
             default=[dict(iv("2026-02-01", "2026-02-28", **win), configuration="high")])
    cases.append((sc, "ERROR", "default 'high' from 2026-02-01: its configuration does not exist then"))
    sc = base()                                           # a route's accepts before / after the configuration
    sc.model("my", configs=[dict(iv("2026-03-01", "2026-05-31", from_basis="stated", to_basis="stated"), id="low",
                                 served="itself")])
    sc.route("orq", "router", models={"my": {"accepts": [dict(iv("2026-02-01", "2026-04-30", **win), configuration="low")]}})
    cases.append((sc, "ERROR", "accepts 'low' from 2026-02-01: its configuration does not exist then"))
    sc = base()
    sc.model("my", configs=[dict(iv("2026-03-01", "2026-05-31", from_basis="stated", to_basis="stated"), id="low",
                                 served="itself")])
    sc.route("orq", "router", models={"my": {"accepts": [dict(iv("2026-04-01", "2026-07-31", **win), configuration="low")]}})
    cases.append((sc, "WARNING", "accepts 'low' 2026-04-01 → 2026-07-31 outlasts its configuration's dates"))
    sc = base()                                           # a price before the release, a price after as_of
    sc.prices["prices"].append(price("ma", "2025-12-01", "2026-09-30", {"input": 1, "output": 5}))
    cases.append((sc, "ERROR", "priced from 2025-12-01, before ma's release 2026-01-01"))
    sc = base()
    sc.prices["prices"].append(price("ma", "2026-01-01", "2026-12-31", {"input": 1, "output": 5}))
    cases.append((sc, "ERROR", "to 2026-12-31 lies after as_of 2026-10-01"))
    sc = base()                                           # evidence without its saved file and quote
    sc.models["ma"]["released"]["evidence"] = [{"url": "https://example.org/release", "where": "post"}]
    cases.append((sc, "ERROR", "released.evidence[0]: evidence without its file and quote"))
    for sc, kind, msg in cases:
        out = validate_messages(sc)
        eq(any(l.startswith(kind) and msg in l for l in out.splitlines()), True, f"{kind} {msg}")
    out = validate_messages(base())
    eq(" 0 error(s)" in out.splitlines()[-1], True, "the base fixture is clean")


# ---------------------------------------------------------------- 7: validate.py's per-file summary
@test
def validate_per_file_summary():
    sc = base()
    sc.setup("s2", headline={"metric": "pass%", "basis": "decision", "decision": None})   # a registry warning
    s = sc.source("a")
    sc.m(s, model="ma", effort=[LOW], value_form="prose")                              # the file's own error
    root = tempfile.mkdtemp(prefix="pilot-")
    try:
        reg, fnd, dec = sc.write(root)
        p = subprocess.run([sys.executable, os.path.join(DATA, "schema", "validate.py"), "--registry", reg,
                            "--findings", fnd], capture_output=True, text=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    out = p.stdout
    i_src = out.find(f"{s}.json: 1 error(s), 0 warning(s)")
    i_reg = out.find("== registry (")
    eq((i_src >= 0, i_reg > i_src), (True, True), "the source's own section, then the registry's")
    eq("headline pending" in out[i_reg:], True, "registry warnings summarised in their own section")


# ---------------------------------------------------------------- 8: converter toolkit
@test
def toolkit_mapping_and_rules():
    root = tempfile.mkdtemp(prefix="pilot-")
    try:
        csvp = write_csv(root, ["g,src,ma,low,c,m,h,per-task,,,10,20,50,pass%,,,entry-id:e1,r",
                                "g,src,mb,low,c,m,h,per-task,,,11,21,60,pass%,,,,r",
                                "g,src,mb,high,c,m,h,per-task,,,12,22,61,pass%,,,,r",
                                "g,other,ma,low,c,m,h,per-task,,,10,20,50,pass%,,,,r"])
        raw = mapping.raw_rows(csvp, "src")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    src = [{"id": "e1", "in": "10", "out": "20", "eff": "low"}, {"id": "e2", "in": "11", "out": "21", "eff": "low"},
           {"id": "e9", "in": "99", "out": "99", "eff": "max"}]
    amb = mapping.match(raw + [(9, "x", dict(raw[1][2]))], src[1:2], [
        ("tokens+effort", lambda r: (r["tokens_in"], r["tokens_out"], r["effort"]), lambda s: (s["in"], s["out"], s["eff"]))])
    eq((amb["pairs"], len(amb["ambiguous"]), amb["unmatched_source"]), ([], 1, [0]),
       "a key shared by two raw rows is ambiguous: not paired, reported")
    res = mapping.match(raw, src, [
        ("entry tag", lambda r: mapping.tag(r["confound"], r"entry-id:([^;]+)"), lambda s: s["id"]),
        ("tokens+effort", lambda r: (r["tokens_in"], r["tokens_out"], r["effort"]), lambda s: (s["in"], s["out"], s["eff"]))])
    eq([(j, e[0], how) for j, e, how in res["pairs"]], [(0, 2, "entry tag"), (1, 3, "tokens+effort")], "pairs")
    eq(([e[0] for e in res["unmatched_raw"]], res["unmatched_source"]), ([4], [2]), "unmatched on both sides")
    eq(mapping.legacy_ref(res["pairs"][0][1])["line"], 2, "legacy_ref")
    c = rules.classify_all(["default", "high_budget_8192", "low", "none", "vibes", "vibes"])
    eq((c["values"]["default"][0], c["values"]["high_budget_8192"]), ("no-effort-sent", ("thinking-budget", "8192")), "rules")
    eq((c["values"]["low"], c["unknown"]), ((None, None), {"vibes": 2}), "a plain cell; unknown values reported")


@test
def toolkit_precheck_and_gaps():
    sc = base()
    sc.model("mz", configs=[dict(iv("2026-09-01", None, from_basis="stated", to_basis="open"), id="low", served="itself")])
    s = sc.source("a")
    m1 = sc.m(s, model="mk/ma", namespace="prefix", effort=[LOW], cost="1.0")
    sc.m(s, model="zz/unknown-model", namespace="prefix", effort=[LOW])
    sc.m(s, model="mb", effort=[("effort-setting", "max")])
    sc.m(s, model="mz", effort=[LOW])
    root = tempfile.mkdtemp(prefix="pilot-")
    try:
        reg, fnd, dec = sc.write(root)
        pc = precheck.precheck(reg, fnd, s)
        out = os.path.join(root, "b")
        with contextlib.redirect_stdout(io.StringIO()):
            build.main(["--registry", reg, "--findings", fnd, "--decisions", dec, "--out", out, "--no-check-files",
                        "--no-lqm"])
        g = gaps.gaps(json.load(open(os.path.join(out, "status-report.json"))))[s]
    finally:
        shutil.rmtree(root, ignore_errors=True)
    eq((pc["resolved"], pc["unresolved"], pc["unknown_heads"]), (3, {"zz/unknown-model": 1}, {"zz": 1}),
       "precheck: mk/ma, mb, mz resolve; the zz head names no route")
    eq(sum(g["ids"].values()), 1, "one id gap")
    eq(next(iter(g["ids"])).startswith("zz/unknown-model"), True, "the id gap names the value")
    eq(g["configurations"], {"mb @ max": 1, "mz @ (empty configuration list)": 1}, "configuration gaps (mz: none at the run date)")
    eq(g["prices"], {"ma": 1}, "price gap")


# ---------------------------------------------------------------- the coordinator's build rules (23 Oct)
@test
def cost_reproduction_rule():
    sc = base()
    sc.model("mc")
    same_price(sc, "ma", "mb", "mc")
    sc.price_tables = {"lib-1": {"label": "runcost 0.1.12", "evidence": EV, "input_includes_cache_read": False,
                                 "cards": [{"model": k, "currency": "USD", "per": "MTok",
                                            "classes": {"input": 1, "output": 5}} for k in ("ma", "mb")]}}
    s = sc.source("a")
    tok = {"tokens-in": "1000000", "tokens-out": "200000"}
    pt = ("priced with runcost", "lib-1")
    m1 = sc.m(s, model="ma", effort=[LOW], cost="2.00", tokens=tok, price_table=pt, method="library-table")
    m2 = sc.m(s, model="mb", effort=[LOW], cost="2.50", tokens=tok, price_table=pt, method="library-table")
    m3 = sc.m(s, model="mc", effort=[LOW], cost="2.75", tokens=tok, price_table=pt, method="library-table")
    sc.m(s, model="mc", effort=[HIGH], cost="3.10", tokens=tok, price_table=pt, method="library-table")
    r = sc.run()
    eq(r[m1]["fields"]["cost"]["reproduction"].startswith("reproduced"), True, "reproduced within its rounding")
    eq(r.c(m2), "out:contradictory", "stated method reproduced and off by more than its rounding")
    eq(r[m3]["fields"]["cost"]["reproduction"].startswith("no card"), True, "no card: accepted as written")
    eq(r.c(m3), "in", "accepted as written")
    computed, _ = reproduce.card_cost({"input": 1000, "cache-read": 400, "output": 10}, {"input": 1, "output": 5,
                                      "cache-read": 0.1}, input_includes_cache_read=True)
    eq(round(computed * 1e6, 6), 600 + 40 + 50, "input read as total: cache reads subtracted")


@test
def run_date_from_documented_id_convention():
    out = {}
    for level in ("written", "not-established:assumed"):
        sc = base()
        sc.model("aa1", released="2026-01-01", names=[name("alias-x", "2026-01-01", "2026-03-31")])
        sc.model("aa2", released="2026-04-01", names=[name("alias-x", "2026-04-01")])
        s = sc.source("a", published="2026-05-01")
        q = "Entry ids are manual-YYYYMMDD-<model>, the date of the run."
        conv = ("run-date-convention", "manual-YYYYMMDD", {"form": "prose", "quote": q, "level": level,
                                                            "pattern": r"manual-(?P<date>[0-9]{8})-"})
        m1 = sc.m(s, model="alias-x", effort=[LOW], more={"run_date": [conv],
                                                          "aggregation": [("run-id", "manual-20260215-alias-x", {})]})
        out[level] = sc.run()[m1]["fields"]["model"]["value"]
    eq(out["written"], "aa1", "a documented convention: the id's date places the alias")
    eq(out["not-established:assumed"], None, "an undocumented convention gives no run date")


@test
def price_tier_factor():
    sc = base()
    for k, batch in (("ma", {"input": 1, "output": 5}), ("mb", {"input": 1, "output": 6})):
        sc.prices["prices"] += [price(k, "2026-01-01", "2026-10-01", {"input": 2, "output": 10}),
                                price(k, "2026-01-01", "2026-10-01", batch, kind="batch")]
    sc.model("mc")
    sc.prices["prices"] += [price("mc", "2026-01-01", "2026-10-01", {"input": 2, "output": 10}),
                            price("mc", "2026-01-01", "2026-10-01", {"input": 1, "output": 5}, kind="batch")]
    s = sc.source("a")
    tier = {"spend": [("price-tier", "Batch API", {"term": "batch", "about": None})]}
    m1 = sc.m(s, model="ma", effort=[LOW], cost="1.0", more=tier)
    m2 = sc.m(s, model="mb", effort=[LOW], cost="1.0", more=tier)
    m3 = sc.m(s, model="mc", effort=[LOW], cost="1.5", more=tier)
    sc.model("md")
    sc.prices["prices"] += [price("md", "2026-01-01", "2026-10-01", {"input": 2, "output": 10}),
                            price("md", "2026-01-01", "2026-03-31", {"input": 1, "output": 5}, kind="batch"),
                            price("md", "2026-04-01", "2026-10-01", {"input": 1.2, "output": 6}, kind="batch")]
    m4 = sc.m(s, model="md", effort=[LOW], cost="1.0", more=tier)
    r = sc.run()
    eq(r.c(m4), "out:cost-not-comparable", "two batch factors over the price date (0.5, 0.6): none proven")
    c1 = r[m1]["fields"]["cost"]
    eq((c1["tier"]["factor"], c1["base"]["value"]), (0.5, 2.0), "batch = ½ standard, proven: re-priced to standard")
    eq(r.c(m2), "out:cost-not-comparable", "batch not a uniform multiple of standard: no proven factor")
    eq(sorted(x["cost_usd"] for x in r.tables["fit-cost.csv"]), ["2", "3"], "at standard in the fit table")
    eq(r.c(m3), "in", "in")
