"""raw-data.csv rows ↔ a source's rows, for a conversion (DATA-PIPELINE §8.4): the mapping that gives each converted
measure its `legacy_ref`, with the unmatched rows of both sides listed, never guessed. Standard library only.

    from convert import mapping
    raw = mapping.raw_rows("raw-data.csv", "github-obviousbench")        # [(line, row_sha256, row)]
    res = mapping.match(raw, src_rows, [
        ("entry tag", lambda r: mapping.tag(r["confound"], r"entry(?:-id:|=)([^;]+)"), lambda s: s["model_entry_id"]),
        ("tokens+effort", lambda r: (r["tokens_in"], r["tokens_out"], r["effort"]),
                          lambda s: (s["input_tokens"], s["output_tokens"], s["reasoning_effort"])),
    ])
    res["pairs"]          # [(source row index, raw (line, sha, row), strategy)]
    res["unmatched_raw"], res["unmatched_source"], res["ambiguous"], res["how"]
    mapping.legacy_ref(raw_entry, csv_sha)  # the measure's legacy_ref
    mapping.save("mapping.json", res, src_rows, src_key)    # then: python3 data/convert/mapping.py mapping.json [--csv raw-data.csv]

Strategies are tried in order; a strategy pairs a source row with a raw row only when its key is unique on both
sides among the rows still unpaired (a key shared by several rows is reported as ambiguous and left to the next
strategy). A key function returning None or '' skips the row for that strategy.
"""
import argparse, collections, csv, hashlib, json, re, sys


def raw_rows(csv_path, source=None):
    """[(line, row_sha256, row dict)] of raw-data.csv, the line as written (the legacy converter's numbering)."""
    with open(csv_path, encoding="utf-8", newline="") as f:
        lines = f.read().split("\n")
    header = next(csv.reader([lines[0]]))
    out = []
    for n, line in enumerate(lines[1:], 2):
        if not line:
            continue
        rec = next(csv.reader([line]), [])
        if len(rec) != len(header):
            continue
        row = dict(zip(header, rec))
        if source is None or row.get("source") == source:
            out.append((n, hashlib.sha256(line.encode("utf-8")).hexdigest(), row))
    return out


def tag(text, pattern):
    """The first group of a regex in a text (an entry tag in a confound), stripped, or None."""
    m = re.search(pattern, text or "")
    return m.group(1).strip() if m else None


def match(raw, src_rows, strategies):
    left_raw = list(range(len(raw)))
    left_src = list(range(len(src_rows)))
    pairs, ambiguous, how = [], [], collections.Counter()
    for name, raw_key, src_key in strategies:
        rk = collections.defaultdict(list)
        for i in left_raw:
            k = raw_key(raw[i][2])
            if k not in (None, ""):
                rk[k].append(i)
        sk = collections.defaultdict(list)
        for j in left_src:
            k = src_key(src_rows[j])
            if k not in (None, ""):
                sk[k].append(j)
        done_r, done_s = set(), set()
        for k, js in sk.items():
            is_ = rk.get(k, [])
            if len(js) == 1 and len(is_) == 1:
                pairs.append((js[0], raw[is_[0]], name))
                done_r.add(is_[0])
                done_s.add(js[0])
                how[name] += 1
            elif is_:
                ambiguous.append(dict(strategy=name, key=repr(k), source_rows=js, raw_lines=[raw[i][0] for i in is_]))
        left_raw = [i for i in left_raw if i not in done_r]
        left_src = [j for j in left_src if j not in done_s]
    return dict(pairs=sorted(pairs, key=lambda p: p[0]), unmatched_raw=[raw[i] for i in left_raw],
                unmatched_source=left_src, ambiguous=ambiguous, how=dict(how))


def legacy_ref(raw_entry, csv_sha256=None):
    line, sha, _ = raw_entry
    out = {"line": line, "row_sha256": sha}
    if csv_sha256:
        out["csv_sha256"] = csv_sha256
    return out


def write_tsv(path, res, src_rows, src_key):
    """The mapping as a TSV: every source row (with its raw line or blank) and every unmatched raw row."""
    by = {j: (e, how) for j, e, how in res["pairs"]}
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["source_row", "source_key", "raw_line", "strategy"])
        for j, s in enumerate(src_rows):
            e, how = by.get(j, (None, ""))
            w.writerow([j, src_key(s), e[0] if e else "", how])
        for line, _, row in res["unmatched_raw"]:
            w.writerow(["", "", line, "unmatched raw row"])


def save(path, res, src_rows=None, src_key=None):
    """The result as JSON for the CLI: pairs (source row, raw line, strategy), the ambiguous keys, the unpaired raw
    rows (line, sha, row) and the unpaired source rows (index and, with src_key, their key)."""
    out = dict(how=res["how"], pairs=[dict(source_row=j, raw_line=e[0], strategy=how) for j, e, how in res["pairs"]],
               ambiguous=res["ambiguous"],
               unmatched_raw=[dict(line=l, row_sha256=h, row=r) for l, h, r in res["unmatched_raw"]],
               unmatched_source=[dict(source_row=j, key=(str(src_key(src_rows[j])) if src_rows and src_key else None))
                                 for j in res["unmatched_source"]])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)


def report(data, raw_by_line=None, limit=None):
    """Text lines: the ambiguous tags (the raw lines sharing each), then the unpaired raw rows and source rows."""
    L = [f"paired {len(data['pairs'])} ({', '.join(f'{k}: {v}' for k, v in data.get('how', {}).items())}); "
         f"{len(data['ambiguous'])} ambiguous key(s), {len(data['unmatched_raw'])} unpaired raw row(s), "
         f"{len(data['unmatched_source'])} unpaired source row(s)"]

    def brief(row):
        return ", ".join(f"{k}={row[k]}" for k in ("group", "model", "effort", "tokens_in", "tokens_out", "score", "confound")
                         if row.get(k) not in (None, ""))
    L.append("== ambiguous (not paired; left to the next strategy, still unpaired if none takes them)")
    for a in data["ambiguous"][:limit]:
        L.append(f"  [{a['strategy']}] key {a['key']}: source rows {a['source_rows']}, raw lines {a['raw_lines']}")
        for ln in a["raw_lines"]:
            if raw_by_line and ln in raw_by_line:
                L.append(f"      line {ln}: {brief(raw_by_line[ln])}")
    L.append("== unpaired raw rows")
    for u in data["unmatched_raw"][:limit]:
        row = u.get("row") or (raw_by_line or {}).get(u["line"]) or {}
        L.append(f"  line {u['line']}: {brief(row)}")
    L.append("== unpaired source rows")
    for u in data["unmatched_source"][:limit]:
        L.append(f"  row {u['source_row']}" + (f": {u['key']}" if u.get("key") else ""))
    return L


def main(argv=None):
    ap = argparse.ArgumentParser(description="Print the ambiguous tags and the unpaired rows/measures of a saved "
                                             "mapping (mapping.save).")
    ap.add_argument("result", help="JSON written by mapping.save")
    ap.add_argument("--csv", help="raw-data.csv, to show the raw rows of ambiguous lines")
    ap.add_argument("--source", help="raw-data `source` filter for --csv")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--json", action="store_true", help="print the ambiguous and unpaired parts as JSON")
    a = ap.parse_args(argv)
    try:
        data = json.load(open(a.result, encoding="utf-8"))
        by = {l: r for l, _, r in raw_rows(a.csv, a.source)} if a.csv else None
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps({k: data[k] for k in ("ambiguous", "unmatched_raw", "unmatched_source")}, indent=1,
                         ensure_ascii=False))
    else:
        print("\n".join(report(data, by, a.limit)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
