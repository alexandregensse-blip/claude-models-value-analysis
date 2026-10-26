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

Strategies are tried in order; a strategy pairs a source row with a raw row only when its key is unique on both
sides among the rows still unpaired (a key shared by several rows is reported as ambiguous and left to the next
strategy). A key function returning None or '' skips the row for that strategy.
"""
import collections, csv, hashlib, re


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
