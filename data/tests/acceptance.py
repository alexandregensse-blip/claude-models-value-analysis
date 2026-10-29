#!/usr/bin/env python3
"""Acceptance test of the legacy path (docs/DATA-PIPELINE.md §6, §8): today's raw-data.csv converted into legacy
findings (data/legacy.py), built (data/build.py --fit-models catalog), must give lqm.load exactly what the CSV gives it:
the same groups, the same rows in the same order (every field lqm.load computes), the same report and the same
republished list, on both axes. Each fit-table row is also checked to be a line of the CSV, byte for byte.

    python3 data/tests/acceptance.py [raw-data.csv]       # default: the repository's raw-data.csv (the frozen legacy input)
    python3 data/tests/acceptance.py CSV --keep DIR        # keep the converted findings and the build in DIR
Exit 0 when identical; otherwise the differences are listed.
"""
import argparse, collections, contextlib, io, json, os, shutil, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.dirname(HERE)
REPO = os.path.dirname(DATA)
sys.path[:0] = [DATA, os.path.join(DATA, "schema"), os.path.join(REPO, "model")]
import build, legacy  # noqa: E402
import lqm  # noqa: E402
from catalog import MODEL_ORDER  # noqa: E402


def comparable(groups):
    """lqm.load's groups as plain data (row dicts minus nothing: every computed field counts)."""
    return {g: dict({k: v for k, v in G.items() if k != "rows"}, rows=G["rows"]) for g, G in groups.items()}


def compare(axis, a, b, out):
    (ga, ra, pa), (gb, rb, pb) = a, b
    if sorted(ga) != sorted(gb):
        out.append(f"{axis}: groups differ: only in the CSV {sorted(set(ga) - set(gb))[:10]}, only in the build "
                   f"{sorted(set(gb) - set(ga))[:10]}")
    for g in sorted(set(ga) & set(gb)):
        A, B = comparable(ga)[g] if False else ga[g], gb[g]
        if [x for x in A["rows"]] != [x for x in B["rows"]]:
            n = sum(1 for x, y in zip(A["rows"], B["rows"]) if x != y) + abs(len(A["rows"]) - len(B["rows"]))
            out.append(f"{axis}: group {g}: {n} row(s) differ ({len(A['rows'])} vs {len(B['rows'])})")
        for k in A:
            if k != "rows" and A[k] != B[k]:
                out.append(f"{axis}: group {g}: {k} {A[k]!r} vs {B[k]!r}")
    if dict(ra) != dict(rb):
        out.append(f"{axis}: report {dict(ra)} vs {dict(rb)}")
    if pa != pb:
        out.append(f"{axis}: republished lists differ ({len(pa)} vs {len(pb)})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    default = os.path.join(REPO, "raw-data.csv")         # v2026.10.21 repriced (sha256 489b5d48…), = /work/.wt-px's
    ap.add_argument("csv", nargs="?", default=default)
    ap.add_argument("--keep", help="keep the converted findings and the build here")
    ap.add_argument("--registry", help="build against this registry (e.g. data/registry; the build supplies the "
                                       "legacy setup and publisher) instead of the minimal one data/legacy.py writes")
    a = ap.parse_args()
    t0 = time.time()
    diffs = []
    if lqm.EFFORTS != build.LEGACY_EFFORTS:
        diffs.append(f"build.LEGACY_EFFORTS {sorted(build.LEGACY_EFFORTS)} != lqm.EFFORTS {sorted(lqm.EFFORTS)}")
    root = a.keep or tempfile.mkdtemp(prefix="acceptance-")
    try:
        os.makedirs(root, exist_ok=True)
        fnd, reg, out = (os.path.join(root, x) for x in ("findings", "registry", "build"))
        for d in (fnd, reg):
            shutil.rmtree(d, ignore_errors=True)
        info = legacy.convert(a.csv, fnd, None if a.registry else reg)
        if a.registry:
            reg = a.registry
        else:
            fm = os.path.join(DATA, "registry", "flag-map.json")
            fm = fm if os.path.isfile(fm) else os.path.join(DATA, "findings", "examples", "registry", "flag-map.json")
            shutil.copy(fm, os.path.join(reg, "flag-map.json"))       # informative column only
        print(f"converted: {info['rows']} rows, {info['sources']} legacy sources, lines skipped (free text) "
              f"{info['skipped_lines']} ({time.time() - t0:.0f} s)", flush=True)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = build.main(["--registry", reg, "--findings", fnd, "--decisions", os.path.join(root, "none.json"),
                               "--out", out, "--fit-models", "catalog"] + (["--no-check-files"] if a.registry else []))
        print(buf.getvalue().strip()[:600])
        if code != 0:
            print("build failed")
            return 1
        print(f"built ({time.time() - t0:.0f} s)", flush=True)
        with open(a.csv, encoding="utf-8", newline="") as f:
            lines = set(f.read().split("\n"))
        for name in ("fit-quality.csv", "fit-cost.csv"):
            with open(os.path.join(out, name), encoding="utf-8", newline="") as f:
                body = f.read().split("\n")[1:-1]
            stray = [x for x in body if x not in lines]
            if stray:
                diffs.append(f"{name}: {len(stray)} row(s) not byte-identical to a CSV line, e.g. {stray[0][:120]}")
        for axis, field, name in (("quality", "score", "fit-quality.csv"), ("cost", "cost_usd", "fit-cost.csv")):
            ref = lqm.load(a.csv, MODEL_ORDER, field=field)
            got = lqm.load(os.path.join(out, name), MODEL_ORDER, field=field)
            compare(axis, ref, got, diffs)
            print(f"{axis}: CSV {len(ref[0])} groups / {sum(len(g['rows']) for g in ref[0].values())} rows; build "
                  f"{len(got[0])} groups / {sum(len(g['rows']) for g in got[0].values())} rows", flush=True)
        with open(os.path.join(out, "status-report.json"), encoding="utf-8") as f:
            rep = json.load(f)
        print("legacy counts:", json.dumps(rep["counts"].get("legacy")))
    finally:
        if not a.keep:
            shutil.rmtree(root, ignore_errors=True)
    print(f"\n{'IDENTICAL' if not diffs else 'DIFFERENCES:'} ({time.time() - t0:.0f} s)")
    for d in diffs:
        print("  " + d)
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
