#!/usr/bin/env python3
"""The independent review's fixtures (/work/.salvo14/review-build/review_tests.py, 22 Oct 2026), written from
docs/DATA-PIPELINE.md's text, kept in the suite (data/tests/run.py runs them). One expectation was changed, where the
spec makes it wrong: same_runs_regrade_later_refused (see the test)."""
import os, sys, traceback, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fixtures import Sc, iv, name, price, EV  # noqa: E402

TESTS = []
def test(f):
    TESTS.append(f); return f
def eq(got, want, what=""):
    if got != want:
        raise AssertionError(f"{what}: got {got!r}, want {want!r}")

LOW, HIGH, MED = ("effort-setting", "low"), ("effort-setting", "high"), ("effort-setting", "medium")
WIN = dict(from_basis="earliest-capture", to_basis="last-capture")
def base(as_of="2026-10-01"):
    sc = Sc(as_of); sc.model("ma"); sc.model("mb"); sc.setup("s1"); return sc
def same_price(sc, *models, classes=None, currency="USD"):
    for k in models:
        sc.prices["prices"].append(price(k, "2026-01-01", "2026-10-01", classes or {"input": 1, "output": 5}, currency=currency))

# 1a. alias near its switch, stated run date on the last day before the redirect
@test
def alias_switch_stated_day():
    sc = base()
    sc.model("aa1", released="2026-01-01", names=[name("alias-x", "2026-01-01", "2026-03-31")])
    sc.model("aa2", released="2026-04-01", names=[name("alias-x", "2026-04-01")])
    s = sc.source("a", published="2026-04-10")
    m1 = sc.m(s, model="alias-x", effort=[LOW], run_date=[("run-date", "2026-03-31")])
    m2 = sc.m(s, model="alias-x", effort=[LOW], run_date=[("run-date", "2026-04-01")])
    r = sc.run()
    eq(r.model(m1), "aa1", "run on 31 Mar: the alias still served aa1")
    eq(r.model(m2), "aa2", "run on 1 Apr: aa2")

# 1b. alias, no run date, publication after the switch: the run may have been before it -> not established
@test
def alias_switch_no_run_date():
    sc = base()
    sc.model("aa1", released="2026-01-01", names=[name("alias-x", "2026-01-01", "2026-03-31")])
    sc.model("aa2", released="2026-04-01", names=[name("alias-x", "2026-04-01")])
    s = sc.source("a", published="2026-05-01")
    m1 = sc.m(s, model="alias-x", effort=[LOW])
    r = sc.run()
    eq(r.model(m1), None, "run interval [?, 1 May] spans the redirect: the alias cannot be placed "
                          "(spec: the run interval must lie inside one serves interval)")

# 2. conversion documented from 1 May (earliest capture); run stated 10 Jun -> covered; run with only an upper bound -> not
@test
def conversion_dated_after_lower_bound():
    sc = base()
    conv = [dict(iv("2026-05-01", "2026-12-31", **WIN), route="maker-api", requested="max", served="high")]
    sc.model("mc", configs=("low", "high", {"id": "max", "served": "converted", **iv("2026-01-01", None)}),
             conversions=conv)
    s = sc.source("a", published="2026-06-20")
    m1 = sc.m(s, model="mc", effort=[("effort-setting", "max")], run_date=[("run-date", "2026-06-10")])
    m2 = sc.m(s, model="mc", effort=[("effort-setting", "max")], run_date=[("run-end", "2026-06-10")])
    r = sc.run()
    eq(r.cfg(m1), "high", "stated run date inside the conversion's dated interval")
    eq(r.q(m2), "out:effort-not-established", "lower bound = release (Jan), before the conversion's evidence")

# 3. router default, route known vs unknown
@test
def router_default_known_unknown():
    sc = base()
    sc.model("kk", configs=("low", "medium", "high", "max"),
             default=[dict(iv("2026-01-01", "2026-12-31", **WIN), configuration="high")])
    sc.route("openrouter", "router", spellings=["OpenRouter"], models={"kk": {
        "ids": [dict(iv("2026-01-01", "2026-12-31", **WIN), name="x/kk")],
        "default": [dict(iv("2026-07-21", "2026-07-21", **WIN), configuration="max")],
        "accepts": [dict(iv("2026-01-01", "2026-12-31", **WIN), configuration=c) for c in ("low", "medium", "high", "max")]}})
    s = sc.source("a", published="2026-07-25")
    nes = [("no-effort-sent", "null")]
    m1 = sc.m(s, model="kk", effort=nes, route=[("OpenRouter", None)], run_date=[("run-date", "2026-07-21")])
    m2 = sc.m(s, model="kk", effort=nes, run_date=[("run-date", "2026-07-21")])
    m3 = sc.m(s, model="kk", effort=nes, route=[("OpenRouter", None)], run_date=[("run-date", "2026-07-23")])
    r = sc.run()
    eq(r.cfg(m1), "max", "route known: the router's own documented default")
    eq(r.q(m2), "out:effort-not-established", "route unknown: maker high vs router max disagree")
    eq(r.q(m3), "out:effort-not-established", "a single capture covers its own day only (21 Jul), run 23 Jul")

# 4. hybrid think
@test
def hybrid_think():
    sc = base()
    sc.model("qh", configs=("nothink", "think"), maker="alibaba")
    sc.model("ql", configs=("nothink", "low", "medium", "high"), maker="alibaba")
    s = sc.source("a")
    m1 = sc.m(s, model="qh", effort=[("effort-setting", "enable_thinking: true")])
    m2 = sc.m(s, model="qh", effort=[("effort-label", "Qwen3.6 Thinking")])
    m3 = sc.m(s, model="ql", effort=[("thinking-on", "enable_thinking: true")])
    m4 = sc.m(s, model="qh", effort=[("effort-setting", "enable_thinking: false")])
    r = sc.run()
    eq(r.cfg(m1), "think", "setting line enable_thinking: true")
    eq(r.cfg(m2), "think", "label '<name> Thinking'")
    eq(r.q(m3), "out:effort-not-established", "think is not in a laddered hybrid's list")
    eq((r.cfg(m4), r.q(m1), r.q(m4)), ("nothink", "in", "in"), "nothink and think are couples of the hybrid")

# 5. Haiku 4.5 nothink via the maker's default, maker API and route unknown with a reseller
@test
def haiku_nothink_default():
    sc = base()
    sc.model("haiku-4.5", configs=("nothink", "think-<budget>"), released="2025-10-15",
             default=[dict(iv("2025-10-15", "2026-12-31", from_basis="stated", to_basis="last-capture"), configuration="nothink")])
    sc.route("bedrock", "reseller", spellings=["Bedrock"], models={"haiku-4.5": {
        "ids": [dict(iv("2025-10-15", "2026-12-31", **WIN), name="anthropic.claude-haiku-4-5")]}})
    s = sc.source("a")
    nes = [("no-effort-sent", "no thinking parameter")]
    m1 = sc.m(s, model="haiku-4.5", effort=nes, route=[("Maker API", "maker-api")])
    m2 = sc.m(s, model="haiku-4.5", effort=nes)
    m3 = sc.m(s, model="ma", effort=[LOW])
    r = sc.run()
    eq((r.cfg(m1), r.q(m1)), ("nothink", "in"), "maker API: documented default nothink")
    eq((r.cfg(m2), r.q(m2)), ("nothink", "in"), "route unknown: maker and reseller (maker's default) agree")

# 6. continuation within a version, then a new version, then a continuation of the new version
@test
def campaigns_chain():
    sc = base(); sc.model("mc")
    s1 = sc.source("board", published="2026-05-01")
    a1 = sc.m(s1, model="ma", effort=[LOW], score="50%", version="1.0")
    b1 = sc.m(s1, model="mb", effort=[LOW], score="60%", version="1.0")
    s2 = sc.source("board", published="2026-06-01", snapshot_of=s1)
    a2 = sc.m(s2, model="ma", effort=[LOW], score="55%")
    c2 = sc.m(s2, model="mc", effort=[LOW], score="65%")
    s3 = sc.source("board", published="2026-07-01", snapshot_of=s2)
    a3 = sc.m(s3, model="ma", effort=[LOW], score="40%", version="2.0")
    b3 = sc.m(s3, model="mb", effort=[LOW], score="45%", version="2.0")
    s4 = sc.source("board", published="2026-08-01", snapshot_of=s3)
    a4 = sc.m(s4, model="ma", effort=[LOW], score="42%")
    r = sc.run()
    eq((r.q(a1), r.q(a2)), ("out:superseded", "in"), "within 1.0 the later replaces")
    eq((r.q(b1), r.q(c2)), ("in", "in"), "b1 not re-measured stays; c2 joins 1.0")
    eq(r[a4]["campaign"], "2.0", "s4 inherits 2.0 from s3")
    eq((r.q(a3), r.q(a4), r.q(b3)), ("out:superseded", "in", "in"), "within 2.0")

# 6b. versions compared as strings: a snapshot continuing a source that states 9 and 10
@test
def campaign_inherit_numeric_version():
    sc = base()
    s1 = sc.source("board", published="2026-05-01")
    sc.m(s1, model="ma", effort=[LOW], score="50%", version="9")
    sc.m(s1, model="mb", effort=[LOW], score="51%", version="10")
    s2 = sc.source("board", published="2026-06-01", snapshot_of=s1)
    a2 = sc.m(s2, model="ma", effort=[LOW], score="55%")
    r = sc.run()
    eq(r[a2]["campaign"], "10", "the latest version is 10, not '9' (string order)")

# 7. same-runs-as with a regrade: the later regrade's own measure is refused (no proof)
@test
def same_runs_regrade_later_refused():
    sc = base(); sc.setup("s1b")
    same_price(sc, "ma", "mb")
    s1 = sc.source("run", published="2026-05-01")
    a1 = sc.m(s1, model="ma", effort=[LOW], score="50.0%", cost="1.00")
    b1 = sc.m(s1, model="mb", effort=[LOW], score="60.0%", cost="2.00")
    s2 = sc.source("regrade", published="2026-06-01")
    a2 = sc.m(s2, setup="s1b", model="ma", effort=[LOW], score="52.0%", cost="1.00", same_runs_as=s1, value_form="prose")
    b2 = sc.m(s2, setup="s1b", model="mb", effort=[LOW], score="61.0%", cost="2.00", same_runs_as=s1)
    r = sc.run()
    eq(r.q(a2), "out:no-proof", "the regrade value has no quote")
    # changed from the review's 'in': the accepted regrade b2 does replace b1 (same runs), which leaves a1 alone in
    # its group, so a1 is out:single-couple; what matters is that the refused a2 replaced nothing
    eq(r.q(a1), "out:single-couple", "the earlier grading is not replaced by a refused value (alone after b1 went)")
    eq(r.q(b1), "out:superseded", "the accepted regrade replaces")

# 8a. composite with part of its components (3 components, 2 couples)
@test
def composite_partial_components():
    sc = base()
    for c in ("c1", "c2", "c3"):
        sc.setup(c, family="f" + c)
    sc.setup("comp", family="fc", composite={"components": ["c1", "c2", "c3"],
             "formula": {"weights": {"c1": 1, "c2": 1, "c3": 2}}, "linear": True, "evidence": EV})
    s = sc.source("a")
    ka = sc.m(s, setup="comp", model="ma", effort=[LOW], score="60%")
    kb = sc.m(s, setup="comp", model="mb", effort=[LOW], score="70%")
    sc.m(s, setup="c1", model="ma", effort=[LOW], score="40%")
    sc.m(s, setup="c1", model="mb", effort=[LOW], score="80%")
    sc.m(s, setup="c2", model="mb", effort=[LOW], score="60%")
    r = sc.run(lqm=True)
    ra, rb = r[ka + "~resid"], r[kb + "~resid"]
    eq(ra["setup"], "comp-resid-c2+c3", "ma misses c2, c3")
    eq(round(float(ra["fields"]["score"]["number"]), 6), round((60 - 0.25 * 40) / 0.75, 6), "(C − ¼c1)/¾")
    eq(rb["setup"], "comp-resid-c3", "mb misses c3")
    eq(round(float(rb["fields"]["score"]["number"]), 6), round((70 - 0.25 * 80 - 0.25 * 60) / 0.5, 6), "(C − ¼c1 − ¼c2)/½")
    eq((r.q(ka), r.q(kb)), ("out:composite", "out:composite"), "composite rows dropped by lqm.load")

# 8b. composite on 0-100, component on a fraction metric (0-1): the residual must use one scale
@test
def composite_component_other_scale():
    sc = base()
    sc.setup("c1", family="f1", metric="accuracy", bounds=(0, 1))
    sc.setup("c2", family="f2")
    sc.setup("comp", family="fc", composite={"components": ["c1", "c2"], "formula": {"weights": {"c1": 1, "c2": 1}},
                                             "linear": True, "evidence": EV})
    s = sc.source("a")
    k = sc.m(s, setup="comp", model="ma", effort=[LOW], score="60%")
    sc.m(s, setup="comp", model="mb", effort=[LOW], score="70%")
    sc.m(s, setup="c1", model="ma", effort=[LOW], score="0.5", scale="fraction")
    sc.m(s, setup="c1", model="mb", effort=[LOW], score="0.8", scale="fraction")
    r = sc.run()
    v = float(r[k + "~resid"]["fields"]["score"]["number"]) if (k + "~resid") in r.rep["measures"] else None
    eq(v is None or v <= 100, True, f"residual {v} must stay on the composite's 0-100 scale (70 expected, or no residual)")

# 9. retired model: price cut then retirement; cost from the old period re-priced to the last list price
@test
def retired_model_price():
    sc = base()
    for k in ("ma", "mb"):
        sc.prices["prices"] += [price(k, "2026-01-01", "2026-03-31", {"input": 2, "output": 10}),
                                price(k, "2026-04-01", "2026-06-30", {"input": 1, "output": 5})]
    s = sc.source("a", published="2026-03-01")
    m1 = sc.m(s, model="ma", effort=[LOW], cost="4.0", price_table="prices of 2026-02-01")
    m2 = sc.m(s, model="mb", effort=[LOW], cost="6.0", price_table="prices of 2026-02-01")
    r = sc.run()
    b = r[m1]["fields"]["cost"]["base"]
    eq((b["rule"], b["value"]), ("cost-uniform-factor", 2.0), "× 0.5 to the last list price")
    eq((r.c(m1), "base-last-list-price" in r[m1]["flags"]), ("in", True), "in, flagged")

# 10a. a CNY cost, model priced in CNY on the maker's API
@test
def cny_cost_cny_price():
    sc = base()
    same_price(sc, "ma", "mb", classes={"input": 2, "output": 8}, currency="CNY")
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], cost="¥7.0", currency="CNY")
    m2 = sc.m(s, model="mb", effort=[LOW], cost="¥9.0", currency="CNY")
    r = sc.run()
    eq((r.c(m1), r.c(m2)), ("in", "in"), "CNY cost at a CNY base price")
    eq(r[m1]["fields"]["cost"]["base"]["rule"], "cost-publisher-figure", "rule")

# 10b. a model with USD and CNY list prices: a USD cost must be priced against the USD entry
@test
def usd_cost_model_with_two_currencies():
    sc = base()
    for k in ("ma", "mb"):
        sc.prices["prices"] += [price(k, "2026-01-01", "2026-10-01", {"input": 2, "output": 8}, currency="CNY"),
                                price(k, "2026-01-01", "2026-10-01", {"input": 0.3, "output": 1.2}, currency="USD")]
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], cost="1.0")
    m2 = sc.m(s, model="mb", effort=[LOW], cost="2.0")
    r = sc.run()
    eq(r[m1]["fields"]["cost"].get("base") and r[m1]["fields"]["cost"]["base"]["rule"], "cost-publisher-figure",
       "USD cost, USD price unchanged: publisher figure")

# 11. two metrics of one run on the cost axis
@test
def two_metrics_one_run_cost():
    sc = base()
    sc.setup("s1acc", metric="accuracy%", headline={"metric": "pass%", "basis": "designated", "evidence": EV})
    same_price(sc, "ma", "mb")
    s = sc.source("a")
    out = {}
    for mdl, c in (("ma", "1.0"), ("mb", "2.0")):
        h = sc.m(s, model=mdl, effort=[LOW], score="50%", cost=c)
        spend = sc.msets[s][-1]["facts"]["spend"]
        o = sc.m(s, setup="s1acc", model=mdl, effort=[LOW], score="55%", spend_shared=spend)
        out[mdl] = (h, o)
    r = sc.run(lqm=True)
    h, o = out["ma"]
    eq(r.c(h), "in", "the headline measure carries the cost")
    eq(r[o]["cost_measure"], h, "the other metric is one cost measure with it")
    eq(len(r.rows("fit-cost.csv", model="ma")), 1, "the cost counts once")
    eq(r.rows("fit-cost.csv", model="ma")[0]["group"], "s1", "on the headline measure's setup")

# 11b. a fault in the score fact only must not take the cost out (step 1: every fact *used*)
@test
def score_fault_keeps_cost():
    sc = base()
    same_price(sc, "ma", "mb")
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW], cost="1.0", value_form="prose")   # score fact lacks its quote
    m2 = sc.m(s, model="mb", effort=[LOW], cost="2.0")
    r = sc.run()
    eq(r.q(m1), "out:no-proof", "quality: the score is unproven")
    eq(r.c(m1), "in", "cost: its facts are proven")

# 12a. decision with a stale hash: setup changed; a fact of another measure changed (not stale)
@test
def decision_stale_setup_and_unrelated_fact():
    sc = base(); sc.setup("s9")
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[("effort-setting", "max")])
    m2 = sc.m(s, model="mb", effort=[("effort-setting", "max")])
    sc.decide(m1, "quality", "in")
    sc.after_hash.append(lambda sc: sc.sources[s]["facts"][3].__setitem__("value", "77%"))   # m2's score
    r = sc.run()
    eq(r.q(m1), "in:decision:D1", "an unrelated fact changed: the decision still applies")
    sc2 = base(); sc2.setup("s9")
    s = sc2.source("a")
    m1 = sc2.m(s, model="ma", effort=[("effort-setting", "max")])
    sc2.decide(m1, "quality", "in")
    sc2.after_hash.append(lambda sc: sc.msets[s][0].__setitem__("setup", "s9"))
    r = sc2.run()
    eq((r.q(m1), [d["id"] for d in r.rep["stale_decisions"]]), ("out:effort-not-established", ["D1"]),
       "setup changed: stale, reported, not applied")

# 12b. decision on a measure that no longer exists: reported, the build goes on
@test
def decision_on_removed_measure():
    sc = base()
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[LOW])
    sc.m(s, model="mb", effort=[LOW])
    sc.decide(m1, "quality", "out")
    sc.after_hash.append(lambda sc: sc.msets[s].__setitem__(0, dict(sc.msets[s][0], id="M9")))
    try:
        r = sc.run()
    except AssertionError as e:
        raise AssertionError("the build stopped on a decision whose measure was renumbered: " + str(e).splitlines()[1][:160])
    eq(any(d["id"] == "D1" for d in r.rep["stale_decisions"]), True, "reported as stale")

# 13. requested level not in the model's list through a router mapping to the nearest supported level
@test
def router_nearest_for_unlisted_level():
    sc = base()
    sc.model("mx", configs=("low", "medium", "high"))
    sc.model("my", configs=("low", "medium", "high"))
    sc.route("ory", "router", spellings=["ORY"],
             level_mapping=[dict(iv("2026-01-01", "2026-12-31", **WIN), rule="nearest-supported", ties="ambiguous")],
             models={k: {"accepts": [dict(iv("2026-01-01", "2026-12-31", **WIN), configuration=c)
                                     for c in ("low", "medium", "high")]} for k in ("mx", "my")})
    s = sc.source("a")
    m1 = sc.m(s, model="mx", effort=[("effort-setting", "xhigh")], route=[("ORY", None)])
    sc.m(s, model="my", effort=[LOW], route=[("ORY", None)])
    r = sc.run()
    eq(r.cfg(m1), "high", "OpenRouter-style nearest supported level: xhigh → high (step 6)")

# 14. early-access run: the cost price date must still be usable
@test
def early_access_cost():
    sc = base()
    sc.model("mn", released="2026-07-01"); sc.model("mo", released="2026-07-01")
    same_price(sc, "mn", "mo")
    for p in sc.prices["prices"]:
        p["from"] = "2026-07-01"
    s = sc.source("a", published="2026-07-01")
    m1 = sc.m(s, model="mn", effort=[LOW], cost="1.0", early_access=True)
    m2 = sc.m(s, model="mo", effort=[LOW], cost="2.0", early_access=True)
    r = sc.run()
    eq(r.q(m1), "in", "early access on quality")
    eq(r.c(m1), "in", "the list price never changed: publisher figure")

# 15. a label naming a level plus a thinking marker on a laddered model
@test
def label_level_with_thinking_marker():
    sc = base()
    s = sc.source("a")
    m1 = sc.m(s, model="ma", effort=[("effort-label", "high (thinking on)")])
    m2 = sc.m(s, model="mb", effort=[LOW])
    r = sc.run()
    eq(r.cfg(m1), "high", "a label naming a level of the ladder is that level")

# 16. mode via an unknown route that a router could have served
@test
def mode_route_unknown():
    sc = base()
    sc.model("gp", configs=("low", "high"), modes=[{"parameter": "pro", "value": "true", "key": "gp-pro",
             **iv("2026-01-01", "2026-12-31", **WIN)}])
    sc.model("gp-pro", configs=("low", "high"), line="gp")
    sc.route("openrouter", "router", spellings=["OpenRouter"], models={"gp": {"ids": [dict(iv("2026-01-01", "2026-12-31", **WIN), name="o/gp")]}})
    s = sc.source("a")
    m1 = sc.m(s, model="gp", effort=[HIGH], mode="pro")
    r = sc.run()
    eq(r.model(m1), None, "route unknown and a router that cannot separate Pro is a candidate → not established")

# 17. run-start after publication (contradictory run date) - the run-date field's level
@test
def run_date_contradictory():
    sc = base()
    s = sc.source("a", published="2026-06-01")
    m1 = sc.m(s, model="ma", effort=[LOW], run_date=[("run-start", "2026-07-01")])
    sc.m(s, model="mb", effort=[LOW])
    r = sc.run()
    lv = r[m1]["fields"]["run_date_detail"]["ma"]["level"]
    eq(lv, "not-established:contradictory", "run start after the publication")

# 18. lqm outcome attribution: a row left alone after its partner was dropped as a republication
@test
def lqm_attribution_single_after_republication():
    sc = base()
    for k in ("mc", "md", "me"):
        sc.model(k)
    sc.setup("r1", family="fr"); sc.setup("r2", family="fr")
    s1 = sc.source("a"); s2 = sc.source("b", publisher="puby")
    for mdl, v, c in (("ma", "50.0%", "1.00"), ("mb", "60.0%", "2.00"), ("md", "70.0%", "3.00"), ("me", "75.0%", "4.00")):
        sc.m(s1, setup="r1", model=mdl, effort=[LOW], score=v, cost=c)
    sc.m(s2, setup="r2", model="ma", effort=[LOW], score="50.0%", cost="1.00")
    sc.m(s2, setup="r2", model="mb", effort=[LOW], score="60.0%", cost="2.00")
    mc = sc.m(s2, setup="r2", model="mc", effort=[LOW], score="40.0%", cost="5.00")
    r = sc.run(lqm=True)
    eq(r.q(f"{s2}#M1"), "out:republished", "copy")
    eq(r.q(mc), "out:single-couple", "mc was not republished: it is left alone after the copies were dropped")

# 19. fit-cost keeps the cost as written when the base price is the publisher's figure (lqm reads its last digit)
@test
def fit_cost_digits_kept():
    sc = base()
    same_price(sc, "ma", "mb")
    s = sc.source("a")
    sc.m(s, model="ma", effort=[LOW], cost="0.30")
    sc.m(s, model="mb", effort=[LOW], cost="1.20")
    r = sc.run()
    eq(sorted(x["cost_usd"] for x in r.tables["fit-cost.csv"]), ["0.30", "1.20"], "digits as written (step 0.01 in lqm)")


# 20. thinking-on (not in a laddered model's list) together with a level setting: step 3 matches the level only
@test
def thinking_on_plus_level():
    sc = base()
    sc.model("ml", configs=("nothink", "low", "medium", "high"))
    s = sc.source("a")
    m1 = sc.m(s, model="ml", effort=[("thinking-on", "thinking: enabled"), HIGH])
    sc.m(s, model="ma", effort=[LOW])
    r = sc.run()
    eq(r.cfg(m1), "high", "think is not one of ml's configurations, so only the level setting matches")
