#!/usr/bin/env python3
"""Cost reproduction against a pinned price table (data/registry/price-tables.json): the build's rule and the
converters' per-row check share this code. Standard library only.

The coordinator's rules (23 Oct):
- a cost whose stated method is reproduced and disagrees by more than its rounding → contradictory (out);
- a stated method that cannot be reproduced (no card, no tokens) → accepted as written.

    python3 data/convert/reproduce.py --tables data/registry/price-tables.json --table runcost-0.1.12 \\
        --csv summary.csv --model-col inspect_model --model-map map.json --cost-col estimated_cost_usd \\
        --in-col input_tokens --out-col output_tokens [--cache-read-col cache_read_tokens] \\
        [--reasoning-col reasoning_tokens] [--row-key model_entry_id] > repro.tsv

--model-map maps the CSV's model strings to model keys ({"anthropic/claude-opus-5-5": "opus-5.5"}). The output is
one row per CSV row: reproduced / off / no-card / no-tokens, with the computed cost and the relative gap.
"""
import argparse, csv, json, sys

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
                                  table.get("reasoning_in_output", True))
        if computed is None or not cost_t:
            w.writerow([rk, r[a.model_col], key, cost_t, "", "no-tokens", "", why or "no cost"])
            continue
        v, rel = verdict(float(cost_t), last_digit(cost_t), computed)
        w.writerow([rk, r[a.model_col], key, cost_t, f"{computed:.6g}", v, f"{rel:.4f}", ""])
    return 0


if __name__ == "__main__":
    sys.exit(main())
