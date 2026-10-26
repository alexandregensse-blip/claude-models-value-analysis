"""Cell value → fact type rules for converters: which values of a column need a per-row fact (and which type), which
are plain cells, and which are unknown — reported, never cited silently. Standard library only.

    from convert import rules
    table = rules.EFFORT_RULES                      # or your own list of Rule
    res = rules.classify_all(values, table)         # {value: (fact type, term) | None}, plus res["unknown"]

A rule: (regex, fact type, term template, note). The regex is matched in full, case-insensitively, against the cell;
the term template may use the regex groups ('{1}'). fact type None = a plain cell the build reads as it is (an
effort-setting column cell); the value gets no per-row fact.
"""
import collections, re
from collections import namedtuple

Rule = namedtuple("Rule", "pattern says term note")

EFFORT_RULES = [
    Rule(r"default|provider[ _-]default", "no-effort-sent", None, "no setting sent: the provider default applies"),
    Rule(r"(?:(?:minimal|low|medium|high|xhigh|max)_)?budget_([0-9]+)|(?:minimal|low|medium|high|xhigh|max)_budget_([0-9]+)",
         "thinking-budget", "{1}{2}", "a thinking budget (token count as term)"),
    Rule(r"minimal|low|medium|high|xhigh|x-high|max", None, None, "a level: the cell itself (effort-setting column)"),
    Rule(r"none|disabled|off|no[ _-]?thinking", None, None, "thinking off: the cell itself (the column name makes the "
                                                            "setting line, e.g. reasoning_effort: none)"),
    Rule(r"thinking|enabled|on", "thinking-on", None, "thinking on, no level"),
    Rule(r"[0-9]+(?:\.[0-9]+)?", None, None, "a numeric scale: the cell itself (scalar, not established)"),
]


def classify(value, table=EFFORT_RULES):
    """(fact type or None, term or None, rule) of a value, or None when no rule knows it."""
    for r in table:
        m = re.fullmatch(r.pattern, (value or "").strip(), re.I)
        if m:
            term = r.term.format(*([""] + [g or "" for g in m.groups()])) if r.term else None
            return r.says, term, r
    return None


def classify_all(values, table=EFFORT_RULES):
    out, unknown = {}, collections.Counter()
    for v in values:
        c = classify(v, table)
        out[v] = (c[0], c[1]) if c else None
        if c is None:
            unknown[v] += 1
    return dict(values=out, unknown=dict(unknown))
