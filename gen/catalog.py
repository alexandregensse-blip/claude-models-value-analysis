"""Catalogue: benchmark families and publishers.

A family groups the measurement groups (raw-data.csv `group`) that run the same task set, in the same version, with
the same grading — whoever runs it, whatever the harness, tools or budget. Members of a family share the gain of
their metric (partial pooling, see lqm.py); their offsets stay separate, because a harness moves the level of a
score, not its graduation. Different versions (CursorBench 3.1 / 3.2 / 4.0, FrontierCode v1 / 1.1, SWE-Bench Pro /
Pro V2, AA Index v3 / v4) and different gradings are different families. A family also scopes the detection of
republished numbers (lqm.load).
"""
FAMILIES = {
    "HLE":            ["aahle", "sc5hle", "schletools", "schleeff", "scfhletools", "scf51hlet", "sc55hlet", "schle-nt", "scf51hlen",
                       "scs55hlen"],
    "OSWorld-Verified": ["osworld", "scosweff", "scoosw47"],
    "OSWorld2-partial": ["scf51osw", "sc55osw", "osworld2b", "osworld2s", "osworld2o5", "osworld2o5a", "osworld2s150", "osworld2s300"],
    "TB4.0":          ["aatb40", "an55tb40", "tb40", "valstb4"],
    "TB3.0":          ["tb30chart", "tb30json"],
    "TB2.0":          ["valstb20", "predev-tb20", "kilobench", "tb2hf-0error", "tb2hf-polaris", "tb2hf-simplai", "tb2hf-vix", "tb2hf-wozcode"],
    "TB2.1":          ["valstb21", "valstb21cc", "tb21cc", "tb21t2"],
    "SWE-Pro":        ["scfsweppro", "scswebenchpro", "scsweproeff", "marginlabswe"],
    "SWE-Verified":   ["swebenchverified", "valsswebench", "valsswecc"],
    "AutomationBench": ["zapierab", "sc5autobench", "automationbench"],
    "GDPval-Elo":     ["aagdpval", "scgdpval"],
    "DRACO":          ["sc5draco", "scfdraco", "scf51draco", "sc55draco"],
    "DeepSearchQA":   ["sc5dsqa", "scfdeepqa", "scodeepqa"],
    "BrowseComp":     ["sc5browse", "docsbrowsecomp"],
    "ARC-AGI-2":      ["arcagi2", "scoarc"],
    "Chartography":   ["chartogt", "chartogn"],
    "GPQA":           ["valsgpqa", "orgpqa"],
    "SkillsBench":    ["skillsbench", "skillsbench-noskill", "valsskills"],
    "VibeCodeBench":  ["valsvibecode", "valsvibecc"],
    "swe-rebench":    ["swerebench", "swerebench2"],
    "AA-Index-v3":    ["aa-index", "aa-index-pertask", "aa-index-pertask2"],
    "AA-Index-v4":    ["aa-index4", "aa-index-pertask3"],
    "QCD-nnakapa":    ["nnakapa-f5o48", "nnakapa-o47o48", "nnakapa-o5f51", "nnakapa-o5o48f5", "nnakapa-o5s5", "nnakapa-s5cc",
                       "nnakapa-s5cop", "nnakapa-s5cop2", "zenn-qcd"],
    "kayben-review":  ["kayben-review", "kayben-review-f51"],
    "renchris-review": ["renchris-f51", "renchris-o55"],
    "retroboard":     ["retroboard", "retroboard-abridged", "retroboard-design", "retroboard-pw"],
    "TUA-bench":      ["tuabench-cc", "tuabench-msa", "tuabench-oh", "tuabench-t2"],
    "R2R-CE":         ["vlnr2r", "vlnr2r-msa"],
    "rampnet":        ["rampnet", "rampnet-fable"],
    "databricks":     ["databricks", "databricks-pi"],
    "ctala":          ["ctala", "ctala-cc"],
    "llmcost2026":    ["lcb-baseline", "lcb-batch", "lcb-compression", "lcb-outputcap"],
    "evg":            ["evg-baserm", "evg-opt", "evg-rag", "evg-rlm", "evg-unopt"],
    "pd":             ["pd-control", "pd-nisthigh", "pd-nonroot"],
    "semlayer":       ["semlayerdoc", "semlayerraw"],
    "snowflake":      ["snow-cc", "snow-coco"],
    "tilth":          ["tilth-baseline", "tilth-mcp"],
    "fable-mode":     ["fablemode", "fablemode-inj"],
    "ponytail":       ["ponytail", "ponytail-pony"],
    "lob2":           ["lobdeleg", "lobdelegw"],
    "valsws-finance": ["valswsfinance", "valswsfinance-exa"],
    "valsws-legal":   ["valswslegal", "valswslegal-exa"],
    "vulcan-v3":      ["vulcanbench3", "vulcanbench3-o5"],
    "TB-Science":     ["aatbsci", "scs55tbsci", "valstbsci"],
    "BenchCAD-V2C":   ["sc55bcad", "scs55bcadn"],
    "Chartography-regraded": ["sc55chartq", "scs55chartqn"],
    "ProgramBench":   ["valsprogram", "scs55progb"],
    "OfficeQA":       ["officeqa", "scs55offqa"],
    "HealthBench":    ["schealthbench", "scs55hb"],
    "Box-finserv":    ["boxfinserv", "boxs55-finserv"],
    "CodeRabbit-OSS": ["crabbit-o55oss", "crabbit-s55oss"],
    "occam":          ["occam-base", "occam-base-s1", "occam-ponytail", "occam-rules"],
}
FAMILY_OF = {g: f for f, gs in FAMILIES.items() for g in gs}

# Outlets of one organisation that publish its own measurements: one publisher.
PUBLISHER_OF = {"anthropic-syscard": "anthropic", "anthropic-chart": "anthropic", "anthropic-docs": "anthropic",
                "anthropic-cookbook": "anthropic", "claude-dev-blog": "anthropic"}

# Composite scores (an index, an average or a total over several benchmarks) and what they aggregate: a list of
# component groups, or "publisher" = every other group of the same publisher (its index is built from its own
# benchmarks). A composite and its components are the same measurements counted twice: for a couple measured on at
# least one component, the composite row is left out (lqm.load). A couple measured only on the composite keeps it.
COMPOSITES = {
    "aa-index": "publisher", "aa-index-pertask": "publisher", "aa-index-pertask2": "publisher",
    "aa-index-pertask3": "publisher", "aa-index4": "publisher", "aa-index43": "publisher",
    "valsindex": "publisher", "valsindex2": "publisher", "valsmmindex": "publisher",
    "boxs55-all": ["boxs55-finserv", "boxs55-legal", "boxs55-lifesci", "boxs55-public"],
    "nnrlog-total": "publisher",
}
