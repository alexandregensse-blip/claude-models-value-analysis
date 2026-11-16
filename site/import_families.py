#!/usr/bin/env python3
"""Fills the `families` block of site/makers.json — the one place of the multi-site build's family settings — from the
families salvo: <dir>/<maker>/families.tsv (columns key, line, family, predecessor, successor, successor_date, status,
status_date, evidence_url, quote). Run: python3 site/import_families.py [dir]  (default /work/.salvo14/fam).

Per key of a maker that has a file:
- current: its status is `current` (first word; "current-but-trailing", "unknown", "not a model" are not);
- hidden on its maker's page (older models): neither current nor followed by a current key (the latest model of each
  family and the one before it stay shown, as on the Claude page); a line (build, mode, preview) that is not current
  follows its model;
- family: the file's family; source: the file.
Then `family_overrides` of makers.json are applied (a user decision the file does not carry), and the changes of the
current set are printed. Keys of makers without a file keep their entries."""
import csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS = os.path.join(HERE, "makers.json")


def main(src):
    S = json.load(open(SETTINGS, encoding="utf-8"))
    FAM, before = S["families"], {k: v["current"] for k, v in S["families"].items()}
    for mk in S["makers"]:
        f = os.path.join(src, mk, "families.tsv")
        if not os.path.exists(f):
            print(f"{mk}: no {f}, entries kept"); continue
        rows = {r["key"]: r for r in csv.DictReader(open(f, encoding="utf-8"), delimiter="\t")}
        first = lambda s: (re.match(r"[a-z0-9][a-z0-9.\-]*", (s or "").strip().lower()) or [""])[0]
        cur = {k: first(r["status"]) == "current" for k, r in rows.items()}
        for k, r in rows.items():
            if k not in FAM:
                print(f"  {mk}: {k} is in the file but not in makers.json (left out)"); continue
            succ = first(r["successor"])
            FAM[k].update(family=r["family"], current=cur[k], hidden=not cur[k] and not cur.get(succ, False),
                          status=r["status"], successor=r["successor"], source=os.path.relpath(f, src))
        for k, r in rows.items():                                   # a line that is not current follows its model
            base = r["line"].strip()
            if k in FAM and base in FAM and r["line"] and not cur[k]:
                FAM[k]["hidden"] = FAM[base]["hidden"]
        for k, v in FAM.items():
            if any(k.startswith(p) for p in S["makers"][mk]["prefixes"]) and k not in rows:
                print(f"  {mk}: {k} is not in the file: entry kept ({v['source']})")
    for k, o in S.get("family_overrides", {}).items():
        FAM[k].update({x: y for x, y in o.items() if x != "why"}, source="override: " + o.get("why", ""))
    for k in FAM:
        if FAM[k]["current"] != before.get(k):
            print(f"  {k}: current {before.get(k)} -> {FAM[k]['current']}  ({FAM[k].get('status', '')[:60]})")
    open(SETTINGS, "w", encoding="utf-8").write(json.dumps(S, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/work/.salvo14/fam")
