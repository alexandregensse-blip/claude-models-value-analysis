#!/usr/bin/env python3
"""Migration step 1 (docs/DATA-PIPELINE.md §8.1): today's raw-data.csv → legacy findings. Standard library only.

Every CSV record (header and the two free-text comment lines aside) becomes a `legacy-row` fact, form `legacy`,
whose value is the record's line verbatim. One legacy source per raw-data `source` value, so sources can be migrated
one by one. Each record becomes one measure on the placeholder setup `legacy`, citing its row and nothing else. The
build gives a legacy measure today's status and applies none of the tree's steps (data/BUILD.md, "Legacy path").

    python3 data/legacy.py raw-data.csv OUT/findings [--registry OUT/registry] [--as-of 2026-10-21]

--registry writes the minimal registry a legacy-only build needs:
- models.json (empty);
- routes.json (the maker's API);
- benchmarks.json (the setup `legacy`);
- publishers.json (`legacy`);
- prices.json (no entry: legacy costs are already at today's price);
- rules.json.
Into a real registry, add the setup `legacy` and the publisher `legacy` (LEGACY_SETUP and LEGACY_PUBLISHER below).
"""
import argparse, csv, collections, hashlib, json, os, re, sys

LEGACY_PUBLISHER = {"legacy": {"label": "raw-data.csv (legacy rows, before conversion)", "maker": None}}
EV = []
LEGACY_SETUP = {"legacy": {
    "family": "legacy", "label": "legacy rows", "benchmark": "raw-data.csv rows", "subset": None, "harness": None,
    "tools_regime": None, "judge_panel": None, "metric": "pass%",
    "headline": {"metric": "pass%", "basis": "decision", "decision": None}, "bounds": None, "direction": "higher",
    "task_type": "mixed", "complexity": "mid", "kind": "runs", "composite": None,
    "note": "placeholder: a legacy measure carries its own group, metric, harness, unit and task type in its row"}}


def records(path):
    """(line number, verbatim line, fields) of every CSV record, the line kept as written."""
    with open(path, encoding="utf-8", newline="") as f:
        lines = f.read().split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    for i, line in enumerate(lines, 1):
        rec = next(csv.reader([line]), [])
        yield i, line, rec


def slug(s):
    return re.sub(r"[^a-z0-9._-]+", "-", s.casefold()).strip("-._") or "x"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def convert(csv_path, findings, registry=None, as_of="2026-10-21"):
    csv_path = os.path.abspath(csv_path)
    it = records(csv_path)
    _, _, header = next(it)
    by_source, skipped = collections.OrderedDict(), []
    for n, line, rec in it:
        if len(rec) != len(header):
            skipped.append(n)
            continue
        by_source.setdefault(rec[header.index("source")], []).append((n, line, rec))
    os.makedirs(os.path.join(findings, "sources"), exist_ok=True)
    os.makedirs(os.path.join(findings, "measures"), exist_ok=True)
    digest, ids, nrows = sha(csv_path), set(), 0
    model_col = header.index("model")
    for src, rows in by_source.items():
        sid = f"src-legacy-{slug(src)}"
        base, k = sid, 2
        while sid in ids:
            sid, k = f"{base}-{k}", k + 1
        ids.add(sid)
        sid = f"{sid}-{as_of}"
        facts, measures = [], []
        for j, (n, line, rec) in enumerate(rows, 1):
            facts.append({"id": f"F{j}", "says": "legacy-row", "about": rec[model_col] or None, "value": line,
                          "level": "written", "form": "legacy", "where": f"line {n}", "file": csv_path})
            measures.append({"id": f"M{j}", "setup": "legacy", "facts": {"value": None, "model": [], "legacy": [f"F{j}"]},
                             "verified": None})
        nrows += len(rows)
        doc = {"id": sid, "publisher": "legacy", "urls": [f"raw-data.csv (source {src})"], "wayback": [], "commit": None,
               "sha256": {csv_path: digest}, "harvested_at": f"{as_of}T00:00:00Z", "published": None,
               "salvo": "legacy", "agent": "data/legacy.py", "snapshot_of": None,
               "legacy": {"file": csv_path, "columns": header, "source": src}, "facts": facts}
        with open(os.path.join(findings, "sources", f"{sid}.json"), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False)
        with open(os.path.join(findings, "measures", f"{sid}.json"), "w", encoding="utf-8") as f:
            json.dump({"source": sid, "measures": measures}, f, ensure_ascii=False)
    if registry:
        os.makedirs(registry, exist_ok=True)
        files = {"models.json": {"models": {}},
                 "routes.json": {"routes": {"maker-api": {"class": "maker-api", "label": "The maker's own API",
                                                          "operator": None, "models": {}}}},
                 "benchmarks.json": {"families": {"legacy": {"label": "legacy rows"}}, "setups": LEGACY_SETUP},
                 "publishers.json": {"publishers": LEGACY_PUBLISHER},
                 "prices.json": {"as_of": as_of, "prices": []},
                 "rules.json": {"rules": []}}
        for name, x in files.items():
            with open(os.path.join(registry, name), "w", encoding="utf-8") as f:
                json.dump(x, f, indent=1, ensure_ascii=False)
    return dict(sources=len(by_source), rows=nrows, skipped_lines=skipped)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("findings")
    ap.add_argument("--registry")
    ap.add_argument("--as-of", default="2026-10-21")
    a = ap.parse_args()
    if not os.path.isfile(a.csv):
        print(f"error: {a.csv}: no such file", file=sys.stderr)
        return 2
    print(json.dumps(convert(a.csv, a.findings, a.registry, a.as_of)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
