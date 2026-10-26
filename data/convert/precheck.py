#!/usr/bin/env python3
"""Name and route pre-check of a source against the registry, before any build: every model fact (and model cell)
resolved with the build's name rule, the Inspect / LiteLLM provider heads looked up among routes.json's prefixes and
spellings. Standard library only.

    python3 data/convert/precheck.py --registry data/registry --findings data/findings SOURCE_ID [--json]

Reports per source: the ids resolved (and to which key), the ids resolving to no key or to several, and the prefix
heads that name no route (the build then treats the route as unknown).
"""
import argparse, collections, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.dirname(HERE)
sys.path[:0] = [DATA, os.path.join(DATA, "schema")]
import build  # noqa: E402
import validate as V  # noqa: E402


class _Ctx:
    def __init__(self, registry):
        rd = lambda n: json.load(open(os.path.join(registry, n), encoding="utf-8"))  # noqa: E731
        self.models = rd("models.json")["models"]
        self.routes = rd("routes.json")["routes"]
        self.vocab = json.load(open(os.path.join(DATA, "schema", "vocab.json"), encoding="utf-8"))


class _Fact:
    """The few attributes build.route_of_fact reads, for a prefix head standing as a route fact."""
    def __init__(self, value, term=None, says=("route-name",), namespace=None):
        self.level, self.value, self.term, self.says, self.namespace = "written", value, term, list(says), namespace


def head_route(ctx, head):
    """The route a prefix head names, by the build's own rule (build.route_of_fact): the head as a route term, then
    as a name prefix ('head/'), then as a route spelling, case-insensitive. None when it names no route."""
    for rid in ctx.routes:                                   # term, case-insensitive
        if rid.casefold() == head.casefold():
            head = rid
            break
    for f in (_Fact(head, term=head),
              _Fact(head + "/x", says=("model-api-id",), namespace="prefix")):
        r = build.route_of_fact(ctx, f)
        if r:
            return r
    return None


def model_values(findings, sid):
    """(ref, says, value, namespace) of every model fact or model cell the source's measures cite."""
    src = json.load(open(os.path.join(findings, "sources", f"{sid}.json"), encoding="utf-8"))
    ms = json.load(open(os.path.join(findings, "measures", f"{sid}.json"), encoding="utf-8"))
    facts = {f["id"]: f for f in src.get("facts", [])}
    tables = {t["id"]: t for t in src.get("tables", [])}
    path = os.path.join(findings, "sources", f"{sid}.json")
    out = []
    for m in ms["measures"]:
        for ref in m["facts"].get("model", []):
            if ref.startswith("T"):
                t, row, col = V.split_cell(ref)
                spec = tables[t]["columns"][col]
                rows = V.table_rows(tables[t], path)
                cell = rows[1].get(row, {}).get(col) if rows else None
                says = V.column_says(spec)
                ns = spec.get("namespace") if isinstance(spec, dict) else None
                out.append((ref, says, cell, ns))
            elif ref in facts:
                f = facts[ref]
                out.append((ref, [f["says"]], f["value"], f.get("namespace")))
    return out


def precheck(registry, findings, sid):
    ctx = _Ctx(registry)
    resolved, unresolved, several, heads = {}, collections.Counter(), {}, collections.Counter()
    unreadable = 0
    for ref, says, value, ns in model_values(findings, sid):
        if value is None:
            unreadable += 1
            continue
        if "model-api-id" in says:
            matches, route, unknown = build.api_matches(ctx, value, ns or "maker-api")
            if ns == "prefix" and "/" in value and unknown and not head_route(ctx, value.split("/", 1)[0]):
                heads[value.split("/", 1)[0]] += 1
        elif "model-name" in says:
            matches = build.display_matches(ctx, value)
        else:
            continue
        keys = sorted({k for k, _ in matches})
        if len(keys) == 1:
            resolved[value] = keys[0]
        elif keys:
            several[value] = keys
        else:
            unresolved[value] += 1
    return dict(source=sid, resolved=len(resolved), unresolved=dict(unresolved.most_common()),
                several=several, unknown_heads=dict(heads.most_common()), unreadable_cells=unreadable)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("--registry", default=os.path.join(DATA, "registry"))
    ap.add_argument("--findings", default=os.path.join(DATA, "findings"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        r = precheck(a.registry, a.findings, a.source)
    except (OSError, KeyError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(r, indent=1, ensure_ascii=False))
        return 0
    print(f"{r['source']}: {r['resolved']} id(s) resolved, {sum(r['unresolved'].values())} unresolved "
          f"({len(r['unresolved'])} distinct), {len(r['several'])} resolving to several keys, "
          f"{len(r['unknown_heads'])} prefix head(s) naming no route")
    for h, n in r["unknown_heads"].items():
        print(f"  head   {h!r:30} ×{n}")
    for v, n in r["unresolved"].items():
        print(f"  no key {v!r:50} ×{n}")
    for v, ks in r["several"].items():
        print(f"  alias  {v!r:50} → {ks}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
