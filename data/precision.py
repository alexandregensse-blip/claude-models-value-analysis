#!/usr/bin/env python3
"""Reading precision of every value: fills the columns score_prec and cost_prec of raw-data.csv.

δ is the standard deviation of the error made in READING a value off its source, in the value's own unit (the model
adds it to the row's variance, docs/METHODOLOGY.md §4). Three origins:

  printed    a number copied from a text, a table or a data file: its rounding, one unit of the last digit written in
             the data file / √12 (a uniform error). Where a page prints fewer digits than the data file holds, the
             file's digits came from a finer source (a JSON behind the page, a detailed table) or from a computation:
             the file's own last digit is the one that counts (checked source by source, precision/origins.json).
  digitised  a value read off a chart (precision/charts.json): the axis' units per pixel, recomputed by least squares
             from the chart's tick coordinates, times the reading error in pixels of that chart, estimated from an
             independent re-reading of its points (RMS difference / √2, never below the pixel's own 1/√12; the median of
             the charts when a chart has fewer than 3 re-read points); on a log axis the error is relative. A point
             re-read further than one marker diameter away is a misreading, not precision: it is reported, not used.
  computed   a cost the collector computed from published token counts: the counts' rounding propagated (the largest
             relative rounding of the counts, conservative), added to the rounding of the result.

A value both digitised and rounded takes both errors in quadrature. Run from the repository root:
    python3 data/precision.py            # rewrites raw-data.csv with the two columns
    python3 data/precision.py --check    # reports, writes nothing
"""
import csv, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "raw-data.csv")
KEY = ("group", "model", "effort", "source", "harness", "unit", "ref")
S12 = math.sqrt(12)


def last_digit(text):
    """One unit of the last digit of a number as written ('45.3' → 0.1, '12' → 1)."""
    t = (text or "").strip().lower().split("e")[0]
    return 10.0 ** -(len(t.split(".")[1]) if "." in t else 0)


def count_step(text):
    """Rounding step of a token count as written: trailing zeros of an integer of 3 or more ('1200000' → 100000)."""
    t = (text or "").strip()
    if not t.isdigit():
        return last_digit(t)
    z = len(t) - len(t.rstrip("0"))
    return 10.0 ** z if z >= 3 else 1.0


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def precision(rows):
    charts = json.load(open(os.path.join(HERE, "precision", "charts.json")))
    origins = json.load(open(os.path.join(HERE, "precision", "origins.json")))["groups"]
    read = {}                                                        # (row key, column) → δ from a chart
    for c in charts["charts"]:
        for k in c["rows"]:
            read.setdefault((tuple(k), c["column"]), []).append(c)
    stats = dict(digitised=0, printed_coarser=0, from_tokens=0)
    for r in rows:
        k = tuple(r.get(x, "") for x in KEY)
        o = origins.get(r["group"], {})
        for col, field in (("score", "score_prec"), ("cost_usd", "cost_prec")):
            v = num(r.get(col))
            if v is None:
                r[field] = ""
                continue
            step = last_digit(r[col])
            src = o.get("score" if col == "score" else "cost", {})
            if src.get("step") and src["step"] > step:
                stats["printed_coarser"] += 1                          # reported only: the data file's digits come
            var = (step / S12) ** 2                                     # from a finer source or a computation
            if col == "cost_usd" and src.get("from_tokens"):
                rel = max((count_step(r[t]) / S12 / num(r[t]) for t in ("tokens_in", "tokens_out") if num(r.get(t))),
                          default=0.0)
                var += (v * rel) ** 2
                stats["from_tokens"] += 1
            for c in read.get((k, col), [])[:1]:
                u = c["per_px"] * c["reading_px"]
                if c["via"] == "tokens_out" and num(r.get("tokens_out")):
                    var += (v * u / num(r["tokens_out"])) ** 2       # cost = tokens read on the chart × price
                elif c["scale"] == "log":
                    var += (v * math.log(10) * u) ** 2
                else:
                    var += u ** 2
                stats["digitised"] += 1
            r[field] = f"{math.sqrt(var):.3g}"
    return stats


def main(check=False):
    with open(DATA, newline="") as f:
        reader = csv.DictReader(f)
        head, rows = list(reader.fieldnames), list(reader)
    for col, after in (("cost_prec", "cost_usd"), ("score_prec", "score_metric")):
        if col not in head:
            head.insert(head.index(after) + 1, col)
    stats = precision(rows)
    print(json.dumps(stats))
    if check:
        return
    notes = {i: line for i, line in enumerate(open(DATA).read().split("\n")[1:]) if line.startswith("#") and "," not in line}
    with open(DATA, "w", newline="") as f:                           # free-text note lines are kept as they are
        w = csv.DictWriter(f, fieldnames=head, lineterminator="\n")
        w.writeheader()
        for i, r in enumerate(rows):
            if i in notes:
                f.write(notes[i] + "\n")
            else:
                w.writerow(r)


if __name__ == "__main__":
    main(check="--check" in sys.argv[1:])
