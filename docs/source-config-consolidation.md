# Per-source config consolidation — VERIFIED (5 Sonnet agents, arxiv/site/repo reads)

For every source: the run configuration actually declared (thinking, effort, harness, temp). ✓ = re-verified this pass
by reading the paper/site/code (quotes in agent-config-{A..E}.md). Goal: "default" is never treated as one mystery effort.

## Anthropic API fact (verified, docs)
`effort` default = `high` ONLY when adaptive thinking is active. Adaptive: always-on Fable 5 / Mythos 5; on-by-default
Sonnet 5; opt-in only (thinking off otherwise) Opus 4.6/4.7/4.8 & Sonnet 4.6; absent (budget_tokens only) Haiku 4.5,
Sonnet 4.5, Opus 4.5/4.1, Sonnet 3.7. BUT benchmarks run via harnesses, so the harness/paper sets the real operating point.

## VERIFIED per-source table
| Source | Harness (verified) | Thinking | Effort | Identical across models? |
|---|---|---|---|---|
| OSWorld (anthropic-chart) | Anthropic/AA | on | low→max sweep | yes (per-effort curve) |
| AA Index / per-task | Artificial Analysis | on | max (AA methodology) | yes |
| AIReiter | Claude Code | on | high (explicit) | yes |
| george-liu | Claude Code | — | low & max (explicit) | yes |
| whitekumalabo | Claude Code | — | low & max (explicit) | yes |
| zenn QCD | raw API | — | low & xhigh (explicit) | yes |
| qiita nogataka | raw API | — | low & max (explicit) | yes |
| Braintrust | retrieval eval | budget | T25 / T50 thinking tokens | yes |
| PostTrainBench (2603.08640) | paper | on | medium & high (explicit) | yes |
| **swe-rebench** ✓ | **minimal ReAct** (not "SWE-agent") | **yes, per-model** | Opus4.8 xhigh · Opus4.7/4.6 high · **Sonnet4.6 default** | per-model efforts differ |
| **CEO-Bench** (2606.18543) ✓ | minimal terminal agent | mixed | **Opus4.8/4.7/Sonnet4.6 = MAX · Haiku = "thinking"** | Opus/Sonnet matched; Haiku differs |
| **SlopCode** (2603.24755) ✓ | Claude Code (ver varies) | **YES** | **Reasoning: HIGH** (Table 3) | yes |
| **OfficeQA** (2603.08655) ✓ | Claude Agent SDK | **YES** | **HIGH reasoning** (others matched) | yes |
| **EMB** (Vals.ai) ✓ | bash+execute | NS bool | **Opus4.8 = MAX**; Sonnet 5 = NOT STATED | POSSIBLE MISMATCH (flag) |
| HAL sci / swe-mini ✓ | HAL (Princeton) | — | high vs default (they compare) | compares two |
| **STAGE-Claw** (2606.10394) ✓ | OpenClaw | **OFF** ("reasoning disabled") | temp=0 | yes (temp caveat) |
| **ianlpaterson** ✓ | OpenRouter | **OFF** ("no special reasoning config") | max_tokens 8192 | yes (post-v2 rerun) |
| **WorkBench** (2606.13715) ✓ | native ReAct loop | **NS** | NS · temp=0 · "like-for-like" | yes (explicit) |
| **SkillsBench** (2602.12670) ✓ | **Claude Code 2.1.19** (NOT OpenHands) | NS | NS · temp=0 | yes |
| TOBench (2605.16909) ✓ | ReAct | NS | NS | NS |
| WildClaw (2605.10912) ✓ | OpenRouter (4 harnesses) | NS for Claude | NS | yes (explicit note) |
| **AutomationBench** (2604.18934) ✓ | NOT STATED | NS | NS (my earlier "max" was unfounded) | NS |
| code-review (2606.15689) ✓ | VibeOps prompt | NS | temp 0.1, identical prompt | yes |
| **ctala** ✓ | Claude Code CLI (`claude -p`) | reasoning NOT configured | temp 0.7, max_tokens 2048 | yes (only --model swapped) |
| **drona23** ✓ | **Claude Code CLI** (NOT raw API) | NS | identical code, only --model | yes |
| ponytail ✓ | headless Claude Code | NS | NS | agentic part yes; legacy part promptfoo |
| **CodeSOTA** ✓ | OpenRouter | N/A | **blended list-price, not a measured run** | pricing formula |
| **TrueFoundry** ✓ | AI Gateway, single-turn, NO tools | not labeled | NS | yes (identical integration) |

## Corrections applied vs my earlier labels
- SkillsBench harness: OpenHands → **Claude Code 2.1.19** (was wrong in raw-data.csv).
- drona23 harness: raw API → **Claude Code CLI**.
- CEO-Bench effort: default → **max** (Opus/Sonnet); Haiku left default.
- SlopCode effort: default → **high**. OfficeQA effort: default → **high**.
- EMB: Opus 4.8 → **max**; Sonnet 5 unspecified (possible effort mismatch, flagged).
- AutomationBench: "max" (Opus/Sonnet) → **default/NS** (paper states no config).
- STAGE-Claw & ianlpaterson: **thinking OFF** (explicit), were assumed on.
- CodeSOTA: reframed as **list-price blend**, not an effort-specific run.

## What this means for normalization
The "default"/harness bucket is HETEROGENEOUS (off / NS / high / max). It is NOT true that "harness always enables thinking".
The ratio-based method survives for ONE verified reason: within each source, the config is applied identically to all its
models (temp identical, "like-for-like" — explicitly stated by WorkBench, WildClaw, code-review, ctala, drona23, TrueFoundry).
Cross-effort mismatches to watch: EMB (Opus max vs Sonnet5 NS), CEO-Bench (Haiku differs from Opus/Sonnet).
Matrix VALUES unchanged; provenance & effort-row placement corrected.
