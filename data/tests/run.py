#!/usr/bin/env python3
"""Tests of data/build.py: one small fixture per reason code, per configuration step (1–8), per run-date rule, per
campaign rule, per cost step, decisions first and the stale hash, and the three examples with their expected statuses.

    python3 data/tests/run.py            # all
    python3 data/tests/run.py cost       # the tests whose name contains 'cost'
"""
import os, shutil, sys, time, traceback

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
def cfg3_unlisted_does_not_match():
    sc = base()
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[("effort-setting", "max"), ("effort-label", "High")])
    sc.m(s, model="mb", effort=[LOW])
    r = sc.run()
    eq(r.cfg(m1), "high", "max is not one of ma's configurations: only the label matches")


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
    m1 = sc2.m(s, model="ma", effort=[HIGH], route=[("Unregistered Provider", None)])
    m2 = sc2.m(s, model="mb", effort=[HIGH], route=[("Unregistered Provider", None)])
    m3 = sc2.m(s, model="ma", effort=[HIGH])
    r = sc2.run()
    eq(r.q(m1), "out:effort-not-established", "a route named but unresolved: maker-api says high, orz says medium")
    eq(r.cfg(m2), "high", "only the maker's API serves mb")
    eq((r.cfg(m3), "route-presumed-maker-api" in r[m3]["flags"]), ("high", True), "no route named: maker-api presumed")


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
    m0 = sc.m(s, model="md1", effort=[("no-effort-sent", "default")], route=[("Unregistered Provider", None)])
    m4 = sc.m(s, model="md1", effort=[("no-effort-sent", "default")])
    m1 = sc.m(s, model="md1", effort=[("no-effort-sent", "default")], route=mk)
    m2 = sc.m(s, model="md2", effort=[("no-effort-sent", "default")])
    m3 = sc.m(s, model="md1", effort=[("no-effort-sent", "default")], route=[("ORR", None)])
    r = sc.run()
    eq(r.q(m0), "out:effort-not-established", "route unknown: maker-api medium, orr high")
    eq(r.cfg(m1), "medium", "maker's documented default")
    eq(r.cfg(m2), "default", "default not covering the run")
    eq(r.q(m2), "out:effort-not-established", "default not covering the run")
    eq(r.cfg(m3), "high", "the router's own documented default")
    eq(r.cfg(m4), "medium", "no route named: the maker's default (maker-api presumed)")


@test
def cfg7_default_bridged_gap():
    # rule A (the maintainer, 29 Oct): the same default before and after a span without captures covers the span
    # (qwen3.6-plus: think on the Chinese page to 21 May, on the English page from 19 Oct)
    sc = base()
    win = dict(from_basis="earliest-capture", to_basis="last-capture")
    rec = lambda frm, to, c, **kw: dict(iv(frm, to, **win), configuration=c, **kw)     # noqa: E731
    two = ("nothink", "think")
    sc.model("qa", configs=two, default=[rec("2026-01-01", "2026-03-31", "think"), rec("2026-07-01", "2026-12-31", "think")])
    sc.model("qb", configs=two, default=[rec("2026-01-01", "2026-03-31", "think"), rec("2026-07-01", "2026-12-31", "nothink")])
    sc.model("qc", configs=two, default=[rec("2026-01-01", "2026-03-31", "think"), rec("2026-05-01", "2026-05-10", "nothink"),
                                         rec("2026-07-01", "2026-12-31", "think")])
    sc.model("qd", configs=two, names=[name("qd", "2026-01-01"), name("qd-latest", "2026-05-01")],
             default=[rec("2026-01-01", "2026-03-31", "think"), rec("2026-07-01", "2026-12-31", "think")])
    sc.model("qe", configs=two, default=[rec("2026-01-01", "2026-03-31", "think", setting="thinking"),
                                         rec("2026-07-01", "2026-12-31", "think")])
    s = sc.source("a", published="2026-12-31")
    nes = [("no-effort-sent", "default")]
    on = lambda k, d: sc.m(s, model=k, effort=nes, run_date=[("run-date", d)])          # noqa: E731
    m1, m2, m3 = on("qa", "2026-05-15"), on("qa", "2026-02-15"), on("qb", "2026-05-15")
    m4, m5, m6 = on("qc", "2026-06-15"), on("qd", "2026-06-15"), on("qe", "2026-05-15")
    m7 = sc.m(s, model="qa", effort=nes, run_date=[("run-start", "2026-03-15"), ("run-end", "2026-05-01")])
    r = sc.run()
    eq((r.cfg(m1), "default-bridged" in r[m1]["flags"], "default-bridged-gap" in r[m1]["rules_used"]),
       ("think", True, True), "think on both sides: the gap is covered, flagged")
    eq(r[m1]["fields"]["default_bridged"], [{"from": "2026-03-31", "to": "2026-07-01", "basis": "bridged"}], "the span")
    eq((r.cfg(m2), "default-bridged" in r[m2]["flags"]), ("think", False), "inside a record: no bridge used")
    eq(r.cfg(m7), "think", "a run from a record into the gap")
    # negative controls: another configuration after the gap, another record inside it, a name starting inside it, a
    # record of another setting on one side
    eq([r.cfg(m) for m in (m3, m4, m5, m6)], ["default"] * 4, "no bridge")
    eq(r.q(m3), "out:effort-not-established", "out as before")


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
    # a run that ends before the newer candidate's release (early access by date for it): the bound is the earliest
    # release, so the older model is placed (vals.ai gemini-3.5-flash, 26 Oct); a source published before the
    # release, no run date stated
    sc = base()
    sc.model("ab1", released="2026-01-01", names=[name("alias-y", "2026-01-01", "2026-06-30")])
    sc.model("ab2", released="2026-07-01", names=[name("alias-y", "2026-07-01")])
    s = sc.source("a", published="2026-05-01")
    m4 = sc.m(s, model="alias-y", effort=[LOW])
    r = sc.run()
    eq(r.model(m4), "ab1", "the newer candidate's early access does not unbound the alias")
    # a stated run end before the newer release, in a source published after it: the newer candidate's release is
    # no contradiction (it used to widen its interval to the publication and straddle the switch; matharena, 28 Oct)
    sc = base()
    sc.model("ac1", released="2026-01-01", names=[name("alias-z", "2026-01-01", "2026-06-30")])
    sc.model("ac2", released="2026-07-01", names=[name("alias-z", "2026-07-01")])
    s = sc.source("a", published="2026-10-01")
    m5 = sc.m(s, model="alias-z", effort=[LOW], run_date=[("run-end", "2026-06-23")])
    m6 = sc.m(s, model="alias-z", effort=[LOW])
    r = sc.run()
    eq((r.model(m5), r.q(m6)), ("ac1", "out:model-not-established"), "run end before the switch; none stated")
    # a stated run start before the model's release: the run is from the release, so a default documented from the
    # release covers it (arxiv-2609.04298 Harbor@v0.6.4 1 May, Opus 4.8 released 28 May; 28 Oct)
    sc = base()
    win = dict(from_basis="stated", to_basis="stated")
    sc.model("ad1", released="2026-05-28", configs=("low", "medium", "high"),
             default=[dict(iv("2026-05-28", "2026-12-31", **win), configuration="medium")])
    s = sc.source("a", published="2026-09-03")
    m7 = sc.m(s, model="ad1", effort=[("no-effort-sent", "default settings")], run_date=[("run-start", "2026-05-01")],
              score="50%")
    sc.m(s, model="ma", effort=[LOW], score="40%")
    r = sc.run()
    eq(r.cfg(m7), "medium", "the release is the lower bound")
    import build as B
    eq([x.date().isoformat() for x in B.find_date("April 2026")], ["2026-04-01", "2026-04-30"], "a month only")
    eq((B.find_date("2026-13"), B.find_date("may be 2026")), (None, None), "not a month")


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
    eq(r.rows("fit-quality.csv", model="ma")[0]["confound"], "EAP-run; route-presumed-maker-api", "early-access fact → EAP-run")
    eq(r.rows("fit-quality.csv", model="mn")[0]["confound"], "EAP-run; route-presumed-maker-api", "upper bound before the release")


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
    eq(r.rows("fit-quality.csv", model="ma")[0]["confound"], f"route-presumed-maker-api; prev=50% ({a1})", "prev recorded")


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
    eq(r.rows("fit-cost.csv", model="ma")[0]["cost_usd"], "1.0", "the cost as written")


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
    sc = base()
    two_prices(sc, "ma", {"input": 3, "output": 15}, {"input": 1, "output": 5})
    two_prices(sc, "mb", {"input": 3, "output": 15}, {"input": 1, "output": 5})
    s = sc.source("a")
    sc.m(s, model="ma", effort=[LOW], cost="4.10", price_table="prices of 2026-06-01")
    sc.m(s, model="mb", effort=[LOW], cost="3.00", price_table="prices of 2026-06-01")
    r = sc.run()
    eq([x["cost_usd"] for x in r.tables["fit-cost.csv"]], ["1.37", "1"], "the original's significant digits "
       "(repricing_makers.fmt)")


@test
def cost_promotion_window_is_a_price_applied():
    # a window where only a promotion is printed: the promotion is the price charged (never the base); before the
    # fix the price date was "not registered" (coordinator, 26 Oct)
    sc = base()
    for k in ("ma", "mb"):
        sc.prices["prices"] += [price(k, "2026-01-01", "2026-04-30", {"input": 2, "output": 10}),
                                price(k, "2026-05-01", "2026-06-30", {"input": 1, "output": 5}, kind="promotion"),
                                price(k, "2026-07-01", "2026-10-01", {"input": 2, "output": 10})]
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], cost="1.0", price_table="prices of 2026-06-01")
    sc.m(s, model="mb", effort=[LOW], cost="2.0", price_table="prices of 2026-06-01")
    r = sc.run()
    c = r[m1]["fields"]["cost"]
    eq(c.get("price_covered"), True, "the promotion covers the price date")
    eq(c.get("price_vectors"), [{"input": 1, "output": 5}], "the promotion's classes")


@test
def cost_base_scheduled_list_price():
    # an introductory price with a stated end and the list price after it: the promotion is charged, the stated list
    # price is the base (gemini-3.8-flash, gemini-4-argon; coordinator 26 Oct)
    import build as B
    sc = base()
    for k in ("ma", "mb"):
        sc.prices["prices"].append(price(k, "2026-05-01", "2026-10-01", {"input": 1, "output": 5}, kind="promotion",
                                         list_after={"from": "2027-01-01", "classes": {"input": 2, "output": 10}}))
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], cost="1.0", price_table="prices of 2026-06-01")
    sc.m(s, model="mb", effort=[LOW], cost="3.0", price_table="prices of 2026-06-01")
    r = sc.run()
    b = r[m1]["fields"]["cost"]["base"]
    eq((b["rule"], b["value"]), ("cost-uniform-factor", 2.0), "× 2 to the stated list price")
    eq("base-scheduled-list-price" in r[m1]["flags"], True, "flagged")


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
    eq((r.c(m1), "cost-price-band" in r[m1]["flags"]), ("in", True),
       "non-uniform change over [release, publication]: in, with the price band as uncertainty (29 Oct)")
    eq(float(r.rows("fit-cost.csv", model="ma", effort="low")[0]["cost_prec"]) > 0, True, "band widens the sd")


@test
def cost_stated_prices():
    # rule B (the maintainer, 29 Oct): no registered price covers the price date, the source states the prices it
    # applied (vals.ai's Input / Output Cost column) → re-priced from them to the registered base price
    def scenario(stated, register_from="2026-08-01"):
        sc = base()
        for k in ("ma", "mb"):
            sc.prices["prices"].append(price(k, register_from, "2026-10-01", {"input": 1, "output": 5, "cache-read": 0.1}))
        s = sc.source("a", published="2026-06-01")
        ms = []
        for k, cost, cls in (("ma", "1.0", stated[0]), ("mb", "3.0", stated[1])):
            # a date in a class price's quote is not its price date (a date is a price-table fact of its own, as mb's)
            more = {"spend": [("price-table", v, {"term": c, "written": f"${v}", "about": f"{k}-{len(ms) + 1}",
                                                  "quote": f"{k}, as of 2026-09-01: ${v}"}) for c, v in cls]}
            if k == "mb":
                more["spend"].append(("price-table", "prices of 2026-05-01", {"about": None}))
            ms.append(sc.m(s, model=k, effort=[LOW], cost=cost, more=more))
        return sc, ms
    sc, (m1, m2) = scenario(([("input", "1"), ("output", "5")], [("input", "2"), ("output", "10")]))
    r = sc.run()
    b1, b2 = r[m1]["fields"]["cost"]["base"], r[m2]["fields"]["cost"]["base"]
    eq((r.c(m1), r.c(m2)), ("in", "in"), "re-priced from the stated prices")
    eq((b1["rule"], b1["value"], b2["value"]), ("cost-uniform-factor", 1.0, 1.5), "equal prices: × 1; doubled: × 0.5")
    eq(("cost-stated-prices" in r[m1]["flags"], "cost-stated-prices" in r[m1]["rules_used"]), (True, True), "flagged")
    eq(r[m2]["fields"]["cost"]["stated_prices"], {"classes": {"input": 2.0, "output": 10.0}, "used": True}, "reported")
    # negative controls: nothing stated → out as before; two input prices → not used; a registered price over the
    # price date → the registered vector, the stated one unused; no base price → out
    sc, (m1, m2) = scenario(([], []))
    r = sc.run()
    eq((r.c(m1), "cost-stated-prices" in r[m1]["flags"]), ("out:cost-not-comparable", False), "nothing stated")
    sc, (m1, m2) = scenario(([("input", "1"), ("input", "2"), ("output", "5")], [("input", "2"), ("output", "10")]))
    r = sc.run()
    eq((r.c(m1), r[m1]["fields"]["cost"]["stated_prices"]["why"]), ("out:cost-not-comparable", "two stated input prices"),
       "contradictory stated prices")
    sc, (m1, m2) = scenario(([("input", "2"), ("output", "10")], [("input", "2"), ("output", "10")]),
                            register_from="2026-01-01")
    r = sc.run()
    eq((r[m1]["fields"]["cost"]["base"]["rule"], r[m1]["fields"]["cost"]["stated_prices"]["used"],
        "cost-stated-prices" in r[m1]["flags"]), ("cost-publisher-figure", False, False), "registered prices decide")
    sc, (m1, m2) = scenario(([("input", "1"), ("output", "5")], [("input", "2"), ("output", "10")]))
    sc.prices["prices"] = [p for p in sc.prices["prices"] if p["model"] != "ma"]
    r = sc.run()
    eq(r.c(m1), "out:cost-not-comparable", "no registered base price: not re-priced")
    # validate.py: a stated class price is a number (the agent's reading), and a term is a table or a price class
    sc, (m1, m2) = scenario(([("input", "$1 / $5")], [("input", "2"), ("output", "10")]))
    sc.sources[m1.split("#")[0]]["facts"].append(dict(id="F99", says="price-table", about=None, value="x", term="inputs",
                                                      level="written", form="data-file", where="w", file="saved.txt"))
    r = sc.run()
    eq((r.c(m1), r.q(m1)), ("out:no-proof", "in"), "a stated price written as the source's notation: the cost refused")
    errs = " ".join(e[1] if isinstance(e, (list, tuple)) else str(e) for e in r.rep["validation"]["errors"])
    eq(("is a number per million tokens" in errs, "nor a price class" in errs), (True, True), "validate.py says why")


@test
def cost_currency():
    sc = base()
    same_price(sc, "ma", "mb")
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], cost="7.0", currency="CNY")
    m2 = sc.m(s, model="mb", effort=[LOW], cost="1.0")
    r = sc.run()
    eq(r.c(m1), "out:cost-not-comparable", "a CNY cost: no CNY price registered (the USD vector is not used)")
    eq(r.c(m2), "out:cost-single-couple", "alone in its currency")
    same_price(sc, "ma", "mb", classes={"input": 2, "output": 8})
    for p in sc.prices["prices"][-2:]:
        p["currency"] = "CNY"
    r = sc.run()
    eq(r[m1]["fields"]["cost"]["part"][3], "CNY", "partitioned by currency")
    eq((r.c(m1), r.c(m2)), ("out:cost-single-couple", "out:cost-single-couple"), "each alone in its currency")


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
def reason_value_not_established():
    sc = base()
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], value_level="not-established:assumed")
    eq(sc.run().q(m1), "out:value-not-established", "an assumed value")


# ================================================================ JSON tables, runs, counts
def json_case(sc, doc, where, row_key, s_name="j"):
    import json
    sc.model("mg", configs=("nothink", "low", "medium", "high"))
    s = sc.source(s_name)
    sc.cells[s] = ("saved/data.json", json.dumps(doc), False)
    sc.sources[s]["tables"] = [{"id": "T1", "file": "saved/data.json", "where": where, "format": "json", "row_key": row_key,
                                "columns": {"model": {"says": ["model-api-id", "route"], "namespace": "prefix"},
                                            "cfg.effort": "effort-setting",
                                            "score": {"says": "score", "term": "pass%", "scale": "fraction"}}}]
    for i, e in enumerate(("e1", "e2"), 1):
        sc.msets[s].append({"id": f"M{i}", "setup": "s1", "verified": None, "facts": {
            "value": f"T1/{e}/score", "model": [f"T1/{e}/model"], "effort": [f"T1/{e}/cfg.effort"],
            "route": [f"T1/{e}/model"], "value_seen_in": []}})
    return s


@test
def json_tables():
    rows = [{"id": "e1", "model": "mk/mg", "cfg": {"effort": "none"}, "score": 0.5},
            {"id": "e2", "model": "mk/ma", "cfg": {"effort": "high"}, "score": 0.625}]
    sc = base()
    s = json_case(sc, {"meta": {"v": 1}, "results": rows}, "$.results", "id")
    r = sc.run(check_files=True)
    eq((r.cfg(f"{s}#M1"), r.q(f"{s}#M1")), ("nothink", "in"), "JSON path $.results")
    eq(r.rows("fit-quality.csv", model="ma")[0]["score"], "62.5", "number kept as written, then × 100")
    sc = base()
    s = json_case(sc, {"data": {"rows": {r_["id"]: r_ for r_ in rows}}}, "$['data'].rows", "$key")
    r = sc.run(check_files=True)
    eq((r.cfg(f"{s}#M2"), r.q(f"{s}#M2")), ("high", "in"), "an object of rows, row_key $key")
    sc = base()
    s = json_case(sc, {"results": rows}, "results", "id")
    r = sc.run(check_files=True)
    eq(r.q(f"{s}#M1"), "out:no-proof", "a json table's where must be a JSON path")
    eq(any("must be a JSON path" in e for e in r.rep["validation"]["errors"]), True, "reported by validate.py")


@test
def mean_of_runs():
    sc = base()
    s = sc.source("a")
    runs = [("r1", "50.0%"), ("r2", "60.0%"), ("r3", "70.0%")]
    m1 = sc.m(s, model="ma", effort=[LOW], score="60.0%", runs=runs,
              anomalies=[("failure", "run r1 crashed", "written", "r1")])
    m2 = sc.m(s, model="mb", effort=[LOW], score="60.0%", runs=runs, anomalies=[("failure", "a run crashed", "written")])
    m3 = sc.m(s, model="mb", effort=[HIGH], score="62.0%", runs=runs,
              anomalies=[("failure", "run r1 crashed", "written", "r1")])
    sc.m(s, model="ma", effort=[HIGH], score="55.0%")
    r = sc.run()
    eq(r.q(m1), "in", "recomputed without the failed run")
    eq(float(r[m1]["fields"]["score"]["number"]), 65.0, "mean of r2, r3")
    eq("mean-of-runs" in r[m1]["rules_used"], True, "rule")
    eq(r.q(m2), "out:failed-run", "the failure names no run")
    eq(r.q(m3), "out:failed-run", "the runs do not reproduce the source's mean")
    sc = base()
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], score="60.0%", runs=runs,
              anomalies=[("failure", "run r9 crashed", "written", "r9")])
    sc.m(s, model="mb", effort=[LOW], score="61.0%")
    eq(sc.run().q(m1), "out:no-proof", "validate.py: a failure naming a run not cited")
    sc = base()
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], score="60.0%", runs=runs)
    next(f for f in sc.sources[s]["facts"] if f["says"] == "run-score").pop("run")
    eq(sc.run().q(m1), "out:no-proof", "validate.py: a run-score names its run")


@test
def percent_from_counts():
    sc = base()
    sc.setup("sf", metric="accuracy", bounds=(0, 1))
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], score="45 of 60", scale="counts")
    sc.m(s, model="mb", effort=[LOW], score="1,000/2,000", scale="counts")
    m3 = sc.m(s, setup="sf", model="ma", effort=[LOW], score="3 out of 4", scale="counts")
    sc.m(s, setup="sf", model="mb", effort=[LOW], score="1/4", scale="counts")
    m5 = sc.m(s, model="ma", effort=[HIGH], score="about 45", scale="counts")
    r = sc.run()
    eq((r.q(m1), r.rows("fit-quality.csv", model="ma", group="s1")[0]["score"]), ("in", "75"), "100·k/N")
    eq(r.rows("fit-quality.csv", model="ma", group="sf")[0]["score"], "0.75", "k/N on a fraction metric")
    eq("percent-from-counts" in r[m3]["rules_used"], True, "rule")
    eq(r.q(m5), "out:no-proof", "validate.py: a counts score is written k of N")
    eq(any("a counts score is written" in e for e in r.rep["validation"]["errors"]), True, "reported by validate.py")


# ================================================================ long-context tiers, retired models
@test
def cost_long_context():
    sc = base()
    sc.model("mc")
    lc = lambda i, o, c: [{"threshold_input_tokens": 200000, "classes": {"input": i, "output": o, "cache-read": c}}]  # noqa
    for k in ("ma", "mb", "mc"):
        sc.prices["prices"] += [
            price(k, "2026-01-01", "2026-06-30", {"input": 1, "output": 5, "cache-read": 0.1}, long_context=lc(2, 10, 0.2)),
            price(k, "2026-07-01", "2026-10-01", {"input": 1, "output": 5, "cache-read": 0.05}, long_context=lc(2, 10, 0.1))]
    s = sc.source("a")
    tok = {"tokens-in": "1000000", "tokens-out": "200000", "tokens-cache-read": "2000000"}
    pt = "list prices of 1 June 2026"
    m1 = sc.m(s, model="ma", effort=[LOW], cost="2.20", price_table=pt,
              tokens=dict(tok, requests="10", **{"tokens-in-per-request": "100000"}))
    m2 = sc.m(s, model="mb", effort=[LOW], cost="2.20", price_table=pt, tokens=tok)
    m3 = sc.m(s, model="mc", effort=[LOW], cost="4.40", price_table=pt,
              tokens=dict(tok, requests="1", **{"tokens-in-per-request": "300000"}))
    m4 = sc.m(s, model="mc", effort=[HIGH], cost="4.40", price_table=pt,
              tokens=dict(tok, requests="10", **{"tokens-in-per-request": "300000"}))
    r = sc.run()
    eq(round(r[m1]["fields"]["cost"]["base"]["value"], 6), 2.1, "every call below the threshold: standard prices")
    eq(r[m2]["fields"]["cost"]["base"], None, "requests and per-call sizes unknown: not re-priceable")
    eq("not re-priceable" in r[m2]["fields"]["cost"]["reprice_detail"], True, "why")
    eq(round(r[m3]["fields"]["cost"]["base"]["value"], 6), 4.2, "one call above the threshold: the tier")
    eq(r[m4]["fields"]["cost"]["base"], None, "calls on both sides cannot be split")


@test
def cost_retired_last_list_price():
    sc = base()
    for k in ("ma", "mb"):
        sc.prices["prices"].append(price(k, "2026-01-01", "2026-06-30", {"input": 1, "output": 5}))
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], cost="1.0")
    m2 = sc.m(s, model="mb", effort=[LOW], cost="2.0")
    r = sc.run()
    eq(r.c(m1), "in", "a retired model: priced at its last list price")
    eq("base-last-list-price" in r[m1]["flags"], True, "flagged")
    sc.prices["prices"].append(price("mb", "2026-07-01", "2026-07-31", {"input": 0.5, "output": 2.5}, base=True))
    r = sc.run()
    eq(r[m2]["fields"]["cost"]["base"]["value"], 1.0, "a base entry says otherwise: × 0.5")


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
    eq(M[f"{obv}#M5"]["lqm_outcome"]["quality"], "kept", "nothink: a configuration of lqm.EFFORTS, kept by lqm.load")
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


# ================================================================ legacy path, arguments, diff by source, run date
def legacy_csv(rows):
    head = "group,source,model,effort,task_type,complexity,harness,unit,cost_usd,cost_prec,tokens_in,tokens_out," \
           "score,score_metric,score_prec,cached_pct,confound,ref"
    return head + "\n# a free-text comment line\n" + "\n".join(rows) + "\n"


@test
def legacy_path():
    import csv, io, json, shutil, subprocess, tempfile
    import legacy as LG
    rows = ['g1,srcA,ma,low,coding,mid,"h, v1",per-task,0.30,0.00289,,,71.5,pass%,0.082,,"reprice-2026-10-07:x:was=0.31",r1',
            'g1,srcB,mb,high,coding,mid,h,per-task,,,,,80.0,pass%,0.0289,,,r2',
            'g1,srcB,ma,nothink,coding,mid,h,per-task,0.10,,,,60.0,pass%,,,,r3',
            '#g1,srcB,mb,low,coding,mid,h,per-task,0.10,,,,61.0,pass%,,,,r4',
            'g2,srcB,zz,low,coding,mid,h,per-task,0.10,,,,61.0,pass%,,,,r5',
            'g2,srcA,ma,solo,coding,mid,h,per-task,0.0,,,,100,pass%,,,,r6']
    root = tempfile.mkdtemp(prefix="legacy-")
    try:
        p = os.path.join(root, "raw.csv")
        open(p, "w").write(legacy_csv(rows))
        info = LG.convert(p, os.path.join(root, "f"), os.path.join(root, "reg"))
        eq((info["rows"], info["sources"], info["skipped_lines"]), (6, 2, [2]), "conversion")
        fm = os.path.join(DATA, "findings", "examples", "registry", "flag-map.json")
        shutil.copy(fm, os.path.join(root, "reg", "flag-map.json"))
        lst = os.path.join(root, "fit.txt")
        open(lst, "w").write("ma mb")
        out = os.path.join(root, "b")
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            code = build.main(["--registry", os.path.join(root, "reg"), "--findings", os.path.join(root, "f"),
                               "--decisions", os.path.join(root, "none.json"), "--out", out, "--fit-models", lst,
                               "--no-lqm"])
        eq(code, 0, "build")
        rep = json.load(open(os.path.join(out, "status-report.json")))
        st = {e["line"]: (e["status"]["quality"], e["status"]["cost"]) for e in rep["measures"].values()}
        eq(st[3], ("legacy:in", "legacy:in"), "admitted as today, flags and all")
        eq(st[4], ("legacy:in", "legacy:out:no-value"), "no cost")
        eq(st[5], ("legacy:in", "legacy:in"), "nothink: a configuration of lqm.EFFORTS")
        eq(st[6][0], "legacy:out:comment", "a #-ed row")
        eq(st[7][0], "legacy:out:model-not-in-fit-list", "model not in the fit list")
        eq(st[8], ("legacy:in", "legacy:out:no-value"), "solo, 100 % and cost 0: no tree step, no uninformative")
        fq = open(os.path.join(out, "fit-quality.csv")).read().split("\n")
        eq(fq[1:-1], [rows[0], rows[1], rows[2], rows[5]], "verbatim lines, in the CSV's order")
        e4 = next(e for e in rep["measures"].values() if e["line"] == 3)
        eq(e4["tree_would_say"]["configuration"], "low", "informative column")
        eq(e4["kind"], "legacy", "reported as legacy")
        eq(rep["counts"]["quality"], {}, "tree counts apart from legacy counts")
        # a later build where one row changed: the diff per source names it
        rows2 = list(rows)
        rows2[1] = rows2[1].replace("80.0", "81.0")
        open(p, "w").write(legacy_csv(rows2))
        shutil.rmtree(os.path.join(root, "f"))
        LG.convert(p, os.path.join(root, "f"))
        with contextlib.redirect_stdout(io.StringIO()):
            build.main(["--registry", os.path.join(root, "reg"), "--findings", os.path.join(root, "f"), "--decisions",
                        os.path.join(root, "none.json"), "--out", out + "2", "--fit-models", lst, "--no-lqm",
                        "--previous", os.path.join(out, "status-report.json")])
        d = json.load(open(os.path.join(out + "2", "status-report.json")))["diff"]["by_source"]
        eq(list(d), ["srcB"], "one source changed")
        eq(d["srcB"]["changed"][0]["changes"], {"score": ["80.0", "81.0"]}, "the row's change")
        # a legacy fact whose row is not a line of its CSV: no proof
        sp = os.path.join(root, "f", "sources")
        fn = next(x for x in sorted(os.listdir(sp)) if "srca" in x)
        doc = json.load(open(os.path.join(sp, fn)))
        doc["facts"][0]["value"] = doc["facts"][0]["value"].replace("71.5", "71.6")
        json.dump(doc, open(os.path.join(sp, fn), "w"))
        with contextlib.redirect_stdout(io.StringIO()):
            build.main(["--registry", os.path.join(root, "reg"), "--findings", os.path.join(root, "f"), "--decisions",
                        os.path.join(root, "none.json"), "--out", out + "3", "--fit-models", lst, "--no-lqm"])
        rep3 = json.load(open(os.path.join(out + "3", "status-report.json")))
        eq(next(e for e in rep3["measures"].values() if e["line"] == 3)["status"]["quality"], "legacy:out:no-proof",
           "the row is not a line of its CSV")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@test
def bad_arguments_clean_errors():
    import subprocess, tempfile, shutil
    root = tempfile.mkdtemp(prefix="args-")
    ex = os.path.join(DATA, "findings", "examples")
    base_args = [sys.executable, os.path.join(DATA, "build.py"), "--registry", os.path.join(ex, "registry"),
                 "--findings", ex, "--no-lqm", "--no-check-files"]
    try:
        open(os.path.join(root, "afile"), "w").write("x")
        open(os.path.join(root, "bad.json"), "w").write("{")
        cases = [["--out", os.path.join(root, "afile")], ["--fit-models", "/nonexistent"],
                 ["--previous", os.path.join(root, "bad.json"), "--out", os.path.join(root, "o")],
                 ["--class-ratios", os.path.join(root, "bad.json"), "--out", os.path.join(root, "o")],
                 ["--registry", "/nonexistent", "--out", os.path.join(root, "o")]]
        for c in cases:
            p = subprocess.run(base_args + c, capture_output=True, text=True)
            eq((p.returncode, "Traceback" in p.stderr, p.stderr.startswith("error: ")), (2, False, True), str(c))
        reg = os.path.join(root, "reg")
        shutil.copytree(os.path.join(ex, "registry"), reg)
        os.remove(os.path.join(reg, "prices.json"))
        p = subprocess.run(base_args + ["--registry", reg, "--out", os.path.join(root, "o")], capture_output=True,
                           text=True)
        eq((p.returncode, "no prices.json" in p.stderr), (1, True), "a missing prices.json stops the build")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@test
def run_date_contradictory_with_event():
    sc = base()
    win = dict(from_basis="earliest-capture", to_basis="last-capture")
    sc.model("md", default=[dict(iv("2026-05-01", "2026-05-31", **win), configuration="medium")])
    s = sc.source("a", published="2026-06-01")
    m1 = sc.m(s, model="md", effort=[LOW], run_date=[("run-start", "2026-07-01")])
    m2 = sc.m(s, model="ma", effort=[LOW], run_date=[("run-start", "2026-07-01")])
    sc.m(s, model="mb", effort=[LOW])
    r = sc.run()
    eq(r.q(m1), "out:contradictory", "a dated event of md (its default) inside the widened window")
    eq(r.q(m2), "in", "no dated event of ma inside: the run date is not needed")

# ================================================================ registry extensions of 23 Oct (merge of the parts)
@test
def ext_composite_named_component_and_linear_unknown():
    sc = base()
    sc.setup("c1", family="f1")
    sc.setup("comp", family="fc", composite={"components": ["c1", {"name": "x-part", "setup": None}],
                                             "formula": {"weights": {"c1": 1, "x-part": 1}}, "linear": True,
                                             "evidence": EV})
    sc.setup("compu", family="fu", composite={"components": ["c1"], "formula": {"weights": {}}, "linear": "unknown",
                                              "evidence": EV})
    s = sc.source("a")
    k1 = sc.m(s, setup="comp", model="ma", effort=[LOW], score="60%")
    sc.m(s, setup="comp", model="mb", effort=[LOW], score="70%")
    u1 = sc.m(s, setup="compu", model="ma", effort=[LOW], score="60%")
    sc.m(s, setup="compu", model="mb", effort=[LOW], score="70%")
    sc.m(s, setup="c1", model="ma", effort=[LOW], score="50%")
    sc.m(s, setup="c1", model="mb", effort=[LOW], score="80%")
    r = sc.run()
    res = r[k1 + "~resid"]
    eq(res["setup"], "comp-resid-x-part", "residual for the unregistered component")
    eq(float(res["fields"]["score"]["number"]), 70.0, "(60 − ½·50) / ½")
    eq(u1 + "~resid" in r.rep["measures"], False, "linear unknown: no residual")


@test
def ext_price_per_configuration():
    sc = base()
    sc.model("mq", configs=("nothink", "think"))
    sc.model("mr", configs=("nothink", "think"))
    for k in ("mq", "mr"):
        sc.prices["prices"] += [
            price(k, "2026-01-01", "2026-10-01", {"input": 1, "output": 5}, configurations=["nothink"]),
            price(k, "2026-01-01", "2026-06-30", {"input": 1, "output": 10}, configurations=["think"]),
            price(k, "2026-07-01", "2026-10-01", {"input": 1, "output": 20}, configurations=["think"])]
    s = sc.source("a", published="2026-06-01")
    tok = {"tokens-in": "1000000", "tokens-out": "100000"}
    on, off = [("thinking-on", "enable_thinking: true")], [("thinking-off", "enable_thinking: false")]
    t1 = sc.m(s, model="mq", effort=on, cost="2.00", tokens=tok, price_table="list prices of 1 June 2026")
    sc.m(s, model="mr", effort=on, cost="2.00", tokens=tok, price_table="list prices of 1 June 2026")
    n1 = sc.m(s, model="mq", effort=off, cost="1.50", tokens=tok, price_table="list prices of 1 June 2026")
    sc.m(s, model="mr", effort=off, cost="1.50", tokens=tok, price_table="list prices of 1 June 2026")
    r = sc.run()
    eq(r[t1]["fields"]["cost"]["base"]["rule"], "cost-delta-on-source", "think: its own price changed")
    eq(round(r[t1]["fields"]["cost"]["base"]["value"], 6), 3.0, "2.00 + 0.1 MTok × $10")
    eq(r[n1]["fields"]["cost"]["base"]["rule"], "cost-publisher-figure", "nothink: its price never changed")


@test
def ext_hugging_face_names_case_insensitive():
    sc = base()
    sc.route("huggingface", "self-hosted", prefixes=("hf/",))
    sc.routes["huggingface"]["names_case_insensitive"] = True
    sc.model("mh", names=[name("Org/Model-8B", route="huggingface")])
    s = sc.source("a")
    m1 = sc.m(s, model="org/model-8b", namespace="prefix", effort=[LOW])
    m2 = sc.m(s, model="hf/ORG/model-8B", namespace="prefix", effort=[LOW])
    m3 = sc.m(s, model="MA", effort=[LOW])
    r = sc.run()
    eq(r.model(m1), "mh", "repository id, any case, route unknown")
    eq(r.model(m2), "mh", "hf/ prefix names the namespace")
    eq(r.q(m3), "out:model-not-established", "maker namespace stays case-sensitive")


@test
def ext_between_tools_out_of_fit():
    # between-tools is recorded, not fitted (vocab x-terms in_fit false, 29 Oct 2026: lqm.EFFORTS leaves it out); it was
    # in the fit from 26 Oct (coordinator) while lqm.EFFORTS held only the levels and solo
    sc = base()
    sc.model("ms", configs=("low", "high", "between-tools"))
    s = sc.source("a")
    m1 = sc.m(s, model="ms", effort=[("effort-setting", "thinking: {\"type\": \"between_tools\"}")])
    m2 = sc.m(s, model="ma", effort=[LOW], score="60%")
    r = sc.run()
    eq(r.cfg(m1), "between-tools", "the setting")
    eq(r.q(m1), "out:effort-not-established", "between-tools is out of the fit, as lqm.load has it")
    eq("not fitted" in r[m1]["reason_detail"]["quality"], True, "the detail says why")
    eq(r.rows("fit-quality.csv", effort="between-tools"), [], "not written to the fit table")
    eq(r.q(m2), "out:single-couple", "its group partner is left alone")


@test
def ext_split_default_thinking_and_effort():
    # Anthropic Opus 4.5–4.8, Sonnet 4.6: a call with no thinking field is thinking off; the effort default (high)
    # applies to a call that turns thinking on without a level (registry fix, 26 Oct 2026)
    sc = base()
    sc.model("mt", configs=("nothink", "low", "high"), default=[
        dict(iv("2026-01-01", "2026-12-31", from_basis="stated", to_basis="stated"), configuration="nothink", setting="thinking"),
        dict(iv("2026-01-01", "2026-12-31", from_basis="stated", to_basis="stated"), configuration="high", setting="effort")])
    s = sc.source("a")
    m1 = sc.m(s, model="mt", effort=[("no-effort-sent", "null")])
    m2 = sc.m(s, model="mt", effort=[("no-effort-sent", "null"), ("thinking-on", "adaptive")], score="60%")
    r = sc.run()
    eq(r.cfg(m1), "nothink", "no thinking field, no effort: the thinking default")
    eq(r.cfg(m2), "high", "thinking on, no effort: the effort default")


@test
def ext_harness_per_provider():
    # a harness maps a level per provider: records with `via` (the next step) and `maker` (registry fix, 26 Oct)
    sc = base()
    sc.model("mz", configs=("low", "high", "xhigh", "max"))
    sc.route("orz", "router", spellings=["ORZ"], models={"mz": {"accepts": [
        dict(iv("2026-01-01", "2026-12-31", from_basis="stated", to_basis="stated"), configuration=c)
        for c in ("low", "high", "xhigh")]}})
    sc.route("hz", "harness", spellings=["HZ"], level_mapping=[
        dict(iv("2026-01-01", "2026-12-31", from_basis="stated", to_basis="stated"), rule="identity", via="maker-api",
             maker="anthropic"),
        dict(iv("2026-01-01", "2026-12-31", from_basis="stated", to_basis="stated"), rule="identity", via="orz")])
    sc.routes["hz"]["mapping"] = [dict(iv("2026-01-01", "2026-12-31", from_basis="stated", to_basis="stated"),
                                       requested="max", served="xhigh", via="orz")]
    s = sc.source("a")
    m1 = sc.m(s, model="mz", effort=[("effort-setting", "max")], route=[("HZ", None), ("Maker API", "maker-api")])
    m2 = sc.m(s, model="mz", effort=[("effort-setting", "max")], route=[("HZ", None), ("ORZ", None)], score="60%")
    m3 = sc.m(s, model="mz", effort=[LOW], route=[("HZ", None), ("ORZ", None)], score="55%")
    m4 = sc.m(s, model="ma", effort=[LOW], route=[("HZ", None), ("ORZ", None)], score="45%")
    r = sc.run()
    eq(r.cfg(m1), "max", "to the maker's API: identity (anthropic provider)")
    eq(r.cfg(m2), "xhigh", "to the router: max sent as xhigh")
    eq(r.cfg(m3), "low", "to the router: identity")
    eq(r.q(m4), "out:effort-not-established", "ma has no entry at orz: the router documents nothing for it")


@test
def ext_closed_harness_label():
    # a closed harness that documents nothing: its label is the level sent, flagged (the maintainer, 26 Oct); a
    # harness without the rule still documents nothing, so the configuration is not established
    sc = base()
    sc.model("mz", configs=("low", "high"))
    sc.route("orz", "router", spellings=["ORZ"], models={"mz": {"accepts": [
        dict(iv("2026-01-01", "2026-12-31", from_basis="stated", to_basis="stated"), configuration="low")]}})
    sc.route("cz", "harness", spellings=["CZ"])
    sc.routes["cz"]["label_as_level"] = {"rule": "closed-harness-label", "date": "2026-10-26",
                                         "decided_by": "the maintainer"}
    sc.route("hz", "harness", spellings=["HZ"])
    s = sc.source("a")
    m1 = sc.m(s, model="mz", effort=[HIGH], route=[("CZ", None)])
    m2 = sc.m(s, model="mz", effort=[LOW], route=[("CZ", None)], score="55%")
    m3 = sc.m(s, model="mz", effort=[HIGH], route=[("HZ", None)], score="58%")
    r = sc.run()
    eq(r.cfg(m1), "high", "closed harness: the label is the level")
    eq("harness-label-as-level:cz" in r[m1]["flags"], True, "flagged")
    eq(r.cfg(m2), "low", "closed harness: low")
    eq(r.q(m3), "out:effort-not-established", "a harness without the rule documents nothing")


@test
def ext_label_med_abbreviation():
    # a chart legend's "Med" names medium (Anthropic system cards, 26 Oct)
    import build as B
    eq((B.map_label(None, "Med"), B.map_label(None, "med effort"), B.map_label(None, "Medium")), ("medium",) * 3, "Med")
    eq("media" in B.LEVEL_TOKEN_ALIASES, False, "whole tokens only")


@test
def ext_display_name_without_brand():
    # 'Haiku 5.5' in a system card is the display name 'Claude Haiku 5.5' (leading maker spellings dropped, 26 Oct)
    import validate as VV, json as _j
    voc = _j.load(open(os.path.join(DATA, "schema", "vocab.json")))
    eq(VV.norm_display("Haiku 5.5", voc), VV.norm_display("Claude Haiku 5.5", voc), "brand dropped")
    eq(VV.norm_display("Anthropic Claude Haiku 5.5", voc), "haiku5.5", "both spellings dropped")
    eq(VV.norm_display("Qwen 3.6 Plus", voc), VV.norm_display("Qwen3.6-Plus", voc), "a space before the version")
    eq(VV.norm_display("GPT\u20115.5", voc), VV.norm_display("GPT-5.5", voc), "a non-breaking hyphen")
    eq(VV.norm_display("Claude", voc), "claude", "a name that is only the brand stays")


@test
def ext_chart_effort_order():
    # an effort chart (its caption says the points are effort levels): the k-th of n points in cost order is the
    # model's k-th level when it has n levels, flagged; else ambiguous (the maintainer, 26 Oct)
    sc = base()
    sc.model("mz", configs=("low", "medium", "high", "xhigh", "max"))
    s = sc.source("card")
    cap = sc.fact(s, "effort-label", "reasoning-effort scaling", quote="HLE reasoning-effort scaling")
    nocap = sc.fact(s, "effort-label", "HLE accuracy", quote="Accuracy on HLE")
    eo = lambda k, n, c=cap: ("effort-order", f"{k}/{n}", {"level": "computed", "rule": "chart-effort-order", "inputs": [c]})
    m1 = sc.m(s, model="mz", effort=[eo(3, 5)], score="50%")
    m2 = sc.m(s, model="mz", effort=[eo(5, 5)], score="60%")
    m3 = sc.m(s, model="mz", effort=[eo(2, 4)], score="45%")
    m4 = sc.m(s, model="mz", effort=[eo(1, 5, nocap)], score="40%")
    r = sc.run()
    eq((r.cfg(m1), r.cfg(m2)), ("high", "max"), "3rd and 5th of 5")
    eq("effort-from-chart-order" in r[m1]["flags"], True, "flagged")
    eq(r[m3]["fields"]["configuration"]["level"], "not-established:ambiguous", "4 points, 5 levels")
    eq(r.q(m4), "out:no-proof", "a caption that does not say effort: the computed fact has no proof")


@test
def ext_thinking_on_default_level():
    # "(Reasoning)" with no level on a model with levels and no `think`: the maker's documented effort default
    # (flag level-from-default); a model with `think` keeps think (26 Oct)
    win = dict(from_basis="stated", to_basis="stated")
    sc = base()
    sc.model("ml", configs=("low", "medium", "high"), default=[dict(iv("2026-01-01", "2026-12-31", **win), configuration="high")])
    sc.model("mh", configs=("nothink", "think"))
    sc.model("mn", configs=("low", "high"))
    s = sc.source("a")
    lab = ("effort-label", "(Reasoning)")
    m1 = sc.m(s, model="ml", effort=[lab], score="50%")
    m2 = sc.m(s, model="mh", effort=[lab], score="60%")
    m3 = sc.m(s, model="mn", effort=[lab], score="40%")
    r = sc.run()
    eq((r.cfg(m1), "level-from-default" in r[m1]["flags"]), ("high", True), "the documented default level")
    eq(r.cfg(m2), "think", "a model with think")
    eq(r.q(m3), "out:effort-not-established", "no documented default")
    sc = base()
    sc.model("ml", configs=("low", "medium", "high"), default=[dict(iv("2026-01-01", "2026-12-31", **win), configuration="high")])
    s = sc.source("card")
    m4 = sc.m(s, model="ml", effort=[("effort-label", "Thinking")], score="50%")
    sc.m(s, model="mb", effort=[LOW], score="40%")
    r = sc.run()
    eq(r.cfg(m4), "high", "a bare 'Thinking' column label")


@test
def ext_run_before_shutdown():
    # a page read after a closed model's shutdown: its run lies before the shutdown, so a configuration ending there
    # still covers it (26 Oct); an open-weights model is not capped
    win = dict(from_basis="stated", to_basis="stated")
    sc = base()
    cf = lambda c: {"id": c, "served": "itself", **iv("2026-01-01", "2026-06-30", **win)}
    sc.model("mo", released="2026-01-01", names=[name("mo-1", "2026-01-01", "2026-06-30")], configs=(cf("low"), cf("high")))
    s = sc.source("a", published="2026-09-01")
    m1 = sc.m(s, model="mo-1", effort=[LOW], score="50%")
    r = sc.run()
    eq(r.cfg(m1), "low", "the run is capped at the shutdown")
    eq(r[m1]["fields"]["run_date_detail"]["mo"]["basis"]["hi"], "shutdown", "basis")


@test
def ext_none_label_and_complement():
    # an effort legend 'none' is nothink; a printed error rate whose complement the setup holds (26 Oct)
    sc = base()
    sc.model("mq", configs=("nothink", "low", "high"))
    s = sc.source("post")
    rate = sc.fact(s, "score", "12.5%", term="pass%", scale="percent")
    m1 = sc.m(s, model="mq", effort=[("effort-label", "none")], score="70%")
    m2 = sc.m(s, model="mq", effort=[LOW], score="87.5%", value_level="computed",
              value_kw={"rule": "complement-of-percent", "inputs": [rate]})
    sc.m(s, model="ma", effort=[LOW], score="80%")
    r = sc.run()
    eq(r.cfg(m1), "nothink", "'none' legend")
    eq(r.q(m2), "in", "100 − 12.5")
    sc = base()
    s = sc.source("post")
    rate = sc.fact(s, "score", "0.3681", term="pass%", scale="fraction")
    m3 = sc.m(s, model="ma", effort=[LOW], score="63.19%", value_level="computed",
              value_kw={"rule": "complement-of-percent", "inputs": [rate]})
    sc.m(s, model="mb", effort=[LOW], score="70%")
    r = sc.run()
    eq(r.q(m3), "in", "100 − a fraction input in percent")


@test
def ext_epoch_ms_date():
    import build as B
    eq(B.find_date("1760572800000")[0].isoformat(), "2025-10-16T00:00:00", "epoch milliseconds")
    eq(B.find_date("12345"), None, "not a timestamp")


@test
def ext_max_label_on_model_without_max():
    # "max effort" written for a model whose list has no max at any date: its highest level, flagged (27 Oct)
    sc = base()
    sc.model("mx5", configs=("low", "medium", "high", "xhigh"))
    sc.model("mm5", configs=("low", "high", "max"))
    s = sc.source("card")
    m1 = sc.m(s, model="mx5", effort=[("effort-label", "max effort")], score="50%")
    m2 = sc.m(s, model="mm5", effort=[("effort-label", "max effort")], score="60%")
    r = sc.run()
    eq((r.cfg(m1), "max-as-highest" in r[m1]["flags"]), ("xhigh", True), "highest level")
    eq(r.cfg(m2), "max", "a model with max")


@test
def ext_restated_from_providers():
    # "Providers' self reported numbers" restates each model's maker: restated-from:<the model's maker> (27 Oct)
    sc = base()
    s = sc.source("card", publisher="puby")
    m1 = sc.m(s, model="ma", effort=[LOW], restated_from="Providers' self reported numbers")
    sc.m(s, model="mb", effort=[LOW], score="60%")
    r = sc.run()
    eq("restated-from:Anthropic" in r.rows("fit-quality.csv", model="ma")[0]["confound"], True, "the model's maker")


@test
def ext_decimal_comma_and_counts_words():
    # a source with decimal_mark "," reads '12,5' as 12.5 and '1.234,5' as 1234.5; 'k из N' is a counts score (27 Oct)
    sc = base()
    s = sc.source("habr")
    sc.sources[s]["decimal_mark"] = ","
    m1 = sc.m(s, model="ma", effort=[LOW], score="12,5%")
    m2 = sc.m(s, model="mb", effort=[LOW], score="45 из 60", scale="counts")
    t = sc.source("en")
    m3 = sc.m(t, model="ma", effort=[HIGH], score="12,5%")
    r = sc.run()
    eq(r.rows("fit-quality.csv", model="ma", effort="low")[0]["score"], "12.5", "decimal comma")
    eq(r.rows("fit-quality.csv", model="mb", group="s1")[0]["score"], "75", "из")
    eq(r.q(m3) == "in" and r.rows("fit-quality.csv", model="ma", effort="high")[0]["score"] == "125", True,
       "no decimal_mark: the comma is a thousands separator, as before")
    import build as B
    x = B.Fact(value="1.234,5"); B.Source("p", {"id": "x", "publisher": "p", "decimal_mark": ","}, None).decimal(x)
    eq(x["value"], "1234.5", "thousands dot")


@test
def ext_thinking_on_with_level_on_levels_only_model():
    # thinking on plus a stated level, on a model whose list has levels and no `think`: the level, not a contradiction
    # with the maker's default that thinking on alone would read (bazaar-2608.00102, 27 Oct)
    sc = base()
    win = dict(from_basis="stated", to_basis="stated")
    sc.model("ml5", configs=("low", "medium", "high"),
             default=[dict(iv("2026-01-01", "2026-12-31", **win), configuration="medium")])
    s = sc.source("p")
    m1 = sc.m(s, model="ml5", effort=[("thinking-on", "thinking enabled"), ("effort-label", "high")], score="50%")
    sc.m(s, model="ma", effort=[LOW], score="40%")
    r = sc.run()
    eq((r.cfg(m1), "level-from-default" in r[m1]["flags"]), ("high", False), "the stated level")


@test
def ext_cents_cjk_ladder_nothink_spellings():
    # '51¢' / '10.017 cents' are US cents (/100); 最大值/最低 name the top/bottom level; 'no reasoning' and
    # 'Reasoning:disabled' are thinking off (28 Oct)
    import build as B
    eq(B.parse_number("51¢"), (B.Decimal("0.51"), B.Decimal("0.01")), "cents sign")
    eq(B.parse_number("10.017 cents")[0], B.Decimal("0.10017"), "cents word")
    eq(B.parse_number("$51")[0], B.Decimal("51"), "dollars unchanged")
    cf = {"low": 1, "medium": 1, "high": 1}
    eq((B.label_to_ladder("最大值", cf)[0], B.label_to_ladder("最低", cf)[0], B.label_to_ladder("中", cf)[0]),
       ("high", "low", None), "CJK ladder")
    sc = base()
    sc.model("mn", configs=("nothink", "low", "high"))
    s = sc.source("p")
    m1 = sc.m(s, model="mn", effort=[("effort-label", "no reasoning")], score="50%")
    m2 = sc.m(s, model="mn", effort=[("effort-label", "Reasoning:disabled")], score="40%")
    m3 = sc.m(s, model="mn", effort=[("effort-label", "reasoning")], score="45%")
    sc.m(s, model="ma", effort=[LOW], score="30%")
    r = sc.run()
    eq((r.cfg(m1), r.cfg(m2), r.cfg(m3) == "nothink"), ("nothink", "nothink", False), "nothink spellings")


@test
def ext_quantized_build_is_out():
    # 'runs on my laptop at ~Q4 quantization': the maker's model as a quantized build is another artefact (deepu,
    # the maintainer 29 Oct); the same name without that fact is the model
    sc = base()
    s = sc.source("p")
    m1 = sc.m(s, model="ma", effort=[LOW], score="50%", model_facts=[("quantized-build", "~Q4 quantization", {})])
    m2 = sc.m(s, model="ma", effort=[HIGH], score="60%")
    sc.m(s, model="mb", effort=[LOW], score="40%")
    r = sc.run()
    eq((r.q(m1), r.q(m2)), ("out:model-not-established", "in"), "quantized out, the model in")


@test
def ext_agent_reading_with_written_text():
    # the agent writes its reading (12.5) and the text as written ('12,5 %'): the build takes the reading; a reading
    # whose digits disagree with the text is a fault (29 Oct, the maintainer: the agents read the values)
    import sys as _s
    _s.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "schema"))
    import validate as V
    eq((V.digits_agree("12.5", "12,5 %"), V.digits_agree("0.51", "51¢"), V.digits_agree("13", "12,5 %")),
       (True, True, False), "digits")
    sc = base()
    s = sc.source("p")
    sc.sources[s]["decimal_mark"] = ","
    m1 = sc.m(s, model="ma", effort=[LOW], score="12.5", value_kw={"written": "12,5 %"})
    m2 = sc.m(s, model="mb", effort=[LOW], score="1.234", value_kw={"written": "1,234"})
    r = sc.run()
    eq((r.rows("fit-quality.csv", model="ma")[0]["score"], r.rows("fit-quality.csv", model="mb")[0]["score"]),
       ("12.5", "1.234"), "the reading, not re-read")


@test
def ext_metric_mean():
    # no headline designated, benchmark unknown: the mean of the entry's same-scale metrics (the maintainer, 29 Oct)
    for stated, want in (("70", "in"), ("72", "out:no-proof")):
        sc = base()
        s = sc.source("a")
        fa = sc.fact(s, "score", "80", about="ma-1", term="pass%", scale="percent")
        fb = sc.fact(s, "score", "60", about="ma-1", term="pass%", scale="percent")
        m1 = sc.m(s, model="ma", effort=[LOW], score=stated, value_level="computed",
                  value_kw={"rule": "metric-mean", "inputs": [fa, fb]})
        sc.m(s, model="mb", effort=[LOW], score="60%")
        r = sc.run()
        eq(r.q(m1), want, f"stated {stated}, mean of 80 and 60")


@test
def ext_single_key_name_with_an_end():
    # a name on one key that stopped serving it (a successor snapshot, undocumented move: qwen3.8-max, 29 Oct): a run
    # inside its interval resolves, one after it does not; a name ending at its last capture is not date-checked
    sc = base()
    n1 = name("q-max", "2026-01-01", "2026-06-30"); n1["serves"][0]["to_basis"] = "successor-release"
    n2 = name("q-other", "2026-01-01", "2026-06-30"); n2["serves"][0]["to_basis"] = "last-capture"
    sc.model("aq", released="2026-01-01", names=[n1, n2])
    s = sc.source("a", published="2026-10-01")
    m1 = sc.m(s, model="q-max", effort=[LOW], run_date=[("run-date", "2026-05-01")])
    m2 = sc.m(s, model="q-max", effort=[LOW], run_date=[("run-date", "2026-08-01")])
    m3 = sc.m(s, model="q-other", effort=[LOW], run_date=[("run-date", "2026-08-01")])
    sc.m(s, model="ma", effort=[LOW])
    r = sc.run()
    eq((r.model(m1), r.q(m2), r.model(m3)), ("aq", "out:model-not-established", "aq"), "dated single-key name")


@test
def ext_metric_open_and_judgment_basis():
    # a metric named as the source prints it is accepted (not only the legacy list); headline bases standard /
    # judgment / metric-mean exist (the maintainer, 29 Oct)
    import sys as _s
    _s.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "schema"))
    import validate as V
    sch = V.Schemas(os.path.join(os.path.dirname(__file__), "..", "schema"))
    eq((V.in_vocab(sch, "metric", "Final IoU"), V.in_vocab(sch, "metric", " padded "),
        V.in_vocab(sch, "headline_basis", "judgment"), V.in_vocab(sch, "headline_basis", "guess")),
       (True, False, True, False), "open metric, closed basis")


@test
def lqm_configurations_kept():
    """lqm.load keeps the configurations the build writes (nothink, minimal, think, solo and the levels) and not an
    unknown one; negative control: with the filter of before the change (levels and solo only) the same file loses the
    three new ones, so the test would fail on it."""
    import csv, tempfile
    sys.path.insert(0, os.path.join(DATA, "..", "model"))
    import lqm
    rows = [("g1", "pubA", "ma", "low", 60.0), ("g1", "pubA", "ma", "nothink", 40.0), ("g1", "pubA", "ma", "high", 70.0),
            ("g1", "pubA", "mb", "think", 55.0), ("g1", "pubA", "mb", "minimal", 35.0), ("g1", "pubA", "mb", "solo", 50.0),
            ("g1", "pubA", "mb", "between-tools", 52.0), ("g1", "pubA", "mb", "effort", 53.0)]
    head = ["group", "source", "model", "effort", "task_type", "complexity", "harness", "unit", "cost_usd", "cost_prec",
            "tokens_in", "tokens_out", "score", "score_metric", "score_prec", "cached_pct", "confound", "ref"]
    d = tempfile.mkdtemp(prefix="lqm-cfg-")
    try:
        p = os.path.join(d, "fit-quality.csv")
        with open(p, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(head)
            for g, src, m, e, v in rows:
                w.writerow([g, src, m, e, "coding", "", "h", "per-task", "", "", "", "", v, "pass%", "", "", "", "r"])
        def kept():
            groups, _, _ = lqm.load(p, {"ma", "mb"})
            return sorted(x["couple"] for G in groups.values() for x in G["rows"])
        want = ["ma@high", "ma@low", "ma@nothink", "mb@minimal", "mb@solo", "mb@think"]
        eq(kept(), want, "nothink, minimal, think and solo kept; between-tools and an odd label out")
        new = lqm.EFFORTS
        lqm.EFFORTS = {"low", "medium", "high", "xhigh", "max", "solo"}          # the filter of before the change
        try:
            eq(kept(), ["ma@high", "ma@low", "mb@solo"], "negative control: the old filter drops the three configurations")
        finally:
            lqm.EFFORTS = new
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test
def configurations_vocab_is_lqm_efforts():
    """The build's in-fit configurations (vocab x-terms in_fit true; think-<n> has its own step) are lqm.EFFORTS, both
    ways, so that the tree never writes a row `in` that lqm.load drops, nor drops one it would keep. Negative control:
    with between-tools added to lqm.EFFORTS (its state before this check) the comparison fails."""
    import json
    sys.path.insert(0, os.path.join(DATA, "..", "model"))
    import lqm
    with open(os.path.join(DATA, "schema", "vocab.json"), encoding="utf-8") as f:
        terms = json.load(f)["$defs"]["configuration"]["x-terms"]
    tree = {k for k, v in terms.items() if v.get("in_fit") is not False and not k.startswith("think-")}
    eq(tree, set(lqm.EFFORTS), "vocab in_fit true = lqm.EFFORTS")
    eq(tree == set(lqm.EFFORTS) | {"between-tools"}, False, "negative control: one list wider than the other fails")


@test
def lqm_guard_configuration_not_in_efforts():
    """A fit-table row whose configuration lqm.EFFORTS does not hold never keeps the status `in`: build_lqm gives it
    out:effort-not-established with the reason. Negative control: the same build with lqm.EFFORTS whole keeps it in."""
    sys.path.insert(0, os.path.join(DATA, "..", "model"))
    import lqm

    def scenario():
        sc = base()
        s = sc.source("a")
        refs = [sc.m(s, model=m, effort=[e], score=v) for m, e, v in
                (("ma", LOW, "40%"), ("mb", LOW, "50%"), ("ma", HIGH, "60%"), ("mb", HIGH, "70%"))]
        return sc.run(lqm=True), refs
    r, (a_lo, b_lo, a_hi, b_hi) = scenario()
    eq((r.q(a_hi), r.q(b_hi)), ("in", "in"), "negative control: high in lqm.EFFORTS, in")
    saved = lqm.EFFORTS
    lqm.EFFORTS = set(saved) - {"high"}
    try:
        r, (a_lo, b_lo, a_hi, b_hi) = scenario()
    finally:
        lqm.EFFORTS = saved
    eq((r.q(a_hi), r.q(b_hi)), ("out:effort-not-established",) * 2, "high filtered by lqm.load: not in")
    eq(r[a_hi]["reason_detail"]["quality"], "lqm.load (phase 1): high is not in lqm.EFFORTS", "the reason")
    eq((r.q(a_lo), r.q(b_lo)), ("in", "in"), "the low rows stand")


# ================================================================ the fit reads the build (29 Oct 2026)
@test
def fit_reads_build_tables():
    """model/fit.py's reading of a build: lqm.load on the axis' table with the group-keyed maps resolved through
    group-map.json and group-setups.json (build_lqm.fit_maps, load_table). The composite is a fit group named per
    publisher ('comp@puby'), which the catalog's maps do not know: through the maps its row is dropped as the build
    said (out:composite); without them (negative control) lqm.load keeps it."""
    import json, tempfile
    sys.path[:0] = [os.path.join(DATA, "..", "model"), DATA]
    import lqm, build_lqm
    sc = base()
    sc.setup("c1", family="f1")
    sc.setup("c2", family="f2")
    sc.setup("comp", family="fc", composite={"components": ["c1", "c2"], "formula": {"weights": {"c1": 1, "c2": 1}},
                                             "linear": True, "evidence": EV})
    s, t = sc.source("a"), sc.source("b", publisher="puby")
    k1 = sc.m(s, setup="comp", model="ma", effort=[LOW], score="60%")
    sc.m(s, setup="comp", model="mb", effort=[LOW], score="65%")
    sc.m(t, setup="comp", model="ma", effort=[LOW], score="62%")
    sc.m(t, setup="comp", model="mb", effort=[LOW], score="70%")
    sc.m(s, setup="c1", model="ma", effort=[LOW], score="50%")
    sc.m(s, setup="c1", model="mb", effort=[LOW], score="80%")
    keep = tempfile.mkdtemp(prefix="fitread-")
    try:
        r = sc.run(lqm=True, keep=keep)
        eq(r.q(k1), "out:composite", "the build: the composite row is out")
        gm, gs = build_lqm.read_maps(keep)
        eq(gm.get("comp@pubx"), "comp", "fit group → base group")
        eq(gs["groups"].get("comp@pubx"), "comp", "fit group → setup")
        eq(gs["setups"]["comp"]["components"], ["c1", "c2"], "the setup's components")
        models = r.rep["build"]["fit_models"]
        g, _, _ = build_lqm.load_table(lqm, "quality", models, keep)
        rows = lambda G: sorted((k, x["couple"]) for k, v in G.items() for x in v["rows"])
        eq(("comp@pubx", "ma@low") in rows(g), False, "through the maps: dropped")
        g0, _, _ = lqm.load(build_lqm.table("quality", keep), models, field="score")
        eq(("comp@pubx", "ma@low") in rows(g0), True, "negative control, without the maps: kept")
        eq(lqm.COMPOSITES.get("comp@pubx"), None, "the catalog maps restored after the block")
    finally:
        shutil.rmtree(keep, ignore_errors=True)


@test
def site_ladder_switch():
    """The site's effort-ladder report: on a model whose maker's thinking is a switch (vocab maker x-terms.thinking,
    Anthropic) thinking off above low is not an inversion, and thinking off is compared with thinking on; on another
    maker's model (OpenAI: reasoning_effort none) it is the rung below low. Negative control: with no switch model,
    the Anthropic model's nothink > low is flagged."""
    sys.path.insert(0, os.path.join(DATA, "..", "site"))
    import grids
    sw = grids.thinking_switch()
    eq(("opus-4.8" in sw, "haiku-4.5" in sw, "gpt-5.5" in sw), (True, True, False), "switch from the registry")
    cg = {"opus-4.8": {"nothink": [1.0, .1], "low": [0.5, .1], "high": [2.0, .1]},
          "gpt-5.5": {"nothink": [1.0, .1], "low": [0.5, .1]}, "haiku-4.5": {"nothink": [1.0, .1], "think": [0.8, .1]}}
    eq(grids.monotonicity_report(cg, {}), ["cost: gpt-5.5 nothink(1.0) > low(0.5)",
                                           "cost: haiku-4.5 nothink(1.0) > think(0.8)"], "switch models")
    eq("cost: opus-4.8 nothink(1.0) > low(0.5)" in grids.monotonicity_report(cg, {}, switch=set()), True,
       "negative control: the full ladder")


def main():
    import review_tests, pilot_tests, gaps2_tests, sampler_tests
    TESTS.extend(gaps2_tests.TESTS)
    TESTS.extend(sampler_tests.TESTS)
    for t in pilot_tests.TESTS:
        TESTS.append(t)
    for t in review_tests.TESTS:
        t.__name__ = "review_" + t.__name__
        TESTS.append(t)
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
