#!/usr/bin/env python3
"""Evidence extractor for repricing_makers.py: the prices Artificial Analysis computed each of its costs with.

AA recomputes every cost at the price it displays on the day of the capture (checked: GPT-5.6 Sol's index output
cost 2102.57 at $30/MTok on 4 Aug, 1401.92 at $20/MTok on 1 Sep for the same 70.09 M output tokens). The payload of
each saved capture gives, per model object, the prices used (price1mInputTokens, price1mOutputTokens, cacheHitPrice,
cacheWritePrice) and the class breakdown of the index cost (intelligenceIndexCost: suite; intelligenceIndexCostPerTask:
weighted per task), and per evaluation the cost and output tokens per task. This script reads the saved captures of the
source passes (paths below, outside the repository) and writes the extract into repricing_makers.json ('aa').

    python3 data/precision/repricing_makers_aa.py      # needs /work/.salvo14/g/g2 (the AA pass of 19-20 Oct)
"""
import gzip, json, os, re, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
G2 = "/work/.salvo14/g/g2"
sys.path.insert(0, os.path.join(G2, "tools"))
import aa                                                            # the pass's own payload parser (objs)

CAPTURES = {                                                         # capture date → saved files (Wayback or live)
    "2026-07-30": [f"{G2}/src/aa/wb/claude-sonnet-5_20260730.html"],
    "2026-08-04": [f"{G2}/src/aa/wb/opus5_20260804070242.html"],
    "2026-09-01": [f"{G2}/src/aa/wb/fable51_20260901194602.html"],
    "2026-09-06": [f"{G2}/src/aa/wb/gemini-3-8-flash_20260906235658.html"],
    "2026-10-19": sorted(glob.glob(f"{G2}/src/aa/pages/*.html.gz")),
}
WANT = re.compile(r"^(gpt-5-6-(sol|terra|luna)|gemini-3-[678]-flash|gemini-4-argon|glm-5-3-flash|grok-4-5|grok-4-20|"
                  r"deepseek-v4-(flash|pro)|qwen3-7-(max|plus))")
TMP = "/tmp/repricing_makers_aa.html"


def objects(path):
    if path.endswith(".gz"):
        open(TMP, "w").write(gzip.open(path, "rt", errors="ignore").read())
        path = TMP
    return aa.objs(path)


def summary(o):
    def br(c):
        return {k: c.get(k) for k in ("total", "nonCacheInput", "cacheRead", "cacheWrite", "output")} if c else None
    ipt = o.get("intelligenceIndexCostPerTask") or {}
    return dict(slug=o["slug"], name=o.get("name"),
                price=[o.get("price1mInputTokens"), o.get("price1mOutputTokens"), o.get("cacheHitPrice"),
                       o.get("cacheWritePrice")],
                suite=br(o.get("intelligenceIndexCost")), task=br(ipt.get("cost")),
                evals={e["slug"]: [e.get("costPerTask"), e.get("outputTokensPerTask")]
                       for e in o.get("intelligenceIndexEvaluations") or [] if e.get("costPerTask")})


def main():
    out = {}
    for day, files in CAPTURES.items():
        best = {}
        for f in files:
            for s, o in objects(f).items():
                if WANT.match(s) and (s not in best or len(json.dumps(o)) > len(json.dumps(best[s]))):
                    best[s] = o
        out[day] = {(o.get("name") or s).lower(): summary(o) for s, o in sorted(best.items())}
        out[day]["_files"] = [f.replace("/work/.salvo14/", ".salvo14/") for f in files[:3]] + (
            [f"... {len(files)} files"] if len(files) > 3 else [])
    p = os.path.join(HERE, "repricing_makers.json")
    d = json.load(open(p))
    d["aa"] = out
    json.dump(d, open(p, "w"), indent=1, ensure_ascii=False)
    print({k: len(v) - 1 for k, v in out.items()})


if __name__ == "__main__":
    main()
