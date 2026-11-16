#!/usr/bin/env python3
"""Cost reproduction against a pinned price table (data/registry/price-tables.json): the build's rule and the
converters' per-row check share this code. Standard library only.

The coordinator's rules (23 Oct):
- a cost whose stated method is reproduced and disagrees by more than its rounding → contradictory (out);
- a stated method that cannot be reproduced (no card, no tokens) → accepted as written.

    python3 data/convert/reproduce.py --tables data/registry/price-tables.json --table runcost-0.1.12 \\
        --csv summary.csv --model-col inspect_model --model-map map.json --cost-col estimated_cost_usd \\
        --in-col input_tokens --out-col output_tokens [--cache-read-col cache_read_tokens] \\
        [--reasoning-col reasoning_tokens] [--reasoning-included-col F12_F13] [--row-key model_entry_id] > repro.tsv

    python3 data/convert/reproduce.py build-table --usage summary.csv --model-col inspect_model \\
        --registry data/registry --runner-dir runcost-check --pin 0.1.12 --out candidate-price-tables.json

--reasoning-included-col: a per-row column (true/false/yes/no/1/0; blank = the table's setting) holding the source's own
statement of whether the reasoning tokens are inside the output count (the F12/F13 facts are per row).

build-table prices the CSV's usage with the pinned library (runcost, its package.json must say exactly --pin), reads the
unit prices per class from the ledger, maps each model string to its registry key with the build's name rule (prefix
namespace) and writes the table keyed by registry names to --out (a candidate file: the registry's price-tables.json is
written by whoever owns the registry, never by this script). Strings resolving to no key or several are listed on stderr.

--model-map maps the CSV's model strings to model keys ({"anthropic/claude-opus-5-5": "opus-5.5"}). The output is
one row per CSV row: reproduced / off / no-card / no-tokens, with the computed cost and the relative gap.
"""
import argparse, collections, csv, json, os, subprocess, sys

CLASSES = ("input", "output", "cache-read", "cache-write-5m", "cache-write-1h")


def card_cost(tokens, classes, input_includes_cache_read=False, reasoning_in_output=True, reasoning_included=None):
    """(cost, why-not) of the run's tokens at one card. tokens: {class: count} plus optional 'tokens-reasoning'.
    reasoning_included (the source's own statement, when it makes one) overrides the table's reasoning_in_output."""
    t = {k: float(v) for k, v in tokens.items() if v is not None}
    if input_includes_cache_read and "cache-read" in t and "input" in t:
        t["input"] -= t["cache-read"]
    r = t.pop("tokens-reasoning", None)
    inside = reasoning_in_output if reasoning_included is None else reasoning_included
    if r and not inside:
        t["output"] = t.get("output", 0.0) + r
    use = {k: v for k, v in t.items() if k in CLASSES and v}
    if not use:
        return None, "no tokens"
    missing = sorted(k for k in use if classes.get(k) is None)
    if missing:
        return None, f"the card prices no {', '.join(missing)}"
    return sum(v * classes[k] for k, v in use.items()) / 1e6, ""


def parse_bool(text):
    """True / False for a per-row statement (true/false/yes/no/1/0, any case), None when blank or unreadable."""
    t = (text or "").strip().casefold()
    return True if t in ("true", "yes", "1", "included") else False if t in ("false", "no", "0", "excluded") else None


LEDGER_CLASS = {"input_uncached_tokens": "input", "output_text_tokens": "output", "input_cache_read_tokens": "cache-read"}


def ledger_prices(models, records):
    """{model string: {class: set((price per MTok, price card id))} or {'static': card}} from the library's ledgers
    (records in the order of `models`)."""
    out = collections.defaultdict(dict)
    for m, r in zip(models, records):
        led = r.get("ledger")
        if not isinstance(led, dict):
            continue
        for c in led.get("components", []) or []:
            cls = LEDGER_CLASS.get(c.get("name"))
            if cls and c.get("unit_price") not in (None, ""):
                out[m].setdefault(cls, set()).add((float(c["unit_price"]) * 1e6, c.get("price_card_id")))
        if led.get("price_card"):
            out[m]["static"] = led["price_card"]
    return out


def build_table(prices, ctx, table_id, label, version, evidence, input_includes_cache_read=True,
                reasoning_in_output=True):
    """({'tables': {id: table}}, report) from ledger_prices(): cards keyed by registry names. ctx has .models and
    .routes (the registry). The key of a string is the build's name rule (build.api_matches, prefix namespace); a
    string with no key, several keys, a static (source-priced) card or no priced class is listed in the report and
    gets no card; one card per (model, route), the lowest price when a string has several."""
    data = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path[:0] = [p for p in (data, os.path.join(data, "schema")) if p not in sys.path]
    import build
    cards, rep = {}, dict(unresolved=[], static=[], multi_price=[], mapped={})
    for st in sorted(prices):
        ms, route, _ = build.api_matches(ctx, st, "prefix")
        keys = sorted({k for k, _ in ms})
        if len(keys) != 1:
            rep["unresolved"].append((st, keys))
            continue
        pr = prices[st]
        if "static" in pr:
            rep["static"].append(st)
            continue
        classes = {}
        for cls, v in pr.items():
            if len(v) > 1:
                rep["multi_price"].append(st)
            classes[cls] = round(sorted(v)[0][0], 6)
        if not classes:
            continue
        card_id = sorted(pr["input"])[0][1] if pr.get("input") else ""
        rep["mapped"][st] = keys[0]
        r = route if route not in (None, "maker-api") else None
        cards[(keys[0], r)] = dict(model=keys[0], route=r, currency="USD", per="MTok", classes=classes,
                                   note=f"{label.split(' (')[0]} card {card_id}".strip())
    table = dict(label=label, version=version, evidence=evidence, input_includes_cache_read=input_includes_cache_read,
                 reasoning_in_output=reasoning_in_output, cards=list(cards.values()))
    return {"tables": {table_id: table}}, rep


def run_library(records, runner_dir, pin, script="scripts/runners/price_usage_with_runcost.mjs"):
    """The library's ledgers for usage records, after checking runner_dir's package.json names exactly `pin`."""
    pj = json.load(open(os.path.join(runner_dir, "package.json"), encoding="utf-8"))
    ver = pj.get("version") or ((pj.get("dependencies") or {}).get("runcost"))
    if ver != pin:
        raise ValueError(f"{runner_dir}: library version {ver!r}, pinned {pin!r}")
    p = subprocess.run(["node", os.path.join(runner_dir, script)], input=json.dumps({"records": records}),
                       capture_output=True, text=True, timeout=600)
    if p.returncode:
        raise RuntimeError(p.stderr[-500:])
    return json.loads(p.stdout)["records"]


def usage_records(rows, model_col, in_col="input_tokens", out_col="output_tokens", reasoning_col="reasoning_tokens",
                  cache_col="cache_read_tokens"):
    def n(r, c):
        try:
            return int(float(r.get(c) or 0))
        except ValueError:
            return 0
    return [{"sample_id": str(i), "model": r[model_col],
             "provider": ("xai" if r[model_col].split("/", 1)[0] == "grok" else r[model_col].split("/", 1)[0])
             if "/" in r[model_col] else "unknown", "surface": "normalized.usage",
             "usage": {"input_tokens": n(r, in_col), "output_tokens": n(r, out_col),
                       "reasoning_tokens": n(r, reasoning_col), "cache_read_tokens": n(r, cache_col),
                       "cache_write_tokens": 0, "total_tokens": 0}} for i, r in enumerate(rows)]


def build_main(argv):
    ap = argparse.ArgumentParser(prog="reproduce.py build-table")
    ap.add_argument("--usage", required=True)
    ap.add_argument("--model-col", required=True)
    ap.add_argument("--registry", required=True)
    ap.add_argument("--runner-dir", required=True)
    ap.add_argument("--pin", default="0.1.12")
    ap.add_argument("--table-id")
    ap.add_argument("--evidence", help="JSON file: the evidence list of the table")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    try:
        rows = list(csv.DictReader(open(a.usage, encoding="utf-8", newline="")))
        recs = run_library(usage_records(rows, a.model_col), a.runner_dir, a.pin)
        ev = json.load(open(a.evidence, encoding="utf-8")) if a.evidence else [
            {"url": f"https://registry.npmjs.org/runcost/-/runcost-{a.pin}.tgz", "captured": "", "quote": f'"version": "{a.pin}"'}]
        class Ctx:
            pass
        ctx = Ctx()
        ctx.models = json.load(open(os.path.join(a.registry, "models.json"), encoding="utf-8"))["models"]
        ctx.routes = json.load(open(os.path.join(a.registry, "routes.json"), encoding="utf-8"))["routes"]
    except (OSError, KeyError, ValueError, RuntimeError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    tid = a.table_id or f"runcost-{a.pin}"
    tab, rep = build_table(ledger_prices([r[a.model_col] for r in rows], recs), ctx, tid,
                           f"runcost {a.pin} (npm), default price cards, as the bridge calls them", a.pin, ev)
    json.dump(tab, open(a.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"{len(tab['tables'][tid]['cards'])} card(s) for {len(rep['mapped'])} string(s); "
          f"{len(rep['unresolved'])} string(s) with no single key, {len(rep['static'])} static", file=sys.stderr)
    for st, ks in rep["unresolved"]:
        print(f"  no key: {st} {ks}", file=sys.stderr)
    return 0


def verdict(cost, step, computed, rel_rounding=0.0):
    """'reproduced' when the computed cost is within the cost's rounding (one unit of its last digit) plus the token
    counts' relative rounding; else 'off'. → (verdict, relative gap)."""
    gap = abs(computed - cost)
    rel = gap / cost if cost else float("inf")
    return ("reproduced" if gap <= step + rel_rounding * computed else "off"), rel


def find_card(table, key, route=None):
    cards = [c for c in table.get("cards", []) if c["model"] == key and (c.get("route") in (None, route))]
    exact = [c for c in cards if c.get("route") == route]
    return (exact or cards or [None])[0]


def last_digit(text):
    t = (text or "").strip().lower().split("e")[0]
    return 10.0 ** -(len(t.split(".")[1]) if "." in t else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tables", required=True)
    ap.add_argument("--table", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--model-col", required=True)
    ap.add_argument("--model-map", required=True)
    ap.add_argument("--cost-col", required=True)
    ap.add_argument("--in-col", required=True)
    ap.add_argument("--out-col", required=True)
    ap.add_argument("--cache-read-col")
    ap.add_argument("--reasoning-col")
    ap.add_argument("--row-key")
    ap.add_argument("--reasoning-included-col")
    a = ap.parse_args()
    try:
        table = json.load(open(a.tables, encoding="utf-8"))["tables"][a.table]
        mmap = json.load(open(a.model_map, encoding="utf-8"))
        rows = list(csv.DictReader(open(a.csv, encoding="utf-8", newline="")))
    except (OSError, KeyError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    w = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
    w.writerow(["row", "model", "key", "cost", "computed", "status", "rel_gap", "why"])
    for i, r in enumerate(rows, 1):
        key = mmap.get(r[a.model_col])
        card = find_card(table, key) if key else None
        tok = {"input": r.get(a.in_col) or None, "output": r.get(a.out_col) or None}
        if a.cache_read_col:
            tok["cache-read"] = r.get(a.cache_read_col) or None
        if a.reasoning_col:
            tok["tokens-reasoning"] = r.get(a.reasoning_col) or None
        rk = r.get(a.row_key) if a.row_key else str(i)
        cost_t = (r.get(a.cost_col) or "").strip()
        if not key or not card:
            w.writerow([rk, r[a.model_col], key or "", cost_t, "", "no-card", "", "no model key" if not key else "no card"])
            continue
        computed, why = card_cost(tok, card["classes"], table.get("input_includes_cache_read", False),
                                  table.get("reasoning_in_output", True),
                                  parse_bool(r.get(a.reasoning_included_col)) if a.reasoning_included_col else None)
        if computed is None or not cost_t:
            w.writerow([rk, r[a.model_col], key, cost_t, "", "no-tokens", "", why or "no cost"])
            continue
        v, rel = verdict(float(cost_t), last_digit(cost_t), computed)
        w.writerow([rk, r[a.model_col], key, cost_t, f"{computed:.6g}", v, f"{rel:.4f}", ""])
    return 0


if __name__ == "__main__":
    sys.exit(build_main(sys.argv[2:]) if sys.argv[1:2] == ["build-table"] else main())
