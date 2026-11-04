#!/usr/bin/env python3
"""Cells → facts (the maintainer, 4 Nov 2026: « Les fichiers findings recensent tout … Le build est censé n'être qu'un
filtre simple »). Standard library only.

    python3 data/convert/cells.py [--findings data/findings] [--report OUT.json] [--dry-run]

A table cell cited as `T<n>/<row key>/<column>` (by a measure, in any slot, or as a computed fact's input) used to be
read by the build in the source's saved data file. This script reads each such file one last time, checks its sha256
against the source's `sha256` map, and writes every cited cell into the source as a fact:

- `value`: the cell as validate.table_rows reads it (CSV text, or JSON scalar with its digits as written), stripped —
  exactly what the build read;
- `quote`: the cell and what identifies it, copied from the file: « <row key column>: <row key> | <column>: <cell> »
  (a JSON table keyed by its object keys, row_key `$key`: « <row key> | <column>: <cell> »);
- `says` (a list when the column states several types), `about` (the row key), `level` (the table's, default
  written), `form` data-file, `where` (« <table where> / row <row> / column <column> »), `file`, `table`, `column`,
  `cell` (the cited reference it replaces), and the column's `term`, `scale`, `namespace`, `precision` (else the
  table's precision) and `note`.

Each cited reference is then replaced by the new fact's id in the measures and in the computed facts' inputs. A cell
the file does not give (file not reachable, sha256 not matching, a format the build never read, no such row or column,
an empty cell) is left as it is and listed in the report: nothing is invented, and the build gives such a cell a fault
(out:no-proof on its axis), as it did. Running the script again on converted findings changes nothing.
"""
import argparse, collections, glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(DATA, "schema")]
import validate as V  # noqa: E402


def style(text, doc):
    """(indent, ensure_ascii, trailing newline) reproducing the file as written."""
    for ind in (1, 2, None):
        for ea in (True, False):
            s = json.dumps(doc, indent=ind, ensure_ascii=ea)
            if text == s or text == s + "\n":
                return ind, ea, text.endswith("\n")
    return 1, False, True


def write(path, doc, st):
    ind, ea, nl = st
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(doc, indent=ind, ensure_ascii=ea) + ("\n" if nl else ""))


def cited_cells(src, ms):
    """Cell references in first-citation order: measures' slots (value_seen_in holds captures), then computed inputs."""
    out = []
    for m in (ms or {}).get("measures", []):
        for slot, v in m["facts"].items():
            if slot == "value_seen_in":
                continue
            for r in (v if isinstance(v, list) else [v]):
                if isinstance(r, str) and r.startswith("T"):
                    out.append(r)
    for f in src.get("facts", []):
        out += [r for r in f.get("inputs") or [] if r.startswith("T")]
    return list(dict.fromkeys(out))


def convert(sp, mp, dry):
    """One source file and its measures file → (facts written, {ref: why not written})."""
    st_text = open(sp, encoding="utf-8").read()
    src = json.loads(st_text)
    ms, mst = None, None
    if os.path.isfile(mp):
        t = open(mp, encoding="utf-8").read()
        ms, mst = json.loads(t), style(t, json.loads(t))
    k, failed = to_facts(src, ms, sp)
    if k and not dry:
        write(sp, src, style(st_text, json.loads(st_text)))
        write(mp, ms, mst)
    return k, failed


def to_facts(src, ms, sp):
    """The cells cited in a source (its document) and its measures (document, or None) written as facts, in place;
    sp: the source file's path (saved files relative to it resolve). → (facts written, {ref: why not written})."""
    refs = cited_cells(src, ms)
    if not refs:
        return 0, {}
    tables = {t["id"]: t for t in src.get("tables", [])}
    sha_ok, failed, new = {}, {}, {}
    n = max([int(f["id"][1:]) for f in src.get("facts", [])] or [0])
    for ref in refs:
        t, row, col = V.split_cell(ref)
        tb = tables.get(t)
        if not tb or col not in tb["columns"]:
            failed[ref] = "table or column not declared"
            continue
        p = V.saved_path(tb["file"], sp)
        if not p:
            failed[ref] = f"saved file not reachable: {tb['file']}"
            continue
        if p not in sha_ok:
            want = src.get("sha256", {}).get(tb["file"])
            sha_ok[p] = want is not None and V.sha256_of(p) == want
        if not sha_ok[p]:
            failed[ref] = f"sha256 does not match: {tb['file']}"
            continue
        try:
            rows = V.table_rows(tb, sp)
        except (ValueError, UnicodeDecodeError) as e:
            failed[ref] = f"saved file not readable as {tb.get('format')}: {e}"
            continue
        if rows is None:
            failed[ref] = f"table format {tb.get('format')} never read by the build (csv, json)"
            continue
        cols, byrow = rows
        if row not in byrow or col not in cols:
            failed[ref] = "no such row or column in the saved file"
            continue
        raw = byrow[row].get(col) or ""
        cell = raw.strip()
        if not cell:
            failed[ref] = "empty cell"
            continue
        spec = tb["columns"][col]
        says = V.column_says(spec)
        n += 1
        fid = f"F{n}"
        lead = f"{row}" if tb["row_key"] == "$key" else f"{tb['row_key']}: {row}"
        f = {"id": fid, "says": says[0] if len(says) == 1 else says, "about": row, "value": cell,
             "level": tb.get("level", "written"), "form": "data-file",
             "where": f"{tb['where']} / row {row} / column {col}", "file": tb["file"], "table": t, "column": col,
             "cell": ref, "quote": f"{lead} | {col}: {raw}"}
        if isinstance(spec, dict):
            for k in ("term", "scale", "namespace"):
                if k in spec:
                    f[k] = spec[k]
        prec = (spec.get("precision") if isinstance(spec, dict) else None) or tb.get("precision")
        if prec:
            f["precision"] = prec
        if isinstance(spec, dict) and spec.get("note"):
            f["note"] = spec["note"]
        new[ref] = f
    if not new:
        return 0, failed
    src["facts"] = src.get("facts", []) + list(new.values())
    sub = lambda r: new[r]["id"] if isinstance(r, str) and r in new else r   # noqa: E731
    for f in src["facts"]:
        if f.get("inputs"):
            f["inputs"] = [sub(r) for r in f["inputs"]]
    for m in (ms or {}).get("measures", []):
        for slot, v in list(m["facts"].items()):
            if slot == "value_seen_in":
                continue
            m["facts"][slot] = [sub(r) for r in v] if isinstance(v, list) else sub(v)
    return len(new), failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--findings", default=os.path.join(DATA, "findings"))
    ap.add_argument("--report", help="write the per-source outcome (facts written, cells not written and why) as JSON")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    rep, total = {}, 0
    why = collections.Counter()
    for sp in sorted(glob.glob(os.path.join(a.findings, "sources", "*.json"))):
        mp = os.path.join(a.findings, "measures", os.path.basename(sp))
        k, failed = convert(sp, mp, a.dry_run)
        if k or failed:
            sid = os.path.splitext(os.path.basename(sp))[0]
            rep[sid] = {"facts_written": k, "not_written": failed}
            total += k
            why.update(v.split(":")[0] for v in failed.values())
    print(f"{total} fact(s) written in {sum(1 for r in rep.values() if r['facts_written'])} source(s); "
          f"{sum(len(r['not_written']) for r in rep.values())} cell(s) not written in "
          f"{sum(1 for r in rep.values() if r['not_written'])} source(s): {dict(why)}")
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
