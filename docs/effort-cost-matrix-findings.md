# Model × Effort × Cost — raw findings (aggregated)

Date: 2026-07-06. Goal: complete matrix each model/effort vs cost + all benchmarks found.
Mixing sources; each row tagged with source + confidence.

## 1. PRICING (per 1M tokens) — CONFIRMED (Anthropic docs + aggregators)
| Model | Input $ | Output $ |
|---|---|---|
| Fable 5 | 10 | 50 |
| Opus 4.8 | 5 | 25 |
| Opus 4.7 | 5 | 25 |
| Sonnet 5 | 3 (intro 2 until 2026-08-31) | 15 (intro 10) |
| Sonnet 4.6 | 3 | 15 |
| Haiku 4.5 | 1 | 5 |
- Batch API: -50% all. Prompt cache read ~0.1x; write 1.25x(5m)/2x(1h).

## 2. OFFICIAL CHART — OSWorld-Verified (computer use), pass% · $/task
Digitized from anthropic.com/news/claude-sonnet-5 chart (log x-axis, ±10% cost).
| Effort | Sonnet 4.6 | Sonnet 5 | Opus 4.8 |
|---|---|---|---|
| low | 71.5% · $0.30 | 76.7% · $0.21 | 78.3% · $0.28 |
| med | 76.0% · $0.38 | 77.7% · $0.28 | 79.8% · $0.36 |
| high | 77.8% · $0.50 | 78.5% · $0.34 | 81.3% · $0.44 |
| xhigh | — | 79.2% · $0.45 | 82.9% · $0.75 |
| max | 78.4% · $0.53 | 81.3% · $0.68 | 83.4% · $1.30 |
- 2nd official chart exists: BrowseComp (agentic search), same models/efforts, NO raw numbers published. Sonnet5@max ≈ Opus4.8 accuracy at ~1/3 token cost (per MarkTechPost).

## 3. EFFORT→TOKEN MULTIPLIERS (community-measured, base=medium)
Source: Rigel/Medium, MindStudio.
- low: 0.3–0.5x (−50 to −70% vs medium)
- medium: 1.0x
- high: 1.3–1.5x (+30–50%)
- xhigh: ~2–2.5x ("substantially more")
- max: >=2x medium, up to 10x on hard prompts
- cheapest↔priciest: 2.7x avg, up to 10x complex (MindStudio)
- On trivial prompts: cost ~flat, latency 3.5x (effort explodes tokens only when task is genuinely hard)

## 4. ABSOLUTE MEASURED
- Artificial Analysis Opus 4.8 @max: Intelligence Index 56, 120M output tokens for full eval suite.
- Rigel: Opus benchmark @max = 58M output tokens → $2,486 (at $5/$25).
- Opus 4.8 @min ≈ Opus 4.7 @max quality (DataCamp/Anthropic).
- SWE-bench Pro: Sonnet4.6 58.1 | Sonnet5 63.2 | Opus4.8 69.2 (default effort). SWE-bench Verified Opus4.8 88.6.
- Terminal-Bench 2.1: Sonnet5 80.4 > Opus4.8 74.6.
- HLE(tools): Sonnet4.6 46.8 | Sonnet5 57.4 | Opus4.8 57.9.
- Community quota: 10x faster burn on high/max drove default→medium in CC.
- Recommended distribution: 60-70% low / 20-30% med / 5-10% high / <5% max.

## 4b. ARTIFICIAL ANALYSIS — Intelligence Index + normalized cost (KEY cross-model cost metric)
Intelligence Index (each at MAX effort):
| Model | AA Intelligence Index (max) |
|---|---|
| Fable 5 (w/ fallback) | 60 |
| Opus 4.8 | 56 |
| Opus 4.7 | 54 |
| Sonnet 5 | 53 |
| Sonnet 4.6 | 47 |
Cost per task on the Index (captures price × token verbosity):
| Model | $/task on Index |
|---|---|
| Fable 5 | highest (">Sonnet5", exact TBD) |
| Sonnet 5 | 2.29 |
| Opus 4.8 | ~1.99 |
| Sonnet 4.6 | ~1.15 |
Token/turn scaling with effort (AA):
- GDPval-AA: max effort ~6x more turns than low effort.
- Sonnet5 vs 4.6: ~40% more output tokens/task, ~3x agentic turns.
- Sonnet5 cost/task ~2x Sonnet4.6, ~15% > Opus4.8 — driven ENTIRELY by token usage, not per-token price.
More benchmark deltas (Sonnet5 vs 4.6): CritPt 17% (+14), Terminal-Bench v2.1 +9, HLE +10, SciCode +7.

## 4c. CONSOLIDATED effort multiplier (reconcile community + AA)
General prompts: low 0.4x / med 1x / high 1.4x / xhigh ~2.2x / max ~3x (vs medium); cheapest↔priciest 2.7x.
Agentic/long tasks: spread is LARGER — OSWorld Opus low→max = 4.6x $; AA GDPval max/low ~6x turns.
=> effort cost impact scales with task difficulty (trivial: near-flat; agentic: 4-6x).

Extra: Sonnet5 uses ~2x output tokens/task vs Opus4.8 (why $2.29 > $1.99 despite cheaper token).

## 6. MASTER MATRIX — model × effort × $/task
### 6a. MEASURED (OSWorld-Verified computer-use, official chart) — $/task
| Effort | Sonnet 4.6 | Sonnet 5 | Opus 4.8 |
|---|---|---|---|
| low | 0.30 | 0.21 | 0.28 |
| med | 0.38 | 0.28 | 0.36 |
| high | 0.50 | 0.34 | 0.44 |
| xhigh | — | 0.45 | 0.75 |
| max | 0.53 | 0.68 | 1.30 |

### 6b. DERIVED (per-token price × effort-multiplier, anchored to 6a) — FLAGGED estimate
Haiku4.5 (out $5 = 1/3 Opus; no xhigh/max): low ~0.10 · med ~0.13 · high ~0.16
Opus4.7 (=4.8 price, ~1.15x tokens): low ~0.32 · med ~0.41 · high ~0.51 · xhigh ~0.86 · max ~1.50
Fable5 (out $50 = 2x Opus): low ~0.56 · med ~0.72 · high ~0.88 · xhigh ~1.50 · max ~2.60

### 6c. NORMALIZED cross-model (AA Intelligence Index, at max) — measured
Fable5 idx60 $/task ~4+ (highest) | Opus4.8 idx56 $1.99 | Opus4.7 idx54 n/a | Sonnet5 idx53 $2.29 | Sonnet4.6 idx47 $1.15

## 7. Effort multiplier summary (vs medium=1)
low 0.4 · med 1.0 · high 1.4 · xhigh 2.2 · max 3.0 (general); agentic spread 4-6x low→max.

## 7b. MORE SOURCES (diversified)
- Anthropic OFFICIAL (Opus 4.5 launch), effort→token: medium effort = matches Sonnet4.5 best SWE-bench Verified at −76% output tokens; high effort = +4.3pp over Sonnet4.5 at −48% tokens. (no low-effort figure)
- Aider Polyglot (metatext): 40 models by score+cost. Claude 3.7 Sonnet whole benchmark = $36.83 (32k think). Opus4 72% / Sonnet4 61% (32k think). GPT-5 #1 at 88.0. [per-effort Claude 4.8/5 rows not confirmed yet]
- Sonnet5 uses ~30% more tokens than earlier Claude for equal task (multiple sources); ~40% more vs 4.6 on Index; ~2x vs Opus4.8.
- MindStudio agentic example (5-step): 6,100 in / 1,800 out total. 10-step×500/mo: Opus $31.50, Sonnet5 std $11.82, Sonnet5+ext-thinking $34.32. (NOTE: that article's "Opus 4.x $15/$75" is STALE/WRONG — ignore its pricing, keep the token-count shape only.)
- Cross-check: effort→token savings are model-generational too (Opus4.8@min ≈ Opus4.7@max; Opus4.5@med ≈ Sonnet4.5@high at −76% tokens).

## 7c. MORE BENCHMARKS (diversified, loop 2)
- Fable 5: SWE-bench Verified 95.0%, SWE-bench Pro ~80%. $10/$50, US-only inference 1.1x. Released 2026-06-09. Falls back to Opus4.8 on cyber/bio/chem (<5% sessions).
- Haiku 4.5: SWE-bench Verified 73.3% (avg 50 trials, 128k think, no test-time compute). $1/$5. Within 5pp of Sonnet4.5 (77.2%) at ~1/3 cost. 150 TPS. First Haiku with extended thinking. NO xhigh/max effort.
- Opus 4.7: SWE-bench Verified 87.6% (vs 4.6 80.8%). New tokenizer 1.0-1.35x tokens vs 4.6. CC defaults xhigh. "token eating machine" (Decrypt).
- Opus 4.8: OSWorld 83.4, SWE-bench Pro 69.2, USAMO 96.7, SWE-bench Verified 88.6.
- Sonnet 5 vs Opus 4.8: wins Terminal-Bench 2.1 (80.4 vs 74.6), GDPval-AA v2 Elo (1618 vs 1603); ties HLE(tools) 57.4 vs 57.9; loses SWE-bench Pro (63.2 vs 69.2), USAMO (79.5 vs 96.7), OSWorld (81.2 vs 83.4). At 40-60% lower cost.
- Pricing note: Sonnet5 40% cheaper/token than Opus4.8 (60% w/ intro).

## SOURCES REGISTRY (target 40+ distinct)
Official Anthropic:
1. platform.claude.com/docs/en/build-with-claude/effort
2. platform.claude.com/docs/en/about-claude/pricing
3. anthropic.com/news/claude-sonnet-5
4. anthropic.com/news/claude-opus-4-5
5. anthropic.com/news/claude-opus-4-7
6. anthropic.com/news/claude-haiku-4-5
7. platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-8
Artificial Analysis:
8. artificialanalysis.ai/models/claude-opus-4-8
9. artificialanalysis.ai/models/claude-sonnet-5-low
10. artificialanalysis.ai/articles/claude-sonnet-5-agentic-cost
11. artificialanalysis.ai/providers/anthropic
12. x.com/ArtificialAnlys (2 posts: idx53, $2.29/task)
LLM-Stats:
13. llm-stats.com/blog/research/claude-opus-4-8-launch
14. llm-stats.com/blog/research/claude-sonnet-5-vs-claude-opus-4-8
15. llm-stats.com/models/claude-sonnet-5
16. llm-stats.com/blog/research/claude-fable-5-review
17. llm-stats.com/blog/research/claude-opus-4-7-launch
18. llm-stats.com/ (leaderboard 300+)
Vellum:
19. vellum.ai/blog/claude-sonnet-5-benchmarks-explained
20. vellum.ai/blog/claude-opus-4-8-benchmarks-explained
21. vellum.ai/blog/claude-opus-4-7-benchmarks-explained
Benchmark aggregators:
22. morphllm.com/claude-benchmarks
23. morphllm.com/ai-coding-costs
24. metatext.io/benchmarks/aider-polyglot (Aider)
25. n8n.io/ai-benchmark/claude-haiku-4.5
Cost/pricing analyses:
26. cloudzero.com/blog/claude-api-pricing (+ /claude-opus-4-8-pricing)
27. finout.io/blog/anthropic-api-pricing
28. datacamp.com/blog/claude-opus-4-8
29. datacamp.com/blog/claude-sonnet-5
30. datacamp.com/blog/anthropic-claude-haiku-4-5
31. datasciencedojo.com/blog/claude-sonnet-5
Effort-focused:
32. mindstudio.ai/blog/claude-opus-4-8-effort-levels-explained
33. mindstudio.ai/blog/claude-code-effort-levels-explained
34. mindstudio.ai/blog/claude-sonnet-5-token-efficiency-cost
35. medium rigel-computer effort/quota
36. anthonymaio.substack.com opus-4.7 five effort levels
37. pub.towardsai.net 5 effort levels opus 4.7 (paywall)
38. explainx.ai/blog/claude-effort-parameter-model-selection-guide-2026
39. docs.litellm.ai/docs/providers/anthropic_effort
40. findskill.ai/blog/claude-opus-4-8-effort-settings
41. allthings.how/claude-opus-4-7-token-usage
42. decrypt.co claude-opus-4-7 "token eating machine"
Independent/other:
43. marktechpost.com sonnet5 vs 4.6 vs opus4.8
44. frankx.ai/blog/claude-fable-5-analysis-2026
45. humiris.substack.com haiku benchmark
46. caylent.com haiku 4.5 deep dive
47. dave-c.medium.com token efficiency enterprise
48. edenai.co sonnet5 vs opus4.8
49. openrouter.ai/anthropic/claude-opus-4.8

## 7d. GITHUB + LEADERBOARDS (loop 3)
GitHub repos with MEASURED output_tokens across haiku/sonnet/opus:
50. github.com/adam-s/testing-claude-agent — real output_tokens N=5 across haiku/sonnet/opus; benchmark/SUMMARY.md, SEMANTIC.md.
51. github.com/DietrichGebert/ponytail /benchmarks — agentic Claude Code session on real repo; 60-94% cuts on over-build tasks.
52. github.com/juliusbrussee/caveman — 65% output reduction avg (22-87%) across 10 prompts, reproducible evals/.
53. github.com/getagentseal/codeburn — local token/cost tracker across 31 tools by model/project/task.
54. github.com/egorfedorov/claude-context-optimizer — tracks token usage, 30-50% savings.
55. github.com/drona23/claude-token-efficient — 300-line CLAUDE.md ~$0.080/session Opus4.6 (30 turns, cached) vs 62-line ~$0.013.
56. github.com/topics/token-efficiency ; github.com/affaan-m/everything-claude-code token-optimization.md
Leaderboards:
57. codingfleet.com/blog/swe-bench-pro-leaderboard-2026
58. llm-stats.com/benchmarks/swe-bench-verified
59. vals.ai/benchmarks/swebench
60. swe-rebench.com
61. live-swe-agent.github.io
62. morphllm.com/best-ai-model-for-coding (ranks by SWE-bench Pro + cost/task)
Data: Fable5 SWE-bench Verified 0.950 (leads, "suspended"). Opus4.8 88.6% @ $5/$25. Sonnet4.6 79.6%. Sonnet5 63.2% SWE-bench Pro.
NOTE community CLAUDE.md finding: minimal instructions cut output ~4% haiku / ~12% sonnet / ~7% opus — small at model level, big on verbose agentic loops (60-94%).

TOTAL distinct sources logged: 62+. Target 40 met.

## 7e. GITHUB tooling + harnesses + academic (loop 4) — push to 100
Claude Code usage/cost trackers (measure YOUR real tokens/cost from ~/.claude/*.jsonl):
63. github.com/ryoppippi/ccusage — canonical ccusage CLI
64. github.com/aarora79/claude-code-usage-analyzer — by model+token type, LiteLLM pricing
65. github.com/badlogic/cccost — instrument CC for actual token/cost
66. github.com/Maciek-roboblog/Claude-Code-Usage-Monitor — realtime + predictions
67. github.com/phuryn/claude-usage — local dashboard + VSCode
68. github.com/cc-friend/ccost — Rust, JSONL, dedup streaming
69. github.com/long-910/vscode-claude-status
70. github.com/haasonsaas/claude-usage-tracker — rate-limit aware
71. github.com/evanlong-me/claude-code-usage
72. github.com/topics/token-usage-counter
SWE-bench harnesses / agentic (real resolve + cost):
73. github.com/augmentcode/augment-swebench-agent — #1 OSS SWE-bench Verified impl
74. github.com/Vexp-ai/vexp-swe-bench — resolution rate + cost + unique wins, all agents on Opus 4.5
75. github.com/OpenHands/OpenHands PR#6838 — official image + latest harness
76. github.com/murataslan1/ai-agent-benchmark — 80+ agents, SWE-bench + pricing
77. arxiv.org/pdf/2512.10398 — Confucius Code Agent: Opus4.5+CCA 54.3% SWE-Pro public (> Anthropic reported)
78. arxiv.org/pdf/2606.07462 — research-lifecycle: CC+Opus4.7 62.2% vs CC+Sonnet4.6 52.4%
79. arxiv.org/pdf/2606.20683 — agent harness design survey
80. gist.github.com/mbijon/bf97d677... — consolidated LLM benchmarks incl Opus 4.7 (2026-04-16)
81. gist.github.com/johnlindquist/30c9117... — Sonnet 4.5 release reviews
Token/cost calculators (pricing DBs — some STALE, flag):
82. github.com/AgentOps-AI/tokencost — 400+ LLMs price estimates
83. github.com/iyulab/TokenMeter — .NET, 12 providers, Claude 3.x/4.x
84. github.com/tekacs/llm-pricing
85. github.com/LLMWise-AI/llm-cost — 200+ models live pricing
86. github.com/tokenlint/tokenlint-vscode — NOTE shows STALE Opus4 $15/$75, Haiku3.5 $0.80/$4 (old gen, ignore)
87. github.com/nooscraft/tokuin — token/cost + load tests
88. github.com/GregorGk/token-counter
89. github.com/getagentseal/codeburn — per-project/model/task cost tracker
90. github.com/Green-PT/honey-for-devs — cross-tool skill, −53% token lossless in benchmarks
91. github.com/olivomarco/github-copilot-token-optimization
Agentic cost-per-task leaderboards + academic:
92. artificialanalysis.ai/agents/coding-agents — Coding Agent Index (mean $/task)
93. artificialanalysis.ai/evaluations/terminalbench-v2-1
94. artificialanalysis.ai/evaluations/terminalbench-hard
95. llm-stats.com/benchmarks/terminal-bench
96. whatllm.org/blog/agentic-ai-cost-per-task — "cost per task is the new benchmark"
97. arxiv.org/pdf/2601.11868 — Terminal-Bench paper (2.0: $1-100/task, up to 100M tokens/task)
98. arxiv.org/pdf/2603.23749 — Efficient Benchmarking of AI Agents
99. tbench.ai — Terminal-Bench official
100. artificialanalysis.ai/evaluations (Intelligence Index v4.1: cost/task, Agentic Index, cache pricing, tau-Bench, GDPval-AA)
101. codingfleet.com/blog/swe-bench-pro-leaderboard-2026
102. vals.ai/benchmarks/swebench

KEY new data: Terminal-Bench single task can hit 100M tokens / $1-100. AA "cost per task" now a first-class metric (Index v4.1). Confucius: Opus4.5 54.3% SWE-Pro public. CC+Opus4.7 62.2% research-lifecycle.
TOTAL distinct sources: 102 (>100 target met).

## 7f. loop 5 — more sources + CRITICAL methodology caveat
CRITICAL: Anthropic's published benchmark scores are run at **adaptive thinking, MAX effort, avg of 5 attempts**. At default `high` effort (real production), your scores are LOWER. => the headline numbers (Opus4.8 88.6 SWE-Verified, Fable5 95) are best-case/max-effort, not what a normal run gives. (source: llm-stats, truefoundry)
New sources:
103. venturebeat.com/technology/anthropics-claude-opus-4-8-is-here... (3x cheaper fast mode)
104. webscraft.org/blog/claude-opus-48-benchmarki... 
105. huggingface.co/blog/Laser585/claude-4-benchmarks
106. truefoundry.com/blog/claude-opus-4-8-and-swe-bench-pro... (ran headline through gateway)
107. believemy.com/en/r/claude-opus-4-8-features-benchmarks-complete-guide
108. buildfastwithai.com/blogs/claude-opus-4-8-review-benchmarks-dynamic-workflows-2026
morphllm.com/best-ai-model-for-coding + /claude-benchmarks: persistently HTTP 429 (rate-limited), not fetchable now — known to rank by SWE-bench Pro + cost/task; retry later.
TOTAL distinct sources: 108.

## 9. FINAL CONSOLIDATED MATRIX (merged, reconciled)
### Two cost regimes (DO NOT mix):
- $/task effort multiplier (high=1.0), derived FROM measured OSWorld (Opus4.8+Sonnet5 avg): low 0.6 · med 0.8 · high 1.0 · xhigh 1.5 · max 2.5. (input is fixed → dampened swing)
- output-TOKEN multiplier (medium=1.0), community/AA: low 0.4 · med 1.0 · high 1.4 · xhigh 2.2 · max 3.0; low→max up to 6-10x on hard/agentic.

### T1 MEASURED $/task per effort — OSWorld-Verified (official chart)
| eff | Sonnet4.6 | Sonnet5 | Opus4.8 |
| low | 0.30 | 0.21 | 0.28 |
| med | 0.38 | 0.28 | 0.36 |
| high | 0.50 | 0.34 | 0.44 |
| xhigh | — | 0.45 | 0.75 |
| max | 0.53 | 0.68 | 1.30 |

### T2 DERIVED $/task per effort (scale Opus4.8 OSWorld × k; FLAGGED)
k: Haiku4.5=0.22 (price 1/5, ~same tokens) | Opus4.7=1.2 (~1.2x tokens vs 4.8) | Fable5=2.6 (2x price × 1.3x tokens)
| eff | Haiku4.5 | Opus4.7 | Fable5 |
| low | 0.06 | 0.34 | 0.73 |
| med | 0.08 | 0.43 | 0.94 |
| high | 0.10 | 0.53 | 1.14 |
| xhigh | — | 0.90 | 1.95 |
| max | — | 1.56 | 3.38 |

### T3 MEASURED cross-model @max — AA Intelligence Index (harder suite; ratios only vs T1)
| model | AA idx | $/task | SWE-bench Verified | price in/out |
| Fable5 | 60 | ~4+ | 95.0 | 10/50 |
| Opus4.8 | 56 | 1.99 | 88.6 | 5/25 |
| Opus4.7 | 54 | ~2.2 (est) | 87.6 | 5/25 |
| Sonnet5 | 53 | 2.29 | n/a (SWE-Pro 63.2) | 3/15 (intro 2/10) |
| Sonnet4.6 | 47 | 1.15 | 79.6 | 3/15 |
| Haiku4.5 | n/a | ~0.5 (est) | 73.3 | 1/5 |
CAVEAT: all published SWE/OSWorld scores = adaptive thinking, MAX effort, avg 5 attempts. Default high => lower.
- Fable5 exact $/task on Index (unpublished; ~$4+).
- BrowseComp per-effort raw numbers (chart only, unpublished).
- No official per-effort SWE-bench table anywhere (only default-effort scores).

## 10. ERROR AUDIT (self-review of section 9)
E1 (MAJOR): cross-model $ ratio is NOT benchmark-stable.
  OSWorld @max ÷Sonnet4.6: Sonnet4.6 1.0 / Sonnet5 1.28 / Opus4.8 2.45.
  AA-Index @max ÷Sonnet4.6: Sonnet4.6 1.0 / Sonnet5 1.99 / Opus4.8 1.73.
  Sonnet4.6↔Sonnet5 nearly INVERT: OSWorld high Sonnet4.6 $0.50 > Sonnet5 $0.34; Index max Sonnet5 $2.29 > Sonnet4.6 $1.15.
  Cause: computer-use → weak Sonnet4.6 needs more turns (dear); agentic/reasoning → Sonnet5 ~2x verbose (dear). => no single stable cross-model ratio.
  My T2 was WRONG: scaled Opus4.8 OSWorld curve by pure price factor = imported computer-use cross-model structure (least like autodev).
E2: effort slope is model-dependent (max÷high: Opus4.8 2.95, Sonnet5 2.00, Sonnet4.6 1.06). One averaged multiplier misestimates Fable/Sonnet4.6.
E3: Fable under-set — AA says it's THE most costly; factor @max ≈ 2.0x Opus4.8 (not 1.3x verbosity).
E4: digitization noise on adjacent points (Sonnet4.6 high $0.50 vs max $0.53). Low confidence there.
E5: Haiku k=0.22 is a FLOOR (weak model likely more turns on agentic); no xhigh/max.
E6 (per user): the Anthropic OSWorld chart is ONE source, digitized, and shown at conditions favorable to Anthropic (max effort, avg 5 attempts) — must be cross-validated, not trusted as ground truth.

## 11. CORRECTED FUSED RATIO MATRIX
Base = Opus 4.8 @ max = 1.00. Fused cell = [cross-model factor @max from AA-Index (agentic ≈ autodev)] × [model effort-slope ÷ its own max, from OSWorld].
Cross-model @max ÷Opus4.8 (AA-Index): Opus4.8 1.00 | Sonnet5 1.15 | Sonnet4.6 0.58 | Fable5 ~2.0 | Opus4.7 ~1.10(est) | Haiku4.5 ~0.25(est).
Effort slope ÷own-max (OSWorld): Opus4.8 [.215/.277/.338/.577/1] ; Sonnet5 [.309/.412/.500/.662/1] ; Sonnet4.6 [.566/.717/.943/—/1] ; Opus4.7&Fable←Opus4.8 slope ; Haiku←Sonnet4.6 slope (no xhigh/max).
FUSED (Opus4.8@max=1.00):
| eff | Opus4.8 | Sonnet5 | Sonnet4.6 | Opus4.7* | Fable5* | Haiku4.5* |
| low | 0.21 | 0.36 | 0.33 | 0.24 | 0.43 | ~0.14 |
| med | 0.28 | 0.47 | 0.42 | 0.30 | 0.55 | ~0.18 |
| high | 0.34 | 0.58 | 0.55 | 0.37 | 0.68 | ~0.25 |
| xhigh | 0.58 | 0.76 | — | 0.63 | 1.15 | — |
| max | 1.00 | 1.15 | 0.58 | 1.10 | 2.00 | — |
To $: × task-type anchor. Agentic/autodev anchor = AA-Index Opus4.8@max $1.99; computer-use anchor = $1.30.
CI band: cross-model factors ±30-40% (task-dependence); effort slope ±15% (digitization); starred models wider (±40-60%).

## 12. TODO — final deliverable = graph with curves + confidence intervals
- Confront ALL sources per cell (don't trust single Anthropic chart): OSWorld chart, AA-Index, community multipliers, GitHub measured-token repos.
- Build per-model curve (x=effort or $/task, y=intelligence or ratio) with CI ribbons from source spread.
- Need to gather more independent per-effort $ points (currently only OSWorld gives full effort grid). Candidates: AA per-variant pages (sonnet-5-low etc.), GitHub token repos, BrowseComp digitization.

## 13. AA Intelligence Index v4.1 @max — MEASURED total-suite (1 source, internally consistent)
| model (max) | idx | output tokens (suite) | total $ to run | tok/s |
| Fable5 | 60 | 87M | ~$4,350+ (87M×$50 + input) | 70.4 |
| Opus4.8 | 56 | 120M | $3,752.55 | 58.3 |
| Opus4.7 | 54 | 100M | $3,737.82 | 56.6 |
| Sonnet5 | 53 | 300M | $6,015.18 | 73.7 |
| Sonnet4.6 (reasoning max) | 47 | n/a | n/a | n/a |
| Sonnet4.6 (non-reasoning high) | 36 | n/a | n/a | 45.8 |
| Haiku4.5 | 404 no page | | | |
CORRECTION to E3: Fable5 uses FEWEST tokens (87M < Opus 120M < Sonnet5 300M) — it is token-EFFICIENT; its high cost = $50/Mtok price, NOT verbosity. Sonnet5 is the verbose one (300M = 2.5x Opus).
RATIO INSTABILITY confirmed AGAIN: Sonnet5/Opus4.8 total-cost = 6015/3752 = 1.60 (Index v4.1) vs 1.15 (launch article, older Index). Same vendor, different suite version → 40% swing. Don't trust any single cross-model ratio.
NOTE: these are TOTAL-suite $ (many tasks), not per-task; only comparable within this snapshot.

## 14. BASE CHANGE: fused matrix base = Opus 4.8 @ MEDIUM = 1.00 (user pref). Recompute when data frozen.

## 15. PLAN: need MANY sources of measured data, esp GitHub community repos with partial measurements. AA = 1 source only. Collect raw result files (READMEs, benchmark/*.md) with real token/cost numbers per model (and per effort where available). Partial data acceptable.

## 16. DATA POINTS LEDGER — independent measured points (source-tagged, heterogeneous)
Effort scale internal: 0-100 numeric; CC "medium" default = effort=85 (src: gh#45862). => named levels map to a numeric knob (low/med/high/xhigh/max are buckets).

### A. $/task per effort (Anthropic OSWorld chart, digitized) — 13 pts [SRC: anthropic news chart]
(as T1: Sonnet4.6/Sonnet5/Opus4.8 × low..max)

### B. AA Intelligence Index v4.1 @max — total-suite tokens/$/speed [SRC: artificialanalysis.ai, 1 vendor]
Fable5 87M/~$4.35k+/70.4 · Opus4.8 120M/$3752.55/58.3 · Opus4.7 100M/$3737.82/56.6 · Sonnet5 300M/$6015.18/73.7 · Sonnet4.6-nonreasoning-high idx36/45.8 · Sonnet4.6-reasoning-max idx47.
AA per-variant speed (per effort): sonnet5-low 68.0 tok/s ; sonnet5-max 73.7 tok/s.

### C. GitHub community MEASURED (partial, real) 
- gh#64153 [anthropics/claude-code]: Opus4.8 @medium, 1 routine coding turn → OUTPUT 46,433 tok (mostly hidden thinking), in 131, cache-read 91,877, cache-create 4,054, ~22m43s. => "medium" NOT cheap on 4.8.
- gh#63455: simple tasks 40-50k tokens (model unclear).
- gh#45862: effort=85=medium; medium fewer tok/turn but 2-3x total (retries); $361 extra/48h, Opus ~94% of usage.
- gh#51809 [claude-code]: Sonnet4.6 @normal, per-turn overhead CONSTANT ~6-8k tok regardless of content. Log: ex1 +8.3k, ex2 +6.3k, ex3 +6.3k, ex4 +6.0k. Exhausts 5h quota in ~90min.
- gh#23706: Opus4.6 token consumption >> 4.5 (Max subscriber quota feedback).
- caveman [juliusbrussee]: Sonnet4.6 per-task OUTPUT tokens (normal): 387,446,678,702,704,1042,1180,1200,2347,3454 (10 tasks); caveman-compressed 121-456; avg -65%.
- testing-claude-agent [adam-s]: Sonnet4.6 per-config small task tokens/$: CSV 1016-1199 tok/$0.068-0.083; SQLite 1230-1586/$0.108-0.127; WebSocket 3370-7891 (high variance 2x). Totals 7221-12053 tok across 3 tasks.
- rigel/mindstudio: multipliers (low 0.4/med1/high1.4/xhigh2.2/max3 vs med; low→max up to 10x hard).
- anthropic Opus4.5 launch: medium −76% out tok vs Sonnet4.5-high; high −48%.

### CONFIDENCE NOTES
- Only source A gives a clean per-effort × per-model × $ grid, but it's Anthropic (max-effort-favorable, digitized, 1 benchmark).
- Sources C are REAL but heterogeneous (different tasks/turns) → good for SANITY BOUNDS + variance (e.g. WebSocket 2x run-to-run variance = intrinsic noise), not for clean matrix cells.
- Cross-source agreement so far: "medium is deceptively expensive on 4.7/4.8" (gh#64153, #45862, #54410, rigel) ; "Sonnet5 ~2.5x Opus tokens" (AA 300M vs 120M) ; run-to-run token variance ~2x (adam-s WebSocket) => CI bands must be WIDE.
- NOT enough independent per-effort $ grids yet to fix cells tightly. Need: more GitHub SWE-bench harness result files with per-model cost; digitize BrowseComp; ccusage self-measurement.

### D. SWE-bench $/task (real harness runs) [SRC: GitHub harnesses]
- Vexp-swe-bench: Opus4.5+ClaudeCode, SWE-Verified 100-task: 73.0% resolved, $0.67/task. Baselines (same Opus4.5): Live-SWE-Agent $0.86, OpenHands $1.77.
- SWE-Verified Mini 50-task: Sonnet3.7 54% = $388.88 total ($7.78/task); Opus4.1 54% = $1599.90-1789.67 ($32-36/task). [old models, but real cost spread by model]
- Sekinal/sonnet5-vs-glm52: confirms AA Sonnet5 300M tok/$6015 std/~$4010 intro; cost/index-point ~$113; "most verbose model in field", 2.5x Opus4.8.
- SWE-bench/experiments repo: canonical per-model metadata.yaml (resolved% + cost), needs deep nav per submission — TODO harvest.
- arxiv 2510.11977 Holistic Agent Leaderboard: agent eval infra w/ cost — TODO.

### E. SAME-TASK head-to-head (highest value: clean ratios)
- copilot-intellij-feedback#1770: SAME code change — Sonnet4.6 $10.30 (3,388,386 in tok, ALL uncached) vs Opus4.7 ~$3.83 (804,490 in tok, cached). Ratio 2.7x. CONFOUND: Copilot disables cache_control on Sonnet → not a clean model ratio, it's a caching-failure artifact. Useful as "caching dominates cross-model cost."
- tech-insider.org "2026 Tested" Opus4.6/Sonnet4.6/Haiku4.5: SWE-Verified Opus4.7 74.5 / Sonnet4.6 65.3 / Haiku4.5 48.1 (same benchmark, scores only, no same-task cost).
- CONTRADICTION to resolve: some claim "Opus uses 3-5x MORE tokens than Sonnet" (thoroughness) vs AA-measured "Sonnet5 2.5x Opus tokens" (verbosity). => direction is task/gen-dependent; log both, don't average.

## 19. BACKGROUND AGENTS — same-task ≥2 model/effort hunt
Files: agent-1-github.md (DONE,10) / agent-2-blogs.md (DONE,5) / agent-3-leaderboards.md (DONE,29+HAL) / agent-4-forums.md (DONE,10).
Wave2 in flight: agent-5-swerebench.md / agent-6-video.md / agent-7-nonenglish.md / agent-8-gateways.md / agent-9-academic.md.
QUEUED (user): after ALL wave2 done + merged → launch Wave3 focused on RECENT scientific/academic sources ONLY (<4 months, i.e. published after ~2026-03-06): arxiv listings 2603-2607, openreview 2026, recent agent-cost/token-efficiency papers with Claude $ tables.

### MERGED — Agent-1 GitHub (same-task, MEASURED):
CLEAN same-task cross-model cost (best):
- ponytail [2026-06-17/18, 5 tasks, 30 runs]: baseline USD Haiku $0.030 / Sonnet $0.137 / Opus $0.137 (Opus==Sonnet!); ponytail-style $0.011/$0.035/$0.079; 100% correct all 3; latency H37.7s/S124.1s/O58.7s; LOC baseline H518/S693/O256.
- drona23 SUMMARY [5 prompts, N=5]: OUT tokens Haiku 2266 / Sonnet 1856 / Opus 1888 (~equal S/O); USD Haiku $0.0585 / Sonnet $0.1609 / Opus $0.3850. Opus/Sonnet=2.4x, Opus/Haiku=6.6x.
Same-task cross-GEN (Opus 4.6→4.7→4.8):
- gh#58369: Opus4.7 vs 4.6 same task → out tok 2.9x, cache_read 4.8x, total cost 3.6x; AA 110M vs 36M (~3x). Confound: 4.6 1-pass vs 4.7 +5 edits.
- gh#49302: Opus4.7 vs 4.6 → ~7x effective cost, 91% fewer responses/5h. Confound: cache metering bug, closed not-planned.
- akitaonrails/llm-coding-benchmark: Opus4.6/4.7/4.8 same Rails task → 4.7 ~$1.10/run 97/100; 4.8 95/100 16m48s; 4.6 83/100. (harness sensitivity noted)
- gh#39850: Sonnet4.6 vs Opus4.6 ACP per-instance django-13513, out 5,572/inst; cost-mislabel bug (Sonnet price on Opus).
Tokenizer (same input, count_tokens):
- cometkim gist: v4.6→v4.7 "hi" 1.62x, "Hello Claude" 1.80x, pangram 1.63x, tool 1.36x, PNG3000x2000 3.05x; corpus avg 1.29-1.34x code/prose.
Weak/confounded: yurukusa gist (dup of #1770); Anil-matcha fable5 (Opus not on same task).

KEY: same-task cross-model $ ratio Opus/Sonnet spans 1.0 (ponytail) → 2.4 (drona23) → vs 1.73 (AA Index) → 0.88 (OSWorld high). Range ~2.7x. Confirms cross-model ratio is task-dominated. Output-token counts for Opus vs Sonnet often ~EQUAL on small tasks (drona23) → cost gap is price-driven there, NOT verbosity; verbosity gap (Sonnet5 2.5x) shows on long agentic (AA).

### MERGED — Agent-3 leaderboards (HAL = GOLD: same-instance $/model & $/effort)
HAL (hal.cs.princeton.edu), total $ over SAME instance set:
- SWE-Verified-Mini(50): Sonnet4.5-High 72%/$463.90 ; Sonnet4.5-default 68%/$505.92 ; Opus4.1-default 61%/$1351 ; Opus4.1-High 54%/$1599 ; 3.7Sonnet-High 54%/$388.88 ; 3.7Sonnet 50%/$402.69 ; Opus4 50%/$1330.90.
- ScienceAgentBench: Sonnet4.5-High 30.4%/$7.47 vs 3.7Sonnet-High 30.4%/$11.74 (IDENTICAL score, -36% = clean gen efficiency).
- GAIA: Sonnet4.5 74.5%/$178 ; Opus4.1-High 68.5%/$562.
- TAU-Airline: 3.7Sonnet 56%/$42.11 ; Opus4.1 54%/$180.49 (4.3x).
- CORE-Bench Hard: Haiku4.5 11.1%/$43.93 (only Haiku $ point); + many (scaffold confound Claude Code vs CORE-Agent).
morphllm SWE-Pro cost/task: Opus4.8 69.2% ~$12 ; Sonnet5 63.2% $15.44 (Sonnet5 DEARER/task despite lower score).
swe-rebench.com: has Cost/Problem+Tokens/Problem per model (Sonnet5 72.7%, Sonnet4.6 62.3%, Opus4.8 79.4%) but page >10MB unfetchable — HIGH-VALUE REVISIT.
!! EFFORT INVERSION (breaks monotonic effort↑=cost↑): HAL Sonnet4.5 SWE-Mini High(72%/$464) CHEAPER+BETTER than default(68%/$506); Opus4.5 CORE-Bench High cheaper than default. Cause: higher effort → fewer retry turns → lower TOTAL agentic cost. => on agentic tasks effort→cost is NON-monotonic.

### MERGED — Agent-2 blogs
- george liu [ai.georgeliu.com] GOLD effort-sweep: 4 models(Opus4.7/4.6/4.5,Sonnet4.6) × 5 efforts, 220 headless runs, MEASURED out-tok+cost. Opus4.7 low 2,691→max 17,559 (6.5x!); Opus4.5 max/low 2.1x. cost/10-run Opus4.7 med $2.07 xhigh $1.78cold/$1.12warm; Sonnet4.6 med $1.46/$0.78. tok/$ Sonnet4.6-high 15,516 vs Opus4.7-high 3,015 (5.1x). Cache warm/cold 1.59-1.88x. Caveat McNemar p0.25-0.5 low power.
- ianlpaterson [38 real tasks,15 models,OpenRouter]: Sonnet4.6 $0.20/run, Opus4.6 $0.69, Haiku4.5 $0.04 → Opus/Sonnet 3.45x, Opus/Haiku 17x, Sonnet/Haiku 5x; Opus=Sonnet accuracy at 3.5x cost.
- cosmicjs: Sonnet4.5 vs Opus4.5 same blog-app: Sonnet 188,840 tok, Opus 152,320 (Opus -19% tokens; pricier/token though).
- simonwillison: tokenizer 4.6→4.7 sys-prompt 1.46x, PDF 1.08x, hi-res img 3.01x (2nd independent confirmation w/ cometkim).
- joe.njenga: Fable5 "Hello" = $0.4745 (rest paywalled).

### CROSS-MODEL Opus/Sonnet $ RATIO — full distribution (same-task sources)
0.78 (Opus4.8 vs Sonnet5 SWE-Pro, morphllm) | 0.88 (OSWorld high) | 1.0 (ponytail) | 1.73 (AA Index) | 2.4 (drona23) | ~3.0 (HAL SWE-Mini,GAIA) | 3.45 (ianlpaterson 38-task) | 4.3 (HAL TAU).
PATTERN: same-gen Opus/Sonnet on AGENTIC tasks clusters 3-4x; compresses to ~1 on tiny/computer-use; INVERTS <1 when the Sonnet is verbose Sonnet5 vs Opus4.8. => cross-model must be a WIDE BAND (0.8-4.3), median ~3x for same-gen agentic.
EFFORT out-token low→max: Opus4.7 6.5x (george liu, measured) ; Opus4.5 2.1x ; community "up to 10x". $ low→max smaller (input fixed) AND non-monotonic on agentic (retries).

### MERGED — Agent-4 forums
- HN46039244 (Amp/Sourcegraph prod): Sonnet4.5 $1.83/thread vs Opus4.5 $1.30/thread → Opus CHEAPER (0.71x) all-in. [+ another Opus checkpoint $1.55]
- HN48736605: CursorBench Fable5-Max 72.9%/$18.02 vs Opus4.7-Max 64.8%/$11.02 (Fable/Opus4.7=1.6x). 1st Fable same-bench $.
- HN47816960: AA suite Opus4.6-max 160M tok vs Opus4.7-max 100M; net 4.7 cheaper output but +input.
- dev.to/tensorlake: SAME CLI proj Opus4.6 out 33.2K vs Sonnet4.6 52.9K (Opus -37% tok); $ ~$1.00 vs ~$0.87 output-only (Opus dearer by price); Sonnet stayed BROKEN. 20m vs 34m.
- cosmicjs (dup, fuller): Sonnet4.5 188,840 tot vs Opus4.5 152,320 (Opus -19% tot tokens).
- claudecodecamp: effort Low/Med/High SAME prompt, 30 calls → ~$0.016/req ALL THREE (flat $!), latency 17/20/60s (3.5x). => simple prompt: effort ≈ latency-only, NOT cost. Also 170-turn session $20.97, input=96.2% of cost.
- datacamp/opus-4-7-project: effort high/xhigh/max sweep, 18 tasks: high $0.05-0.07/task, +memory $0.10-0.12; REAL thinking ~290 tok/task (tiny vs 20K budget). xhigh+mem ~47s vs max+mem ~31s.
- reliabledataengineering: Opus4.5 vs 4.6 same query: $0.068 vs $0.090 (+32% "verbosity tax"); latency 5000tok 31.4s vs 43.7s; refactor 4.5 4-5 fix rounds/20min vs 4.6 1-2/8min.
- ai-engineering-trend: AA relay Sonnet5 $2.29 / Sonnet4.6 ~$1.20 / Opus4.8 ~$1.97 per index-task.
- WEAK/partial: sophiaashi (Opus4.6 vs Sonnet4.6 ~15x per-token, session $0.80 vs $12 — projection); sebuzdugan (Opus4.8→Sonnet5 $1000→$400/day, 2.5x, no tokens); HN47050837 (Sonnet4.6 $0.11 vs Opus4.6 ~$0.07 simple req, avg).

### UPDATED cross-model Opus/Sonnet $ ratio distribution (same-task, all sources)
0.71 (Amp Opus4.5<Sonnet4.5) · 0.78 (Opus4.8<Sonnet5 SWE-Pro) · 0.88 (OSWorld) · ~1.0 (ponytail) · 1.15 (tensorlake out-only) · 1.73 (AA Index) · 2.4 (drona23) · ~3.0 (HAL SWE-Mini/GAIA) · 3.45 (ianlpaterson) · 4.3 (HAL TAU).
=> RANGE 0.71–4.3. TWO regimes: (a) recent Opus is TOKEN-efficient (fewer tokens, better correctness) → often CHEAPER all-in than same-gen Sonnet despite higher rate (Amp, tensorlake tokens, cosmicjs); (b) but per-DOLLAR on big agentic suites Opus can be 3-4x (HAL) OR Sonnet5-verbosity flips it. NO stable point — model as WIDE BAND, and note the "Opus efficiency offsets price" effect.
NEW confirmed: effort→$ is FLAT on simple prompts (claudecodecamp $0.016 all levels; datacamp thinking 290 tok tiny), only latency scales; big + non-monotonic only on hard/agentic (retries).

### MERGED — Agent-7 non-English (STRONG effort sweeps + same-task)
- zenn/nnakapa QCD [JA, 240 trials, STRONGEST]: Sonnet5 vs Opus4.8 × low/med/high/xhigh, 3 coding tasks. $ aggregated: Opus4.8 low$0.561→xhigh$1.423 (2.54x); Sonnet5-std low$0.392→xhigh$0.762 (1.94x); Sonnet5-intro low$0.261→xhigh$0.508. Pass: Opus-med 100% vs Sonnet-med 70%, both high 100%. Opus4.8/Sonnet5 $ = 1.43 (low)→1.87 (xhigh). Cost=0.00353·D+0.242 (R².999). Opus wins concurrency task T3 20-8.
- whitekumalabo [JA, 192 runs, effort×DIFFICULTY]: Opus4.6 low/med/high/max × 4 difficulty. $/exec: L1(easy) $0.023-0.028 (effort~flat); L3 low$0.032→max$0.060 (1.9x); L4 low$0.095→high$0.152. Quality: medium≈high≈max (no gain for +33% cost at L3). => effort cost-slope SCALES WITH TASK DIFFICULTY (flat easy, ~2x hard).
- qiita/nogataka [JA, N=1 full grid]: Opus4.7 low→max on 3 tasks w/ token breakdown. TaskA $0.07→$0.19 (2.7x), TaskC $0.22→$0.54 (2.45x). Thinking tok TaskA low0.4K→max16.5K (41x); TaskC max thinking 41.3K. low FAILS all 3; xhigh/max succeed.
- serverworks [JA, same task]: weekly-report gen, Opus4.6 $1.85/$1.77 vs Sonnet4.6 $0.38-0.80 vs Haiku4.5 $0.12-0.13. Opus/Sonnet ~3.6x, Opus/Haiku ~15x. Time Opus 3-5min vs Haiku <30s.
- tencent [ZH, partial]: Opus4.7 effort relative tokens: low=20-30%/med=40-50%/high=60-70% of xhigh; max=2-3x xhigh. "xhigh≈max quality, max ~2x tokens". "4.7 uses 15-40% more tok than 4.6".
- WEAK: engineer117 (single-run noise, order reverses); mixednuts (fleet, NOT same task, author pricing $15/$75 WRONG).
- RE-QUOTED (not new measurements): qiita/59f19, kai_kou, aisparkup[KO], python-engineer, webscraft[DE] — all cite AA/Anthropic.

### CONVERGENCE — effort $-slope on REAL coding tasks (multi-source, independent)
low→max (or low→xhigh) $ multiplier: qiita 2.45-2.7x · zenn 2.54x (Opus) / 1.94x (Sonnet5) · whitekumalabo 1.9x (L3) · OSWorld-derived ~2.5x (Opus) / 2.0x (Sonnet5). => CONVERGES ~1.9-2.7x. Confidence on effort $-slope now MEDIUM-HIGH for coding. (Token-only slope larger: george liu 6.5x, tencent ~3-5x — because $ is dampened by fixed input.)
DIFFICULTY interaction (whitekumalabo + claudecodecamp + datacamp): easy task → effort ≈ flat $ (latency only); hard task → ~2x; agentic w/ retries → can invert (HAL).
Opus4.8/Sonnet5 same-task $ ratio added: 1.43-1.87 (zenn). Distribution now 0.71–4.3 unchanged range.

### MERGED — Agent-5 swe-rebench (SAME-INSTANCE, canonical, hard agentic; ~95% cached; tokens/problem 1.5-2.6M)
SAME-INSTANCE window (5 recent, directly comparable): 
| model | resolved% | $/problem | tok/problem |
| Opus4.8-xhigh | 56.5 | $2.02 | 2,479,387 |
| Opus4.7-high | 53.1 | $1.32 | 1,526,135 |
| Opus4.6-high | 47.8 | $1.53 | 1,828,649 |
| Sonnet4.6 | 51.3 | $1.29 | 2,644,577 |
| ClaudeCode(Opus4.6) | 59.6 | $1.74 | 1,878,248 |
Older (own windows, NOT same-instance): Opus4.5 $1.15/1.36M ; Sonnet4.5 $0.98/2.0M ; Opus4.1 $4.25/1.78M ; Sonnet4/3.5 cost untracked.
Absent: Sonnet5, Haiku4.5, Fable5.
FINDINGS: Opus4.8-xhigh/Sonnet4.6 same-instance $ = 1.57x (Sonnet4.6 uses MORE tokens 2.64M>2.48M but cheaper/token wins). Opus4.7-high CHEAPER than Opus4.6-high ($1.32<$1.53, more token-efficient) — cross-gen efficiency gain. Token-verbosity ordering Opus vs Sonnet is ALSO task-dependent (here Sonnet4.6>Opus4.8). Cross-model distribution += 1.57 (fits cluster).

### MERGED — Agent-8 gateways/observability
- Braintrust GLM-vs-Opus report [SAME task CPython stdlib retrieval, budget tiers T25/T50]: Opus4.8 T25 125.7k tok/$0.060 → T50 237.9k/$0.130 (T25→T50 ~2x cost, +1pp acc); Sonnet4.6 T25 $0.040→T50 $0.080. Acc Opus4.8 87-88% vs Sonnet4.6 56-67%. Opus4.8/Sonnet4.6 $ = 1.5x(T25)/1.63x(T50). [report mixes Sonnet5 token rows w/ Sonnet4.6 acc rows — flag]
- TrueFoundry [50 SWE-Pro, single-turn light harness]: Opus4.8 ~$1.45/suite (50/50) = $0.029/prob ; Opus4.7 ~$1.66 (47/50) = $0.033. Opus4.8 cheaper AND better. (NOT comparable to Anthropic 69.2% agent-harness.)
- codesota [OpenRouter 30-day agentic, real spend]: Sonnet4.6 $20.90M/3.29T tok → ~$6.35/M blended realized ; Opus4.8 $16.32M/1.54T → ~$10.60/M blended. Anthropic=67% of agent-inference $. apps: Sonnet4.6=29, Opus4.8=24.
- OpenRouter provider page [cumulative tokens routed]: Opus4.7 2.42T, Opus4.8 2.24T, Sonnet4.6 1.51T, Sonnet5 581B, Haiku4.5 255B, Fable5 209B.
- OpenRouter State-of-AI: blended effective $/1M 3.7Sonnet $1.963, Sonnet4 $1.937 (older, realized).
- Vercel AI Gateway Production Index [Oct25-Apr26]: Anthropic 26% tokens / 61% spend (premium); model page throughput Opus4.8 ~85-91 tok/s, Sonnet4.6 49 tok/s; TTFT Opus4.8 ~3.6s.
- BenchLM speed: tok/s Haiku 138, Opus4.5 46, Sonnet4.6 44, Opus4.6 40, Opus4.1 29; Opus4.1-Thinking latency 15s.
- simonwillison tokenizer (dup w/ agent-2): 4.6→4.7 prose 1.46x, PDF 1.08x, hi-res img 3.01x.

### REFINEMENT — same-PAIR same-GEN ratio is STABLE (vs the wide cross-everything range)
Opus4.8/Sonnet4.6 $ (hard coding/agentic): swe-rebench 1.57 · Braintrust 1.5-1.63 · tensorlake(4.6) 1.15(out-only) → cluster ~1.5-1.6x. The wide 0.71-4.3 range came from MIXING generations + verbose Sonnet5 + tiny/computer-use tasks. => for the graph: give a same-gen ratio (~1.5-1.6 Opus/Sonnet) AND flag the modifiers (Sonnet5 verbosity flips it; task size compresses it).
Budget/effort doubling (Braintrust T25→T50) = ~2x cost for +1pp — reinforces plateau + the ~2x-per-tier $-slope (consistent w/ ~1.9-2.7x low→max).

### MERGED — Agent-6 video/newsletter (thin: mostly re-quotes; YouTube transcripts unfetchable)
- padiso: Opus4.7 vs Sonnet4.6 SAME entity-extraction pipeline: Opus 99.2% acc/1.3 tool-calls/380ms vs Sonnet 94%/2.0/450ms. Quality+latency only (no tok/$; pricing claim dubious).
- futureinsidernews: real 2-wk spend $874→$41/mo; agentic coding session ~180k tokens = $4-7/session. Off-criteria (Claude vs open-source) but real $/session anchor.
- towardsai (paywalled): Opus4.7 5 efforts, 2.7x cost variance cheap→dear (matches convergence).
- YouTube hands-on leads (transcripts NOT fetchable via WebFetch — need transcript-capable pass): ED6hH4u4Apc (Sonnet5 vs Opus4.8 same prompts), GyPniFZtTmc (Fable5 vs Opus4.8 vs Sonnet4.6), 6abViIy_FUA (Opus4.7 effort levels), 7vdYl0ylOWI (Sonnet5 vs Opus4.8).
- Rest re-quote Anthropic/AA (cloudzero, claudefa.st, wavect, valueaddvc, aithinkerlab, dave-c) — not new measurements.
NOTE: agent confirms genuine independent hands-on numbers are RARE; most of the "long tail" just re-cites Anthropic/AA. This itself is a finding: the effective independent-measurement pool is ~25-30 sources, not hundreds.

### MERGED — Agent-9 academic (7 papers, 26 pts) — BIG confidence uplift
- WorkBench Revisited [2606.13715, CLEAN 4-model same-task ladder]: Fable5 $0.355 (97.7% done) / Opus4.8 $0.182 (96.2%) / Sonnet4.6 $0.105 (88.3%) / Haiku4.5 $0.034 (74.8%). Norm Opus4.8=1: Fable 1.95 · Sonnet4.6 0.58 · Haiku 0.19.
  => CORROBORATES AA-derived cross-model @max factors (Sonnet4.6 0.58 EXACT, Fable ~2.0, Haiku ~0.2). Two independent methods agree → cross-model anchors now HIGH confidence.
- STAGE-Claw [2606.10394]: Opus4.7 $6.55/task (1.242M tok) vs Sonnet4.6 $3.98 (1.265M tok). Tokens ~EQUAL → cost=price. Opus/Sonnet 1.65x.
- EnergyAgentBench [2605.15230]: Sonnet4.6 $0.059/run, Opus4.7 $0.267 (4.5x!), Haiku4.5 $0.018. ⚠️ PAPER USED WRONG OPUS PRICE $15/$75 → Opus inflated 3x; corrected @$5/$25 ≈ $0.089 → ratio ~1.5x. Haiku/Sonnet = 0.31.
- OSWorld 2.0 [2606.29537, computer-use, EXPENSIVE]: Opus4.8 ~$72.4/task (224K out, batched) / Opus4.7 ~$33.6 (150K out) / Sonnet4.6 ~$22.3 (single-action). Config confound. Opus4.8/Opus4.7 ~2.15x.
- AstaBench [2510.21652, sci-research]: Opus4.7 $3.54/prob / Opus4.6 ~$2.18 (4.7 +62% for +2.7pt) / Sonnet4.6 n/a.
- Terminal-Bench 2.0 [2601.11868]: tokens/model/harness (no USD); Claude Code harness = huge input (256.9M, caching artifact).
- DABstep [2506.23719]: old 3.x models total-run $ (overlaps HAL).
- Excluded (had <2 Claude OR no cost): OccuBench, MacAgentBench, WebMall, MMTB, BigFinanceBench, etc.

### CONFIDENCE UPGRADE (post-wave2)
- Cross-model @-comparable-effort factors (÷Opus4.8) now HIGH conf (2 independent methods): Fable5 ~1.95-2.0 · Opus4.8 1.0 · Opus4.7 ~1.1 · Sonnet4.6 ~0.58 · Haiku4.5 ~0.19-0.25. Sonnet5 is the OUTLIER (verbosity) → ~1.15-1.6 depending on suite, treat separately.
- Opus4.8/Sonnet4.6 same-gen $ ratio: HIGH conf ~1.5-1.73x (5+ sources: swe-rebench 1.57, Braintrust 1.5-1.63, WorkBench 1.73, STAGE 1.65, EnergyAgent-corr ~1.5).
- Effort $-slope low→max on real coding: MEDIUM-HIGH ~1.9-2.7x (qiita 2.7, zenn 2.54, whitekumalabo 1.9, Braintrust-tier 2x, OSWorld-derived 2.5).
- Difficulty interaction: HIGH conf (whitekumalabo 192-run, claudecodecamp, datacamp) — flat on easy, ~2x on hard, non-monotonic on agentic-with-retries (HAL).
- STILL LOW: exact per-effort×per-model $ cells for models w/o measured sweeps (Haiku/Fable per effort); Sonnet5 cross-model (verbosity-unstable).
=> Confidence now MEDIUM-HIGH overall — enough for a graph with HONEST CI bands (tight on same-gen cross-model & effort-slope, wide on Sonnet5 & top-effort tails).

## PLAN (user, remaining steps) — RECENT-MODELS focus
Focus models = latest: Opus 4.7, Opus 4.8, Sonnet 5, Haiku 4.5, Fable 5 (down-weight 3.x/4.0/4.1/4.5 except as ratio-links).
1. Finish wave3 (agents 10,12 pending) → merge.
2. WAVE 4 salvo: academic + scientific + tech blogs + AI forums + GitHub, FOCUS on latest models. (5 agents)
3. Consolidate ALL. Note differences by CRITERIA: task complexity (easy/hard), task type (coding / agentic-tool / computer-use / reasoning-math / writing), effort level, caching, harness, generation.
4. Build INTERNAL csv #1 = raw data (all points, source-tagged, with criteria columns).
5. Build csv #2 = NORMALIZED (relative scores). NORMALIZATION METHOD (the hard part):
   - Treat each (model,effort) as a NODE. Each same-task source that contains ≥2 nodes gives measured RATIO edges (cost_i/cost_j) — controlling for task.
   - Build a graph of these ratio-edges; solve for a globally consistent relative cost scale via least-squares on LOG-ratios (over-determined → confidence from residuals/agreement across independent edges). This is a linking/equating problem (like test-equating / Bradley-Terry on cost).
   - Anchor/base = Opus 4.8 @ MEDIUM = 1.00 (user pref).
   - Keep effort-slope and cross-model as SEPARATE edge types; segment by task-type where ratios differ materially (coding vs computer-use diverge → maybe per-task-type normalized layers).
   - CI band per node = spread of independent edges feeding it.
6. Artifact: consolidated matrix + Anthropic-style graph (pass rate / relative-intelligence vs relative cost, per effort, per model), with CI ribbons. Match Anthropic chart aesthetic (cream bg, effort-labeled points, log-x cost).

## 20. WAVE 3 — recent academic (<4 months)
### MERGED — Agent-11 effort/reasoning-budget curves (all >2026-03)
- 2606.17930 [Opus4/4.5/4.6, budget headroom BY BENCHMARK]: raise token budget → FrontierMath +11.7pp, HLE +9.3pp (BIG) BUT SWE-Bench-Pro +0.27pp, Terminal-Bench +1.26pp, HealthBench +0.32pp (near-FLAT). Newer models plateau LATER. => on CODING/agentic, effort/budget headroom is tiny; on frontier-math/reasoning it's large.
- 2606.08878 [claude-sonnet-4-6, effort low/med/high]: 0.0%/16.7%/6.7% → INVERTED-U, peaks at MEDIUM; high DEGRADES + more distractor leakage (23→40%). (multi-agent orchestration task)
- 2604.19758 [Opus4.6 ThermoQA, difficulty tiers]: tokens 12K(T1)→53K(T3) 4.4x but accuracy 96.4→93.6% (DROPS); token-accuracy corr weak r=0.07-0.29; Opus ~20x tokens of Gemini for similar acc (token-inefficient here).
- 2606.00376 [Claude-4.5-Opus reasoning depth]: super-exp decay past d*~19-31 steps; tool-delegation +60pp over neural reasoning.
- 2604.16529 [Claude-4.5-Opus test-time scaling]: SWE-Verified 70.9→77.6 (+6.7pp), Terminal-Bench 46.9→59.1 (+12.2pp) via parallel+sequential rollouts (monotonic, but that's rollout-count not effort).
- non-Claude corroboration: 2604.10739 budget 500→16K INVERTED-U peak ~12K, NEGATIVE at 16K (overthinking); 2604.14853/2603.08877 diminishing returns; 2604.21764 better allocation BEATS the tradeoff (fewer tokens + higher acc).
=> KEY for autodev (coding/agentic): effort→QUALITY curve is ~FLAT or INVERTED-U (overthinking) — +0.3-1.3pp for max vs low; effort→COST ~2x. EFFICIENT FRONTIER for coding = LOW-MEDIUM effort. High/max justified only on frontier-math/deep-reasoning, not code.
This directly supports the autodev tuning thesis: reviewers/mechanical phases → low; only genuine deep-reasoning phases → high.

### MERGED — Agent-12 recovered/non-arxiv (recent)
- WildClawBench [2605.10912, OpenClaw]: Opus4.7 62.2%/$1.29/task vs Opus4.6 51.6%/$1.35/task (4.7 CHEAPER+BETTER; ~26 tool-calls; 5.46 vs 8.47min). Cross-gen efficiency confirmed AGAIN.
- RealClawBench [2606.03889, live dev-agent]: Opus4.7 65.8% ($46.54 full run) / Sonnet4.6 55.3% / Opus4.6 52.1%. Others' cost in Fig5 only.
- Revelio [2606.22263, vuln pipeline]: Haiku4.5 $12.07/proj (5.28M in/1.36M out) + Sonnet4.6 $30.79/proj (9.66M in/0.12M out). CONFOUND: 2-stage, each model diff subtask.
- Score-only (no cost): MyPCBench [2606.16748] Opus4.6/Sonnet4.6; FinTrace [2604.10015]; OccuBench [2604.10866] 6 Claude (Opus4.6 71.5 best); BigFinanceBench [2606.03829] Opus4.7 58.8/Sonnet4.6 58.5 (cost in Fig4 only).
- RECOVERY FAILED: HAL 2510.11977 per-model table (PDF>10MB, ar5iv fatal) — website leaderboard values already captured suffice.
- 2604.22750: Sonnet4.5 only (<2 Claude); note: token usage STOCHASTIC, same-task runs vary up to 30x; accuracy peaks at INTERMEDIATE cost (corroborates inverted-U).

### MERGED — Agent-10 fresh arxiv (recent, per-model cost)
- CEO-Bench [2606.18543, 4 RECENT Claude]: BestRun API$ Opus4.8 213.41 / Opus4.7 128.72 / Sonnet4.6 82.84 / Haiku4.5 6.68. Norm Opus4.8=1: Opus4.7 0.60, Sonnet4.6 0.39, Haiku 0.031. (long-game sim, single best-run = noisy)
- AutomationBench [2604.18934, max effort]: Opus4.7 9.9%/$1.80 ; Sonnet4.6 5.3%/$1.81 (SAME cost, lower score) ; Haiku4.5 1.5%/$0.18.
- OfficeQA Pro [2603.08655, 5 Claude]: Cost$ Opus4.6 8.61/Opus4.5 5.34/Sonnet4.6 6.45/Sonnet4.5 3.81/Haiku4.5 2.84. Sonnet4.6/Opus4.6=0.75; Opus4.6 ~1.2M tok/q.
- SlopCodeBench [2603.24755, coding, 4 Claude]: $/CKPT Sonnet4.5 1.49/Sonnet4.6 1.92/Opus4.5 2.64/Opus4.6 3.47. Sonnet4.6/Opus4.6=0.55.
- PostTrainBench [2603.08640, EFFORT on reasoning-heavy]: Opus4.5 Medium vs High → AvgTok 10.58M vs 29.13M (2.8x), score 13.77→17.76 (+29%). => effort PAYS on reasoning-automation (unlike coding plateau).
- Forage V2 [2604.19837]: Opus4.6 $5.05 vs Sonnet4.6 $9.40 NVIDIA (Sonnet DEARER 1.86x — cold-start extra rounds); Sonnet-seeded $5.13.
- Price Reversal [2603.23971]: Opus4.6(thinking)+Haiku4.5 per-dataset $+tokens (decouples cost/accuracy).
- MODERATE: Parthenon Law [2606.04602] Sonnet4.6 $0.81/matter; NatureBench [2606.24530] Opus4.7/4.6 (cost in Appx D, unextracted).

## 21. CRITERIA SYNTHESIS (task-type / complexity / caching / harness modulate everything)
- TASK TYPE:
  * Pure coding (SWE, Terminal, SlopCode): effort→quality FLAT/plateau (+0.3-1.3pp max vs low); Sonnet4.6/Opus ~0.55-0.75.
  * Reasoning/math/automation (FrontierMath, HLE, PostTrain): effort→quality BIG (medium→high +29%; +9-12pp). Effort WORTH it here.
  * Computer-use (OSWorld 2.0): VERY expensive ($20-72/task), wide cross-model spread.
  * Long-game agentic (CEO-Bench, Forage): cross-model ratio widens/ inverts (turn-count driven; cold-start retries).
- COMPLEXITY: harder → effort helps more (whitekumalabo, PostTrain) UNTIL overthinking inverted-U (2606.08878, 2604.10739).
- CACHING: can dominate cross-model $ (copilot#1770 2.7x from broken cache); ~93-96% cache-read on agentic (swe-rebench).
- HARNESS/scaffold: huge (Terminal-Bench Claude Code 256M input tok; CORE-Bench scaffold; single-turn vs agent-harness SWE-Pro).
- GENERATION: newer Opus = more token-efficient (4.7<4.6 cost repeatedly: swe-rebench, WildClaw, TrueFoundry); newer models plateau LATER on effort (2606.17930).
- Sonnet5 = OUTLIER: verbose (2.5x Opus4.8 tokens) → per-task $ can EXCEED Opus4.8 despite lower rate (morphllm, AA, ai-engineering-trend).

## WAVE 4 (recent-models salvo) merges
### MERGED — Agent-14 recent boards (mostly re-confirm; NEW = Vals Index)
- Vals Index (independent intelligence composite, finance+coding agentic): Fable5 75.14 / Opus4.8 70.36 ($2.90/test) / Sonnet5 68.61 / Opus4.7 66.10 / Sonnet4.6 60.06 / Haiku4.5(thinking) 40.90. => 2nd independent intelligence axis (complements AA Index).
- Vals EMB (spreadsheets, agentic): Opus4.8 69.37%/$12.00/task ; Sonnet5 66.32%/$15.44/task (Sonnet5 PRICIEST — re-confirms morphllm). 
- AA Index run-cost re-confirmed: Opus4.8 $3752.55/120M ; Opus4.7 $3737.82/100M ; Sonnet5 $6015.18/300M ; Fable5 87M. NOTE AA "Index" score now shown 61.4 for Opus4.8 (vs 56 earlier) — index VERSION bumped; use scores only within one snapshot.
- Harness confound loud: Terminal-Bench2.1 Opus4.8 = 84.6% (AA) vs 71.91% (Vals) — same model, diff harness = 13pt gap.
- Dead ends: LiveBench/BenchLM no cost col; metatext/pricepertoken 403/404; AA eval cost cells chart-only.

### MERGED — Agent-16 forums + Agent-17 GitHub (recent, same-task)
- AIReiter [SAME task, effort-matched high, real CC CLI] Sonnet5/Opus4.8 $ by TYPE: coding $0.378/$0.439=0.86 ; writing $0.072/$0.084=0.86 ; agentic-dir $0.119/$0.120=0.99. (Sonnet5-xhigh vs Opus4.8-medium coding = $0.390/$0.401 wash.) => small tasks S5≈0.86-0.99×Opus4.8; contrasts AA long-agentic 1.15. TASK-SIZE dependent.
- ctala/ai-benchmarks-alternativos [Spanish 141-LLM, ≥20 runs, cost/1k-calls]: Opus4.8 $39/1k (q8.65) ; Haiku4.5 $7.80/1k (q8.44) ; Fable5 ~$78/1k (q8.38) ; Sonnet4.6 (q8.04). => Fable5/Opus4.8=2.0x, Haiku4.5/Opus4.8=0.20x (3RD independent source matching WorkBench 1.95/0.19 + AA). Fable does NOT beat Opus quality despite 2x cost. force_reasoning=high HURT quality -0.67(Opus4.7)/-0.50(Sonnet4.6) → overthinking.
- honey-for-devs [committed]: Opus4.8 token-reduction by task tier: code -49%, UI -6%, agent-handoff -51%; Opus4.8 vs GPT5.5 same-task (Opus larger swings). Satellite skills -43 to -86% output.
- pxpipe: Fable5 SWE-Lite -65% req size (10/10 pass), SWE-Pro -60% (14/19 vs 15/19).
- Fable5/Opus4.8 $ (Index/planning): X-post 1.68x ($6.2K/$3.7K), HN ~2x, ctala 2.0x → cluster ~1.7-2.0x.
- Haiku4.5/Sonnet4.5 = 0.33 (caylent calc, $0.07/$0.21).
- GH#64961: Opus4.8 post-update 2-3x token regression (cache collapse, 29 issues). HN48737858: Sonnet5-low ~half Sonnet4.6-med, ~25% < Opus4.8-low (computer-use).
- Illustrative/weak (flagged): mindstudio 10-step calc, developersdigest 50k/day, HN anecdotes ($200/20min).

## 22. CROSS-MODEL Sonnet4.6/Opus $ ratio — ALL same-task points (for normalization)
0.39(CEO) 0.55(SlopCode) 0.58(WorkBench) 0.61(STAGE) 0.63(Braintrust) 0.64(swe-rebench) 0.75(OfficeQA) 1.0(AutomationBench) 1.86(Forage-cold). Median ~0.6, coding-cluster 0.55-0.64. => Opus/Sonnet4.6 ≈ 1.6 (1/0.6) same-gen, consistent w/ earlier.

## 23. CONFIRMED cross-model anchors ÷Opus4.8 (3+ independent methods → HIGH conf)
Fable5 ~2.0 (WorkBench 1.95, ctala 2.0, X-post 1.68, HN 2x) · Opus4.8 1.00 · Opus4.7 ~0.6-1.1 (CEO 0.60, but swe-rebench/WildClaw show 4.7 cheaper than 4.6...gen-eff) · Sonnet4.6 ~0.6 (WorkBench 0.58, ctala-implied, swe-rebench 0.64, many) · Haiku4.5 ~0.19-0.20 (WorkBench 0.19, ctala 0.20) · Sonnet5 0.86-1.6 TASK-SIZE-dependent (small ~0.86, long-agentic ~1.15-1.6; verbosity).
Intelligence axes (recent): AA-Index Fable60/Opus4.8-56/Opus4.7-54/Sonnet5-53/Sonnet4.6-47 ; Vals-Index Fable75.1/Opus4.8-70.4/Sonnet5-68.6/Opus4.7-66.1/Sonnet4.6-60.1/Haiku4.5-40.9.

### MERGED — Agent-15 recent blogs (thin; ecosystem mostly re-quoted)
- arxiv 2606.15689 [CODE REVIEW, autodev-relevant!]: Haiku4.5 3.2x LOWER cost/review than Sonnet4.6, F1 0.365 vs 0.343 (+18% recall). "bigger isn't better" on review. Haiku4.5/Sonnet4.6 = 0.31 (matches cluster). => strong support for Haiku reviewers.
- FullStack Labs [own IT bench, 5 runs]: Opus4.8 ~half tokens & -40% $ vs Opus4.7 (cross-gen eff); Sonnet5 <half $/correct-result (mid task); frontier: Sonnet5 -15% $ but Opus4.8 more token-eff (inversion).
- every.to: Fable5 500k-1M tok/task, quality 91 vs Opus4.8 63 (codebase rewrite — Fable big win on hardest).
- natesnewsletter [own judgment bench]: Opus4.8 81 > GPT5.5 71 > Opus4.7 54 > Sonnet4.6 52 (quality only).
- ksred: real aggregate ~/.claude tokens (Jun 421M, Jul 2.4B) but no per-task A/B.
- CALCULATED/requoted (flagged): digitalapplied, finout, caylent, youcanbuildthings (Haiku subagent $0.045 vs Opus $0.225 = 0.20, matches anchor), sebuzdugan.
NOTE agent confirms: 2026 ecosystem is OVERWHELMINGLY re-quoted Anthropic/AA — genuine independent hands-on cost tests are RARE (~4-6 per salvo). The independent-measurement pool is saturating.

### MERGED — Agent-13 recent academic
- TOBench [2605.16909, tool-use, CLEAN per-model $+tok]: Haiku4.5 $0.27/244K ; Opus4.6 $2.37/330K ; Sonnet4.6 $1.67/370K. Haiku/Sonnet4.6=0.16, Sonnet4.6/Opus4.6=0.70, Haiku/Opus4.6=0.11.
- SkillsBench [2602.12670, only academic w/ Opus4.8 $]: Opus4.8 $14.02-22.70/trial, Opus4.7 $6.37-10.99, Sonnet4.6 ~$10-12.3. ⚠️ Opus4.8 ~2x Opus4.7 HERE (contradicts FullStack -40% & swe-rebench) — harness/effort-coupled, HIGH variance. Flag.
- NatureBench [2606.24530]: Opus4.7 $21.65/case (24.25M in/179K out) vs Opus4.6 $16.56 (9.03M/87.6K). 4.7/4.6=1.31.
- Claw-SWE-Bench [2606.12344]: Opus4.7 77.1% $3.09/inst (35.6M in/6.2M out, 97% cache).
- AgentOpt [2604.06296, role-combos]: Opus4.6-solo $60.13, Haiku+Haiku $0.79, Opus4.6+Haiku-critic $123.87.
- Terminal-Bench Haiku4.5 tokens ×4 harnesses (OH 663M in caching artifact). AgentCyberRange Opus4.7 token-only. EnterpriseClaw/T1-Bench/AgenticReview cost figure/aggregate-only.
- KEY GAP: NO academic paper measures Sonnet5 / Fable5 / Opus4.8-solo cost yet (too new: Sonnet5 Jun30, Fable5 Jul1). Those rely on AA + blogs/forums only.

## ====== WAVE 4 COMPLETE. CORPUS FROZEN FOR CONSOLIDATION ======
Total independent MEASUREMENT sources ~55-60 (distinct from ~150 catalog URLs, most of which re-cite). Confidence: cross-model anchors HIGH; effort-slope MEDIUM-HIGH (coding); Sonnet5 & top-effort tails WIDE. Ready to build raw CSV → normalized CSV → artifact.

## 17. INDEPENDENT MEASUREMENT-SOURCE COUNT (distinct from the 108 catalog; many catalog entries just re-cite Anthropic)
Real measurement sources so far (~15): Anthropic OSWorld chart, Anthropic Opus4.5 effort→tok, AA Index (per-variant), gh#64153, gh#45862, gh#51809, gh#23706, caveman, testing-claude-agent, Vexp, SWE-Mini, Sekinal, rigel, mindstudio, dave-c(enterprise).
=> Meets "much more than 1". BUT: only Anthropic OSWorld gives a clean per-effort×per-model×$ grid. GitHub sources are single-task, high variance (2x run-to-run), heterogeneous tasks => good for VARIANCE BOUNDS + effort DIRECTION, weak for tight per-cell $.

## 18. CONFIDENCE VERDICT (pre-graph)
- HIGH confidence: per-token pricing; effort DIRECTION (higher=more tokens); "medium deceptively costly on 4.7/4.8" (4+ sources agree); Sonnet5 verbosity 2.5x Opus (AA+Sekinal); run-to-run variance ~2x.
- MEDIUM: per-effort $ SHAPE within a model (OSWorld only, 1 src) — plausible but unverified externally.
- LOW: cross-model $ ratio (benchmark-unstable: 1.15-1.60-2.45 across sources) — must be a RANGE not a point; and derived cells for Haiku/Fable/Opus4.7 per effort.
- => A graph now would need CI bands so wide (esp cross-model & xhigh/max) it'd be more honest as "direction + order-of-magnitude" than precise curves.
- STRONGEST path to real confidence = self-measure via ccusage/cccost at each effort on representative autodev tasks (generates clean, autodev-relevant, low-variance-if-averaged cells). Public data alone caps confidence at MEDIUM.
