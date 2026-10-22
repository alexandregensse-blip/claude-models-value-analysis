#!/usr/bin/env python3
"""Tests of data/build.py: one small fixture per reason code, per configuration step (1–8), per run-date rule, per
campaign rule, per cost step, decisions first and the stale hash, and the three examples with their expected statuses.

    python3 data/tests/run.py            # all
    python3 data/tests/run.py cost       # the tests whose name contains 'cost'
"""
import os, sys, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fixtures import Sc, iv, name, price, EV, build, DATA  # noqa: E402

TESTS = []


def test(f):
    TESTS.append(f)
    return f


def eq(got, want, what=""):
    if got != want:
        raise AssertionError(f"{what}: got {got!r}, want {want!r}")


def base(as_of="2026-10-01"):
    sc = Sc(as_of)
    sc.model("ma")
    sc.model("mb")
    sc.setup("s1")
    return sc


LOW, HIGH, MED = ("effort-setting", "low"), ("effort-setting", "high"), ("effort-setting", "medium")


def same_price(sc, *models, classes=None):
    for k in models:
        sc.prices["prices"].append(price(k, "2026-01-01", "2026-10-01", classes or {"input": 1, "output": 5}))


# ================================================================ reason codes
@test
def reason_in():
    sc = base()
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW])
    m2 = sc.m(s, model="mb", effort=[HIGH], score="60%")
    r = sc.run()
    eq(r.q(m1), "in", "ma@low")
    eq(r.q(m2), "in", "mb@high")
    eq(len(r.rows("fit-quality.csv", group="s1")), 2, "fit rows")
    eq(r.group_map, {"s1": "s1"}, "group map")


@test
def reason_no_proof():
    sc = base()
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], value_form="prose")      # a prose fact without its quote
    m2 = sc.m(s, model="mb", effort=[LOW])
    r = sc.run()
    eq(r.q(m1), "out:no-proof", "prose value without quote")
    eq(r.q(m2), "out:single-couple", "the other one alone")


@test
def reason_model_not_established():
    sc = base()
    s = sc.source("a")
    m1 = sc.m(s, model="no-such-model", effort=[LOW])
    r = sc.run()
    eq(r.q(m1), "out:model-not-established", "unknown id")


@test
def reason_budget_config_and_merge():
    sc = base()
    sc.model("mh", configs=("nothink", "think-<budget>"))
    s = sc.source("a")
    m1 = sc.m(s, model="mh", effort=[("thinking-budget", "budget 10000")])
    m2 = sc.m(s, model="mh", effort=[("thinking-budget", "budget 10240")], score="55%")
    m3 = sc.m(s, model="mh", effort=[("thinking-budget", "budget 512")], score="45%")
    r = sc.run()
    eq(r.q(m1), "out:budget-config", "budget")
    eq(r.cfg(m1), "think-10000", "budget")
    eq(r.cfg(m2), "think-10000", "within 5 % merged")
    eq(r.q(m3), "out:effort-not-established", "below budget_min: not in the list")


@test
def reason_effort_not_in_list():
    sc = base()
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[("effort-setting", "max")])
    r = sc.run()
    eq(r.cfg(m1), "max", "requested")
    eq(r.q(m1), "out:effort-not-established", "max not offered")


@test
def reason_estimate():
    sc = base()
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], value_level="source-estimate")
    eq(sc.run().q(m1), "out:estimate", "source estimate")


@test
def reason_failed_partial_assumed_contradictory():
    sc = base()
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], anomalies=[("failure", "2 runs crashed", "written")])
    m2 = sc.m(s, model="ma", effort=[MED], anomalies=[("partial", "12 items not scored", "written")])
    m3 = sc.m(s, model="mb", effort=[LOW], anomalies=[("partial", "missing items scored as wrong", "written")])
    m4 = sc.m(s, model="mb", effort=[MED], anomalies=[("partial", "maybe partial", "not-established:assumed")])
    m5 = sc.m(s, model="mb", effort=[HIGH], value_level="not-established:contradictory")
    m6 = sc.m(s, model="ma", effort=[HIGH], anomalies=[("cap", "100 turns", "written")])
    r = sc.run()
    eq(r.q(m1), "out:failed-run", "failure")
    eq(r.q(m2), "out:partial", "partial")
    eq(r.q(m3), "in", "partial scored as wrong")
    eq(r.q(m4), "out:anomaly-assumed", "anomaly assumed")
    eq(r.q(m5), "out:contradictory", "contradictory value")
    eq(r.q(m6), "in", "a declared cap is a setup attribute")


@test
def reason_not_headline():
    sc = base()
    sc.setup("s2", headline={"metric": "accuracy%", "basis": "designated", "evidence": EV})
    sc.setup("s3", headline={"metric": "pass%", "basis": "decision", "decision": None})
    sc.setup("s4", headline={"metric": "pass%", "basis": "decision", "decision": "D1"})
    sc.decisions.append(dict(kind="headline", id="D1", setup="s4", metric="pass%", publisher=None, reason="r",
                             date="2026-10-22", decided_by="maintainer"))
    s = sc.source("a")
    m1 = sc.m(s, setup="s2", model="ma", effort=[LOW])
    m2 = sc.m(s, setup="s3", model="ma", effort=[LOW])
    m3 = sc.m(s, setup="s4", model="ma", effort=[LOW])
    m4 = sc.m(s, setup="s4", model="mb", effort=[LOW])
    r = sc.run()
    eq(r.q(m1), "out:not-headline", "other headline")
    eq(r.q(m2), "out:not-headline", "headline pending")
    eq(r.q(m3), "in", "headline decided")
    eq(r.q(m4), "in", "headline decided")


@test
def reason_uninformative():
    sc = base()
    same_price(sc, "ma", "mb")
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], score="100%", cost="1.0")
    m2 = sc.m(s, model="mb", effort=[LOW], score="50%", cost="2.0")
    m3 = sc.m(s, model="mb", effort=[HIGH], score="60%", cost="3.0")
    r = sc.run()
    eq(r.q(m1), "out:uninformative", "at the ceiling")
    eq(r.c(m1), "in", "its cost kept")
    eq(r.q(m2), "in", "others")


@test
def reason_single_couple_and_fit_list():
    sc = base()
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW])
    s2 = sc.source("b", publisher="puby")
    m2 = sc.m(s2, model="ma", effort=[LOW])
    m3 = sc.m(s2, model="mb", effort=[LOW])
    r = sc.run()
    eq(r.q(m1), "out:single-couple", "alone in its group")
    eq(r.q(m2), "in", "pair")
    eq(sorted(r.group_map), ["s1@puby"], "a setup with two publishers: groups named per publisher")
    lst = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_fit-models.txt")
    with open(lst, "w") as f:
        f.write("ma\n")
    try:
        r = sc.run("--fit-models", lst)
    finally:
        os.remove(lst)
    eq(r.q(m2), "out:single-couple", "mb not in the fit's model list")


@test
def reason_cost_codes():
    sc = base()
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], cost="1.0")                       # no price registered
    m2 = sc.m(s, model="mb", effort=[LOW], cost="1.0", basis="subscription")
    r = sc.run()
    eq(r.c(m1), "out:cost-not-comparable", "no price over its price date")
    eq(r.c(m2), "out:cost-basis", "subscription")
    sc2 = base()
    same_price(sc2, "ma", "mb")
    s = sc2.source("a")
    m1 = sc2.m(s, model="ma", effort=[LOW], cost="1.0")
    m2 = sc2.m(s, model="mb", effort=[LOW])
    r = sc2.run()
    eq(r.c(m1), "out:cost-single-couple", "one couple with a cost")
    eq(r.c(m2), None, "no cost: not on the cost axis")


@test
def reason_decisions_first_and_stale():
    sc = base()
    same_price(sc, "ma", "mb")
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], cost="1.0")
    m2 = sc.m(s, model="mb", effort=[LOW], cost="2.0")
    s2 = sc.source("b", publisher="puby")
    m3 = sc.m(s2, model="ma", effort=[("effort-setting", "max")])           # tree: out:effort-not-established
    sc.decide(m3, "quality", "in", "the maintainer accepts it")
    sc.decide(m1, "cost", "out", "cost doubted")
    r = sc.run()
    eq(r.q(m3), "in:decision:D1", "decision in, evaluated first")
    eq(r.c(m1), "out:decision:D2", "decision on the cost axis only")
    eq(r.q(m1), "in", "quality untouched")
    eq(r.c(m2), "out:cost-single-couple", "its cost partner decided out")
    # stale: the fact judged changed after the decision
    sc = base()
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[("effort-setting", "max")])
    sc.decide(m1, "both", "in")
    sc.after_hash.append(lambda sc: sc.sources[s]["facts"][1].__setitem__("value", "51%"))
    r = sc.run()
    eq(r.q(m1), "out:effort-not-established", "stale decision not applied")
    eq([d["id"] for d in r.rep["stale_decisions"]], ["D1"], "stale reported")


@test
def reason_lqm_composite_and_residual():
    sc = base()
    sc.setup("c1", family="f1")
    sc.setup("c2", family="f2")
    sc.setup("comp", family="fc", composite={"components": ["c1", "c2"], "formula": {"weights": {"c1": 1, "c2": 1}},
                                             "linear": True, "evidence": EV})
    s = sc.source("a")
    k1 = sc.m(s, setup="comp", model="ma", effort=[LOW], score="60%")
    k2 = sc.m(s, setup="comp", model="mb", effort=[LOW], score="70%")
    sc.m(s, setup="c1", model="ma", effort=[LOW], score="50%")
    sc.m(s, setup="c1", model="mb", effort=[LOW], score="80%")
    r = sc.run(lqm=True)
    eq(r.q(k1), "out:composite", "component measured: lqm.load drops the composite")
    eq(r.q(k2), "out:composite", "component measured")
    res = r[k1 + "~resid"]
    eq(res["status"]["quality"], "in", "residual for c2")
    eq(res["setup"], "comp-resid-c2", "residual setup")
    eq(float(res["fields"]["score"]["number"]), 70.0, "(60 − ½·50) / ½")


@test
def reason_lqm_republished():
    sc = base()
    sc.setup("r1", family="fr")
    sc.setup("r2", family="fr")
    same_price(sc, "ma", "mb")
    s1 = sc.source("a")
    s2 = sc.source("b", publisher="puby")
    for s, setup, extra in ((s1, "r1", True), (s2, "r2", False)):
        sc.m(s, setup=setup, model="ma", effort=[LOW], score="50.0%", cost="1.00")
        sc.m(s, setup=setup, model="mb", effort=[LOW], score="60.0%", cost="2.00")
        if extra:
            sc.m(s, setup=setup, model="ma", effort=[HIGH], score="70.0%", cost="3.00")
    r = sc.run(lqm=True)
    eq(r.q(f"{s2}#M1"), "out:republished", "copy dropped from the smaller group")
    eq(r.q(f"{s1}#M1"), "in", "kept in the larger group")


@test
def reason_lqm_saturated():
    sc = base()
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], score="100%")
    sc.m(s, model="mb", effort=[LOW], score="100%")
    r = sc.run(lqm=True)
    eq(r.q(m1), "out:saturated", "every couple at the bound")


# ================================================================ configuration steps
@test
def cfg1_solo():
    sc = base()
    sc.model("ms", configs=("solo",))
    s = sc.source("a")
    m1 = sc.m(s, model="ms", effort=[("effort-label", "high")])
    m2 = sc.m(s, model="ma", effort=[LOW])
    r = sc.run()
    eq(r.cfg(m1), "solo", "solo whatever is stated")
    eq(r.q(m1), "in", "solo in the fit")
    eq(r.q(m2), "in", "partner")


@test
def cfg2_budget_and_scalar():
    sc = base()
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[("effort-setting", "0.5")])
    r = sc.run()
    eq(r.cfg(m1), "scalar-0.5", "numeric scale")
    eq(r.q(m1), "out:effort-not-established", "scalar without mapping")


@test
def cfg3_setting_thinking_selects_contradiction():
    sc = base()
    sc.model("mg", configs=("nothink", "low", "medium", "high"))
    sc.model("mq", configs=("nothink", "think"))
    sc.model("md", configs=("nothink", "think"), names=[name("md-chat", selects="nothink"),
                                                         name("md-reasoner", selects="think")])
    s = sc.source("a")
    m1 = sc.m(s, model="mg", effort=[("effort-setting", "reasoning_effort: none")])
    m2 = sc.m(s, model="mq", effort=[("thinking-on", "enable_thinking: true")])
    m3 = sc.m(s, model="mq", effort=[("thinking-off", "enable_thinking: false")])
    m4 = sc.m(s, model="md-chat")
    m5 = sc.m(s, model="md-reasoner", effort=[("no-effort-sent", "null")])
    m6 = sc.m(s, model="ma", effort=[LOW, ("effort-label", "high")])
    m7 = sc.m(s, model="mg", effort=[("effort-setting", "reasoning_effort: high")])
    r = sc.run()
    eq(r.cfg(m1), "nothink", "reasoning_effort: none")
    eq(r.cfg(m2), "think", "thinking on")
    eq(r.cfg(m3), "nothink", "thinking off")
    eq(r.cfg(m4), "nothink", "a name that selects nothink")
    eq(r.cfg(m5), "think", "-thinking id with no level sent: the more specific statement")
    eq(r[m6]["fields"]["configuration"]["level"], "not-established:contradictory", "setting low, label high")
    eq(r.q(m6), "out:effort-not-established", "contradictory")
    eq(r.cfg(m7), "high", "key: value setting line")
    eq(r.q(m1), "in", "nothink is a couple of its model")


@test
def cfg3_cells_with_prefix_and_column():
    sc = base()
    sc.model("mg", configs=("nothink", "low", "medium", "high"))
    s = sc.source("t")
    text = "entry,model,reasoning_effort,score\ne1,mk/mg,none,0.50\ne2,mk/mg,low,0.625\n"
    sc.cells[s] = ("table.csv", text, False)
    doc = sc.sources[s]
    doc["tables"] = [{"id": "T1", "file": "table.csv", "where": "table.csv", "format": "csv", "row_key": "entry",
                      "columns": {"model": {"says": ["model-api-id", "route"], "namespace": "prefix"},
                                  "reasoning_effort": "effort-setting",
                                  "score": {"says": "score", "term": "pass%", "scale": "fraction"}}}]
    for i, e in enumerate(("e1", "e2"), 1):
        sc.msets[s].append({"id": f"M{i}", "setup": "s1", "verified": None, "facts": {
            "value": f"T1/{e}/score", "model": [f"T1/{e}/model"], "effort": [f"T1/{e}/reasoning_effort"],
            "route": [f"T1/{e}/model"]}})
    r = sc.run(check_files=True)
    eq(r.cfg(f"{s}#M1"), "nothink", "column reasoning_effort, cell none")
    eq(r.model(f"{s}#M1"), "mg", "prefix mk/ names the maker's API")
    eq(r.rows("fit-quality.csv", effort="low")[0]["score"], "62.5", "fraction → percent, exactly")
    eq(r.q(f"{s}#M2"), "in", "cell measure in")
    sc.cells[s] = ("table.csv", text, True)
    r = sc.run()
    eq(r.q(f"{s}#M1"), "out:no-proof", "a cell whose saved file's sha256 does not match")


@test
def cfg4_label():
    sc = base()
    sc.model("mq", configs=("nothink", "think"))
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[("effort-label", "High effort")])
    m2 = sc.m(s, model="mq", effort=[("effort-label", "Non-reasoning")])
    r = sc.run()
    eq(r.cfg(m1), "high", "label naming a level")
    eq(r.cfg(m2), "nothink", "a thinking-off label")


@test
def cfg5_label_to_ladder():
    sc = base()
    sc.model("mg", configs=("nothink", "low", "medium", "high"))
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[("effort-label", "lowest effort setting")])
    m2 = sc.m(s, model="mg", effort=[("effort-label", "lowest effort setting")])
    m3 = sc.m(s, model="mg", effort=[("effort-label", "maximum reasoning")])
    r = sc.run()
    eq(r.cfg(m1), "low", "lowest of [low … high]")
    eq(r[m2]["fields"]["configuration"]["level"], "not-established:ambiguous", "nothink or low")
    eq(r.cfg(m3), "high", "highest level")


@test
def cfg6_route_chain():
    sc = base()
    win = dict(from_basis="earliest-capture", to_basis="last-capture")
    sc.model("mc", configs=("low", "high", {"id": "max", "served": "converted", **iv("2026-01-01", None)}),
             conversions=[dict(iv("2026-01-01", "2026-12-31", **win), route="maker-api", requested="max",
                               served="high")])
    sc.model("mc2", configs=("low", "high", {"id": "max", "served": "converted", **iv("2026-01-01", None)}))
    sc.model("mx", configs=("low", "medium", "high", "xhigh"))
    sc.route("orx", "router", spellings=["ORX"], models={"ma": {"mapping": [
        dict(iv("2026-01-01", "2026-12-31", **win), requested="high", served="medium")]}})
    sc.route("ory", "router", spellings=["ORY"],
             level_mapping=[dict(iv("2026-01-01", "2026-12-31", **win), rule="nearest-supported", ties="ambiguous")],
             models={"mx": {"accepts": [dict(iv("2026-01-01", "2026-12-31", **win), configuration=c)
                                        for c in ("low", "high")]}})
    sc.route("orw", "router", spellings=["ORW"])
    s = sc.source("a")
    m1 = sc.m(s, model="mc", effort=[("effort-setting", "max")])
    m2 = sc.m(s, model="mc2", effort=[("effort-setting", "max")])
    m3 = sc.m(s, model="ma", effort=[HIGH], route=[("ORX", None)])
    m4 = sc.m(s, model="mx", effort=[("effort-setting", "xhigh")], route=[("ORY", None)])
    m5 = sc.m(s, model="mx", effort=[MED], route=[("ORY", None)])
    m6 = sc.m(s, model="ma", effort=[HIGH], route=[("ORW", None)])
    r = sc.run()
    eq(r.cfg(m1), "high", "dated maker conversion max → high")
    eq(r.q(m2), "out:effort-not-established", "converted without a dated conversion (decision C)")
    eq(r.cfg(m3), "medium", "router mapping high → medium")
    eq(r.cfg(m4), "high", "nearest supported")
    eq(r[m5]["fields"]["configuration"]["level"], "not-established:ambiguous", "a tie")
    eq(r.q(m6), "out:effort-not-established", "a router documenting nothing")
    # route unknown: every candidate route must agree
    sc2 = base()
    sc2.route("orz", "router", models={"ma": {"mapping": [dict(iv("2026-01-01", "2026-12-31", **win),
                                                               requested="high", served="medium")]}})
    s = sc2.source("a")
    m1 = sc2.m(s, model="ma", effort=[HIGH])
    m2 = sc2.m(s, model="mb", effort=[HIGH])
    r = sc2.run()
    eq(r.q(m1), "out:effort-not-established", "maker-api says high, orz says medium")
    eq(r.cfg(m2), "high", "only the maker's API serves mb")


@test
def cfg7_default():
    sc = base()
    win = dict(from_basis="earliest-capture", to_basis="last-capture")
    sc.model("md1", default=[dict(iv("2026-01-01", "2026-12-31", **win), configuration="medium")])
    sc.model("md2", default=[dict(iv("2026-08-01", "2026-08-31", **win), configuration="medium")])
    sc.route("orr", "router", spellings=["ORR"], models={"md1": {"default": [
        dict(iv("2026-01-01", "2026-12-31", **win), configuration="high")]}})
    s = sc.source("a")
    mk = [("Maker API", "maker-api")]                      # unknown route: orr documents md1 too (they disagree)
    m0 = sc.m(s, model="md1", effort=[("no-effort-sent", "default")])
    m1 = sc.m(s, model="md1", effort=[("no-effort-sent", "default")], route=mk)
    m2 = sc.m(s, model="md2", effort=[("no-effort-sent", "default")])
    m3 = sc.m(s, model="md1", effort=[("no-effort-sent", "default")], route=[("ORR", None)])
    r = sc.run()
    eq(r.q(m0), "out:effort-not-established", "route unknown: maker-api medium, orr high")
    eq(r.cfg(m1), "medium", "maker's documented default")
    eq(r.cfg(m2), "default", "default not covering the run")
    eq(r.q(m2), "out:effort-not-established", "default not covering the run")
    eq(r.cfg(m3), "high", "the router's own documented default")


@test
def cfg8_unstated():
    sc = base()
    s = sc.source("a")
    m1 = sc.m(s, model="ma")
    r = sc.run()
    eq(r.cfg(m1), "unstated", "nothing stated")
    eq(r.q(m1), "out:effort-not-established", "unstated")


# ================================================================ run date
@test
def run_date_alias():
    sc = base()
    sc.model("aa1", released="2026-01-01", names=[name("alias-x", "2026-01-01", "2026-03-31")])
    sc.model("aa2", released="2026-04-01", names=[name("alias-x", "2026-04-01")])
    s = sc.source("a")
    m1 = sc.m(s, model="alias-x", effort=[LOW], run_date=[("run-date", "2026-02-15")])
    m2 = sc.m(s, model="alias-x", effort=[LOW], run_date=[("run-date", "1 May 2026")])
    m3 = sc.m(s, model="alias-x", effort=[LOW], run_date=[("run-start", "2026-03-01")])
    r = sc.run()
    eq(r.model(m1), "aa1", "before the redirect")
    eq(r.model(m2), "aa2", "after the redirect")
    eq(r.q(m3), "out:model-not-established", "an interval across the redirect")
    eq("alias-by-date" in r[m1]["rules_used"], True, "rule recorded")


@test
def run_date_interval_and_default_upper():
    sc = base()
    win = dict(from_basis="earliest-capture", to_basis="last-capture")
    sc.model("md", released="2026-03-01", default=[dict(iv("2026-03-03", "2026-03-31", **win), configuration="medium")])
    s = sc.source("a", captures=[{"id": "S1", "kind": "fetch", "url": "https://example.org/a", "captured": "2026-03-20"}])
    nes = [("no-effort-sent", "default")]
    m1 = sc.m(s, model="md", effort=nes, run_date=[("run-start", "2026-03-05"), ("run-end", "2026-03-20")])
    m2 = sc.m(s, model="md", effort=nes, run_date=[("run-end", "2026-03-20")])
    st = ("run-start", "2026-03-05")
    m3 = sc.m(s, model="md", effort=nes, run_date=[st])
    m4 = sc.m(s, model="md", effort=nes, run_date=[st], value_seen_in=["S1"])
    s2 = sc.source("b", commit="abcdef1", captures=[{"id": "G1", "kind": "commit", "commit": "abcdef1",
                                                     "captured": "2026-03-15T10:00:00Z"}])
    m5 = sc.m(s2, model="md", effort=nes, run_date=[st])
    r = sc.run()
    eq(r.cfg(m1), "medium", "start and end inside the dated default")
    eq(r.cfg(m2), "default", "a lone end: the lower bound is the release")
    eq(r.cfg(m3), "default", "upper bound = publication, after the default's last capture")
    eq(r.cfg(m4), "medium", "upper bound = the earliest capture carrying the value")
    eq(r.cfg(m5), "medium", "upper bound = the commit")


@test
def run_date_early_access():
    sc = base()
    sc.model("mn", released="2026-07-01")
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], early_access=True)
    m2 = sc.m(s, model="mn", effort=[LOW])                 # published 2026-06-01, before the release
    r = sc.run()
    eq(r.q(m1), "in", "early access in")
    eq(r.rows("fit-quality.csv", model="ma")[0]["confound"], "EAP-run", "early-access fact → EAP-run")
    eq(r.rows("fit-quality.csv", model="mn")[0]["confound"], "EAP-run", "upper bound before the release")


# ================================================================ campaigns
@test
def campaign_continuation():
    sc = base()
    s1 = sc.source("board", published="2026-05-01")
    a1 = sc.m(s1, model="ma", effort=[LOW], score="50%", version="1.0")
    sc.m(s1, model="mb", effort=[LOW], score="60%", version="1.0")
    s2 = sc.source("board", published="2026-06-01", snapshot_of=s1)
    a2 = sc.m(s2, model="ma", effort=[LOW], score="55%")
    b2 = sc.m(s2, model="mb", effort=[LOW], score="65%")
    r = sc.run()
    eq(r[a2]["campaign"], "1.0", "inherited along snapshot_of")
    eq(r.q(a1), "out:superseded", "replaced within its campaign")
    eq(r.q(a2), "in", "the later value")
    eq(r.q(b2), "in", "the later value")
    eq(r.rows("fit-quality.csv", model="ma")[0]["confound"], f"prev=50% ({a1})", "prev recorded")


@test
def campaign_new_version():
    sc = base()
    s1 = sc.source("board", published="2026-05-01")
    a1 = sc.m(s1, model="ma", effort=[LOW], score="50%", version="1.0")
    sc.m(s1, model="mb", effort=[LOW], score="60%", version="1.0")
    s2 = sc.source("board", published="2026-06-01", snapshot_of=s1)
    a2 = sc.m(s2, model="ma", effort=[LOW], score="55%", version="v2.0")
    sc.m(s2, model="mb", effort=[LOW], score="65%", version="v2.0")
    r = sc.run()
    eq(r.q(a1), "in", "earlier campaign stays")
    eq(r.q(a2), "in", "new campaign")
    eq(sorted(r.group_map), ["s1#1.0", "s1#2.0"], "one group per campaign")


@test
def campaign_same_runs_as():
    for stated in (True, False):
        sc = base()
        sc.setup("s1b")
        s1 = sc.source("run", published="2026-05-01")
        a1 = sc.m(s1, model="ma", effort=[LOW], score="50.0%", cost="1.00")
        sc.m(s1, model="mb", effort=[LOW], score="60.0%", cost="2.00")
        s2 = sc.source("regrade", published="2026-06-01")
        sra = s1 if stated else None
        a2 = sc.m(s2, setup="s1b", model="ma", effort=[LOW], score="52.0%", cost="1.00", same_runs_as=sra)
        sc.m(s2, setup="s1b", model="mb", effort=[LOW], score="61.0%", cost="2.00", same_runs_as=sra)
        same_price(sc, "ma", "mb")
        r = sc.run()
        how = "stated" if stated else "proven by identical costs"
        eq(r.q(a1), "out:superseded", f"{how}: the later grading replaces the earlier")
        eq(r.c(a1), "out:superseded", f"{how}: the cost counts once")
        eq(r.q(a2), "in", how)
        eq(r.c(a2), "in", how)


# ================================================================ cost steps
@test
def cost_publisher_figure():
    sc = base()
    same_price(sc, "ma", "mb")
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], cost="1.0")
    sc.m(s, model="mb", effort=[LOW], cost="2.0")
    r = sc.run()
    eq(r.c(m1), "in", "re-priced: figure at the base price")
    eq(r[m1]["fields"]["cost"]["base"]["rule"], "cost-publisher-figure", "rule")
    eq(r.rows("fit-cost.csv", model="ma")[0]["cost_usd"], "1", "value")


def two_prices(sc, model, old, new, change="2026-07-01"):
    d = (__import__("datetime").date.fromisoformat(change) - __import__("datetime").timedelta(days=1)).isoformat()
    sc.prices["prices"] += [price(model, "2026-01-01", d, old), price(model, change, "2026-10-01", new)]


@test
def cost_delta_on_source():
    sc = base()
    old, new = {"input": 1, "output": 5, "cache-read": 0.1}, {"input": 1, "output": 5, "cache-read": 0.05}
    two_prices(sc, "ma", old, new)
    two_prices(sc, "mb", old, new)
    s = sc.source("a")
    tok = {"tokens-in": "1000000", "tokens-out": "200000", "tokens-cache-read": "2000000"}
    m1 = sc.m(s, model="ma", effort=[LOW], cost="2.20", tokens=tok, price_table="list prices of 1 June 2026")
    sc.m(s, model="mb", effort=[LOW], cost="2.20", tokens=tok, price_table="list prices of 1 June 2026")
    r = sc.run()
    b = r[m1]["fields"]["cost"]["base"]
    eq(b["rule"], "cost-delta-on-source", "rule")
    eq(round(b["value"], 6), 2.1, "2.20 − 2 MTok × $0.05")
    eq(r.c(m1), "in", "re-priced")


@test
def cost_uniform_factor():
    sc = base()
    two_prices(sc, "ma", {"input": 2, "output": 10}, {"input": 1, "output": 5})
    two_prices(sc, "mb", {"input": 2, "output": 10}, {"input": 1, "output": 5})
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], cost="4.0", price_table="prices of 2026-06-01")
    sc.m(s, model="mb", effort=[LOW], cost="3.0", price_table="prices of 2026-06-01")
    r = sc.run()
    b = r[m1]["fields"]["cost"]["base"]
    eq((b["rule"], b["value"]), ("cost-uniform-factor", 2.0), "× 0.5")
    eq(r.c(m1), "in", "re-priced")


@test
def cost_class_ratio():
    sc = base()
    old, new = {"input": 1, "output": 5, "cache-read": 0.1}, {"input": 1, "output": 5, "cache-read": 0.05}
    two_prices(sc, "ma", old, new)
    two_prices(sc, "mb", old, new)
    sc.class_ratios = {"ratios": [{"model": k, "change": "2026-07-01", "classes": {"api": {"factor": 0.9, "sd": 0.01}},
                                   "setups": {"s1": "api"}} for k in ("ma", "mb")]}
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], cost="2.0", price_table="prices of 2026-06-01")
    sc.m(s, model="mb", effort=[LOW], cost="3.0", price_table="prices of 2026-06-01")
    r = sc.run()
    b = r[m1]["fields"]["cost"]["base"]
    eq((b["rule"], round(b["value"], 9)), ("cost-class-ratio", 1.8), "× class factor")
    eq(r.c(m1), "in", "re-priced")


@test
def cost_per_model_subset_and_single():
    sc = base()
    old, new = {"input": 1, "output": 5, "cache-read": 0.1}, {"input": 1, "output": 5, "cache-read": 0.05}
    two_prices(sc, "ma", old, new)
    two_prices(sc, "mb", old, new)
    s = sc.source("a")
    pt = "prices of 2026-06-01"
    m1 = sc.m(s, model="ma", effort=[LOW], cost="1.0", price_table=pt)
    sc.m(s, model="ma", effort=[HIGH], cost="2.0", price_table=pt)
    m3 = sc.m(s, model="mb", effort=[LOW], cost="1.5", price_table=pt)
    r = sc.run()
    eq(r.c(m1), "in", "unrepriced: its own subset, efforts' ratios hold")
    eq("cost-unrepriced" in r[m1]["flags"], True, "flagged")
    eq(r.c(m3), "out:cost-single-couple", "a subset of one couple")
    eq(r[m1]["cost_group"], "s1~c1", "cost group suffix")
    # the price changed (not uniformly) inside its price-date interval
    sc = base()
    two_prices(sc, "ma", old, new, change="2026-04-01")
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], cost="1.0")
    sc.m(s, model="ma", effort=[HIGH], cost="2.0")
    r = sc.run()
    eq(r.c(m1), "out:cost-not-comparable", "non-uniform change over [release, publication]")


@test
def cost_currency():
    sc = base()
    same_price(sc, "ma", "mb")
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], cost="7.0", currency="CNY")
    m2 = sc.m(s, model="mb", effort=[LOW], cost="1.0")
    r = sc.run()
    eq(r[m1]["fields"]["cost"]["part"][3], "CNY", "partitioned by currency")
    eq(r.c(m1), "out:cost-single-couple", "alone in its currency")
    eq(r.c(m2), "out:cost-single-couple", "alone in its currency")


@test
def cost_method_unstated_setting():
    sc = base()
    same_price(sc, "ma", "mb")
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], cost="1.0")
    m2 = sc.m(s, model="mb", effort=[LOW], cost="2.0")
    r = sc.run()
    eq(r.c(m1), "in", "single-per-table (default)")
    eq("cost-method-assumed-single" in r.rows("fit-cost.csv", model="ma")[0]["confound"], True, "flagged")
    r = sc.run("--cost-method-unstated", "out")
    eq(r.c(m2), "out:cost-not-comparable", "setting out")
    sc = base()
    same_price(sc, "ma", "mb")
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], cost="1.0", method="tokens×list")
    sc.m(s, model="mb", effort=[LOW], cost="2.0", method="tokens×list")
    r = sc.run("--cost-method-unstated", "out")
    eq(r.c(m1), "in", "a stated method is not affected")


@test
def report_counts_and_diff():
    import shutil, tempfile
    sc = base()
    same_price(sc, "ma", "mb")
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], cost="1.0")
    sc.m(s, model="mb", effort=[LOW], cost="2.0")
    keep = tempfile.mkdtemp(prefix="buildprev-")
    try:
        r0 = sc.run(keep=keep)
        eq(r0.rep["counts"], {"quality": {"in": 2}, "cost": {"in": 2}}, "counts per reason")
        eq(set(r0[m1]) >= {"status", "reason_detail", "facts_used", "rules_used", "fields"}, True, "report fields")
        r = sc.run("--cost-method-unstated", "out", "--previous", os.path.join(keep, "status-report.json"))
    finally:
        shutil.rmtree(keep, ignore_errors=True)
    eq(r.rep["diff"]["changed"][m1], {"cost": ["in", "out:cost-not-comparable"]}, "status diff")


# ================================================================ the three examples
@test
def examples():
    ex = os.path.join(DATA, "findings", "examples")
    obv = "src-github-obviousbench-v0.2-aggregate-2026-10-10"
    if not os.path.isfile("/work/.salvo14/arb/obv/evidence/summary-222d955.csv"):
        raise AssertionError("SKIP: the examples' saved copies are not reachable here")
    import contextlib, io, json, shutil, tempfile
    out = tempfile.mkdtemp(prefix="buildex-")
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = build.main(["--registry", os.path.join(ex, "registry"), "--findings", ex, "--decisions",
                               os.path.join(ex, "decisions.json"), "--out", out])
        eq(code, 0, "build")
        rep = json.load(open(os.path.join(out, "status-report.json")))
    finally:
        shutil.rmtree(out, ignore_errors=True)
    M = rep["measures"]
    st = lambda ref: (M[ref]["fields"]["configuration"].get("value"), M[ref]["status"]["quality"])  # noqa: E731
    want = {f"{obv}#M1": ("low", "in"), f"{obv}#M2": ("max", "out:uninformative"),
            f"{obv}#M3": ("default", "out:effort-not-established"), f"{obv}#M4": ("think-1024", "out:budget-config"),
            f"{obv}#M5": ("nothink", "in"), f"{obv}#M6": ("low", "in"),
            f"{obv}#M7": ("default", "out:effort-not-established")}
    for ref, w in want.items():
        eq(st(ref), w, ref)
    eq(M[f"{obv}#M1"]["setup"], "obvbench", "setup")
    eq(M[f"{obv}#M1"]["fields"]["score"]["text"], "0.958333", "fraction as written")
    eq(M[f"{obv}#M5"]["lqm_outcome"]["quality"].startswith("filtered"), True, "nothink: lqm.EFFORTS pending")
    hot = "src-hotkv-banking77-semantic-cache-2026-10-12"
    for i in (1, 2):
        eq(st(f"{hot}#M{i}"), ("low", "out:not-headline"), f"HotKV M{i}: lowest → low; headline pending")
        eq(M[f"{hot}#M{i}"]["fields"]["configuration"]["step"], 5, "label-to-ladder")
        eq(M[f"{hot}#M{i}"]["status"]["cost"], "out:cost-not-comparable", "11 Oct prices not registered")
    card = "src-anthropic-fable-5-1-system-card-2026-09-01"
    for i in (1, 2, 3, 4):
        eq(st(f"{card}#M{i}"), (None, "out:effort-not-established"), f"chart M{i}: unlabeled marker")
        eq(M[f"{card}#M{i}"]["fields"]["configuration"]["level"], "not-established:assumed", "assumed")
    eq(st(f"{card}#M5"), ("max", "out:single-couple"), "printed 86.2 % with 'max effort'")
    eq(M[f"{card}#M5"]["fields"]["score"]["text"], "86.2%", "printed over read")


def main():
    pat = sys.argv[1] if len(sys.argv) > 1 else ""
    t0, fails, skips = time.time(), 0, 0
    sel = [t for t in TESTS if pat in t.__name__]
    for t in sel:
        try:
            t()
            print(f"ok    {t.__name__}")
        except AssertionError as e:
            if str(e).startswith("SKIP"):
                skips += 1
                print(f"skip  {t.__name__}: {e}")
                continue
            fails += 1
            print(f"FAIL  {t.__name__}: {e}")
        except Exception:
            fails += 1
            print(f"ERROR {t.__name__}:\n{traceback.format_exc()}")
    print(f"\n{len(sel) - fails - skips} passed, {fails} failed, {skips} skipped ({time.time() - t0:.1f} s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
