"""Tests of the toolkit fixes after the ObviousBench pilot v2 (report-v2.md §7, §8.4): route heads by the build's rule,
`enabled` and the unmapped settings in rules.py, the legacy_ref diff's `unchanged`, the mapping CLI, per-row
reasoning_included and the price-table builder. Each test fails on the code before the fix (noted per test)."""
import contextlib, csv, io, json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fixtures import Sc, iv, name, EV, build, DATA  # noqa: E402
sys.path.insert(0, DATA)
from convert import mapping, rules, reproduce, precheck  # noqa: E402

TESTS = []


def test(f):
    f.__name__ = "gaps2_" + f.__name__
    TESTS.append(f)
    return f


def eq(got, want, what=""):
    if got != want:
        raise AssertionError(f"{what}: got {got!r}, want {want!r}")


@test
def precheck_heads_by_the_builds_route_rule():
    """Before: a head only counted when it was a name prefix; a route term or a spelling (case-insensitive) was
    reported as naming no route."""
    sc = Sc("2026-10-01")
    sc.model("ma")
    sc.setup("s1")
    sc.route("grok", "maker-api", prefixes=[])
    sc.route("gem-flex", "router", spellings=["Flexy"])
    root = tempfile.mkdtemp(prefix="g2-")
    try:
        ctx = precheck._Ctx(sc.write(root)[0])
        eq(precheck.head_route(ctx, "GROK"), "grok", "a route term, case-insensitive")
        eq(precheck.head_route(ctx, "flexy"), "gem-flex", "a route spelling")
        eq(precheck.head_route(ctx, "mk"), "maker-api", "a name prefix")
        eq(precheck.head_route(ctx, "zz"), None, "no route")
        s = sc.source("a")
        sc.m(s, model="grok/ma", namespace="prefix", effort=[("effort-setting", "low")])
        sc.m(s, model="Flexy/ma", namespace="prefix", effort=[("effort-setting", "low")])
        sc.m(s, model="zz/ma", namespace="prefix", effort=[("effort-setting", "low")])
        reg, fnd, _ = sc.write(os.path.join(root, "w"))
        eq(precheck.precheck(reg, fnd, s)["unknown_heads"], {"zz": 1}, "only zz names no route")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@test
def rules_enabled_and_unmapped_settings_follow_the_build():
    """Before: `enabled` gave a thinking-on fact (the build maps that to think, established) while the build reads an
    `enabled` cell as not established; adaptive/dynamic/reasoning were unknown (row refused as absent)."""
    ctx = type("C", (), {})()
    ctx.vocab = json.load(open(os.path.join(DATA, "schema", "vocab.json"), encoding="utf-8"))
    for v in ("enabled", "adaptive", "dynamic", "reasoning"):
        c = rules.classify(v)
        eq(c is not None and c[0] is None, True, f"{v}: a plain cell, no per-row fact")
    eq(build.map_setting(ctx, "enabled", "reasoning_effort"), ("enabled", "not-established"), "the build's reading")
    eq(rules.classify("thinking")[0], "thinking-on", "thinking stays a thinking-on fact")
    eq(rules.classify("on")[0], "thinking-on", "on stays a thinking-on fact")


@test
def diff_unchanged_ignores_digits():
    """Before: `unchanged` counted only pairs whose digits were spelled identically (always 0 in a conversion); a
    change of model key still counts (coordinator, 26 Oct)."""
    L = {"line": 2, "row_sha256": "h"}
    st = {"quality": "in", "cost": "in"}
    pm = {"L1": dict(kind="legacy", line=2, row_sha256="h", status=st,
                     row=dict(source="src", group="g", model="opus-5", effort="high", score="50.0", cost_usd="0.30"))}
    nm = {"M1": dict(source="s", legacy_ref=L, status=dict(st),
                     row=dict(source="src", group="g", model="opus-5", effort="high", score="50", cost_usd="0.3"))}
    d = build.diff_by_legacy_ref(pm, nm)["src"]
    eq((d["unchanged"], d["changed"]), (1, []), "digit spelling does not count")
    nm["M1"]["row"]["model"] = "opus-5-pro"
    d = build.diff_by_legacy_ref(pm, nm)["src"]
    eq((d["unchanged"], list(d["changed"][0]["changes"])), (0, ["model"]), "a model key change counts")
    nm["M1"]["row"]["model"] = "opus-5"
    nm["M1"]["row"]["effort"] = "low"
    d = build.diff_by_legacy_ref(pm, nm)["src"]
    eq((d["unchanged"], list(d["changed"][0]["changes"])), (0, ["effort"]), "configuration counts")


@test
def mapping_cli_prints_ambiguous_and_unpaired():
    """Before: mapping.py had no save/report/CLI (the ambiguous tags and the unpaired rows lived in the result dict)."""
    raw = [(2, "a", {"model": "m", "confound": "entry=x"}), (3, "b", {"model": "m", "confound": "entry=x"}),
           (4, "c", {"model": "n", "confound": ""})]
    src = [{"id": "x"}, {"id": "y"}]
    res = mapping.match(raw, src, [("entry tag", lambda r: mapping.tag(r["confound"], r"entry=([^;]+)"), lambda s: s["id"])])
    root = tempfile.mkdtemp(prefix="g2-")
    try:
        p = os.path.join(root, "m.json")
        mapping.save(p, res, src, lambda s: s["id"])
        out = subprocess.run([sys.executable, os.path.join(DATA, "convert", "mapping.py"), p], capture_output=True,
                             text=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    eq(out.returncode, 0, "exit code")
    t = out.stdout
    eq(("[entry tag] key 'x'" in t, "raw lines [2, 3]" in t, "line 4" in t, "row 1: y" in t), (True,) * 4, t)


@test
def reproduce_reasoning_included_per_row():
    """Before: one reasoning setting per table; a per-row statement could not change a row's computed cost."""
    root = tempfile.mkdtemp(prefix="g2-")
    try:
        tj = os.path.join(root, "t.json")
        json.dump({"tables": {"t": {"label": "t", "evidence": [], "reasoning_in_output": True,
                                    "cards": [{"model": "ma", "currency": "USD", "per": "MTok",
                                               "classes": {"input": 1, "output": 5}}]}}}, open(tj, "w"))
        mj = os.path.join(root, "m.json")
        json.dump({"x/ma": "ma"}, open(mj, "w"))
        cj = os.path.join(root, "r.csv")
        with open(cj, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "m", "cost", "i", "o", "r", "inc"])
            w.writerow(["a", "x/ma", "1.00", "0", "200000", "200000", "true"])     # reasoning inside: 200000*5/1e6
            w.writerow(["b", "x/ma", "2.00", "0", "200000", "200000", "false"])    # added: 400000*5/1e6
            w.writerow(["c", "x/ma", "1.00", "0", "200000", "200000", ""])         # blank: the table (inside)
        out = subprocess.run([sys.executable, os.path.join(DATA, "convert", "reproduce.py"), "--tables", tj, "--table",
                              "t", "--csv", cj, "--model-col", "m", "--model-map", mj, "--cost-col", "cost",
                              "--in-col", "i", "--out-col", "o", "--reasoning-col", "r", "--reasoning-included-col",
                              "inc", "--row-key", "id"], capture_output=True, text=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    st = {l.split("\t")[0]: l.split("\t")[5] for l in out.stdout.splitlines()[1:]}
    eq(st, {"a": "reproduced", "b": "reproduced", "c": "reproduced"}, out.stdout + out.stderr)


@test
def price_table_builder_keys_by_registry_names():
    """Before: nothing built a table from a library's ledgers; the model map was hand-made."""
    sc = Sc("2026-10-01")
    sc.model("ma")
    sc.model("mb")
    root = tempfile.mkdtemp(prefix="g2-")
    try:
        reg = sc.write(root)[0]
        ctx = precheck._Ctx(reg)
        ctx.routes = ctx.routes
        led = lambda inp, out: {"ledger": {"components": [  # noqa: E731
            {"name": "input_uncached_tokens", "unit_price": inp / 1e6, "price_card_id": "c1"},
            {"name": "output_text_tokens", "unit_price": out / 1e6, "price_card_id": "c1"}]}}
        prices = reproduce.ledger_prices(["mk/ma", "mk/ma", "zz/nobody", "mk/mb"],
                                         [led(1, 5), led(1, 5), led(2, 9), {"ledger": {"price_card": {"source": "s"}}}])
        tab, rep = reproduce.build_table(prices, ctx, "lib-1", "lib 1 (npm)", "1", [{"url": "u"}])
        t = tab["tables"]["lib-1"]
        eq([(c["model"], c["route"], c["classes"]) for c in t["cards"]], [("ma", None, {"input": 1.0, "output": 5.0})],
           "one card keyed by the registry name")
        eq([s for s, _ in rep["unresolved"]], ["zz/nobody"], "a string with no key is listed, not carded")
        eq(rep["static"], ["mk/mb"], "a source-priced (static) card is listed, not carded")
        try:
            reproduce.run_library([], os.path.join(root, "nodir"), "0.1.12")
            raise AssertionError("no error for a missing library")
        except (OSError, ValueError):
            pass
        os.makedirs(os.path.join(root, "lib"))
        json.dump({"version": "0.1.11"}, open(os.path.join(root, "lib", "package.json"), "w"))
        try:
            reproduce.run_library([], os.path.join(root, "lib"), "0.1.12")
            raise AssertionError("a different version was accepted")
        except ValueError as e:
            eq("pinned '0.1.12'" in str(e), True, "version pin")
    finally:
        shutil.rmtree(root, ignore_errors=True)
