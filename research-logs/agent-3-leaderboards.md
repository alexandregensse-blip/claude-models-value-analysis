# Agent-3 leaderboards — NEW measured per-model cost/token findings
# count: 29 measured data points (+2 source notes)
# format: URL | benchmark | models/efforts | resolved%_or_score | cost/task_or_total | tokens | notes

# === HAL (Holistic Agent Leaderboard, Princeton) — SAME-INSTANCE, measured total cost per model/effort. GOLD. ===
https://hal.cs.princeton.edu/swebench_verified_mini | SWE-bench Verified Mini (50 instances) | Claude Sonnet 4.5 High (Sep2025) | 72.0% | $463.90 total | - | same 50-instance set; "High"=high reasoning effort; Pareto-optimal
https://hal.cs.princeton.edu/swebench_verified_mini | SWE-bench Verified Mini (50) | Claude Sonnet 4.5 (Sep2025) | 68.0% | $505.92 total | - | same set; DEFAULT effort costs MORE than High variant (72%/$463.90) — effort-vs-cost inversion
https://hal.cs.princeton.edu/swebench_verified_mini | SWE-bench Verified Mini (50) | Claude Opus 4.1 (Aug2025) default | 61.0% | $1351.35 total | - | same set; (HAL summary page elsewhere showed 68% — detailed page says 61%, discrepancy)
https://hal.cs.princeton.edu/swebench_verified_mini | SWE-bench Verified Mini (50) | Claude Opus 4.1 High (Aug2025) | 54.0% | $1599.90 total | - | same set; High effort LOWER score, higher cost than default Opus 4.1
https://hal.cs.princeton.edu/swebench_verified_mini | SWE-bench Verified Mini (50) | Claude-3.7 Sonnet High (Feb2025) | 54.0% | $388.88 total | - | same set
https://hal.cs.princeton.edu/swebench_verified_mini | SWE-bench Verified Mini (50) | Claude-3.7 Sonnet (Feb2025) | 50.0% | $402.69 total | - | same set
https://hal.cs.princeton.edu/swebench_verified_mini | SWE-bench Verified Mini (50) | Claude Opus 4 (May2025) | 50.0% | $1330.90 total | - | same set

# CORE-Bench Hard — same instance set BUT two scaffolds (Claude Code vs CORE-Agent) = confound; cost NOT comparable across scaffold
https://hal.cs.princeton.edu/corebench_hard | CORE-Bench Hard | Claude Opus 4.5 (Nov2025) [Claude Code] | 77.78% (95.5% manual) | $87.16 total | - | scaffold=Claude Code
https://hal.cs.princeton.edu/corebench_hard | CORE-Bench Hard | Claude Sonnet 4.5 (Sep2025) [Claude Code] | 62.22% | $68.33 total | - | scaffold=Claude Code
https://hal.cs.princeton.edu/corebench_hard | CORE-Bench Hard | Claude Sonnet 4 (May2025) [Claude Code] | 46.67% | $65.58 total | - | scaffold=Claude Code
https://hal.cs.princeton.edu/corebench_hard | CORE-Bench Hard | Claude Opus 4.1 (Aug2025) [Claude Code] | 42.22% | $331.79 total | - | scaffold=Claude Code
https://hal.cs.princeton.edu/corebench_hard | CORE-Bench Hard | Claude Opus 4.1 (Aug2025) [CORE-Agent] | 51.11% | $412.42 total | - | scaffold=CORE-Agent (diff harness)
https://hal.cs.princeton.edu/corebench_hard | CORE-Bench Hard | Claude Sonnet 4.5 High [CORE-Agent] | 44.44% | $92.34 total | - | scaffold=CORE-Agent
https://hal.cs.princeton.edu/corebench_hard | CORE-Bench Hard | Claude Opus 4.5 High (Nov2025) [CORE-Agent] | 42.22% | $152.66 total | - | scaffold=CORE-Agent
https://hal.cs.princeton.edu/corebench_hard | CORE-Bench Hard | Claude Opus 4.5 (Nov2025) [CORE-Agent] | 42.22% | $168.99 total | - | scaffold=CORE-Agent; Opus4.5 High cheaper than default here
https://hal.cs.princeton.edu/corebench_hard | CORE-Bench Hard | Claude Sonnet 4.5 (Sep2025) [CORE-Agent] | 37.78% | $97.15 total | - | scaffold=CORE-Agent
https://hal.cs.princeton.edu/corebench_hard | CORE-Bench Hard | Claude-3.7 Sonnet (Feb2025) [CORE-Agent] | 35.56% | $73.04 total | - | scaffold=CORE-Agent
https://hal.cs.princeton.edu/corebench_hard | CORE-Bench Hard | Claude Sonnet 4 High (May2025) [CORE-Agent] | 33.33% | $100.48 total | - | scaffold=CORE-Agent
https://hal.cs.princeton.edu/corebench_hard | CORE-Bench Hard | Claude Haiku 4.5 (Oct2025) [CORE-Agent] | 11.11% | $43.93 total | - | scaffold=CORE-Agent; only Haiku 4.5 cost point found anywhere

# GAIA — same instance set, measured total cost
https://hal.cs.princeton.edu/ | GAIA | Claude Sonnet 4.5 (Sep2025) | 74.5% | $178.20 total | - | HAL; default effort beats High here
https://hal.cs.princeton.edu/ | GAIA | Claude Sonnet 4.5 High (Sep2025) | 70.9% | $179.86 total | - | HAL
https://hal.cs.princeton.edu/ | GAIA | Claude Opus 4.1 High (Aug2025) | 68.5% | $562.24 total | - | HAL; Opus ~3x Sonnet cost for lower score

# ScienceAgentBench — same set; two models SAME score, cost differs (clean ratio)
https://hal.cs.princeton.edu/ | ScienceAgentBench | Claude Sonnet 4.5 High (Sep2025) | 30.4% | $7.47 total | - | same 30.4% as 3.7-Sonnet-High but 36% cheaper
https://hal.cs.princeton.edu/ | ScienceAgentBench | Claude-3.7 Sonnet High (Feb2025) | 30.4% | $11.74 total | - | identical score, $11.74 vs $7.47 = clean cost ratio

# TAU-bench Airline — same set
https://hal.cs.princeton.edu/ | TAU-bench Airline | Claude-3.7 Sonnet (Feb2025) | 56.0% | $42.11 total | - | HAL; cheaper AND higher than Opus 4.1 here
https://hal.cs.princeton.edu/ | TAU-bench Airline | Claude Opus 4.1 (Aug2025) | 54.0% | $180.49 total | - | HAL; ~4.3x cost of 3.7-Sonnet for lower score

# === Artificial Analysis — per-task cost on Intelligence Index (v4.1), same eval suite ===
https://artificialanalysis.ai/articles/claude-sonnet-5-agentic-cost | AA Intelligence Index (per-task) | Sonnet 5 | Index 53 | $2.29/task | Sonnet5 uses ~40% more output tokens & ~3x agentic turns vs Sonnet 4.6 | measured same-suite per-task
https://artificialanalysis.ai/articles/claude-sonnet-5-agentic-cost | AA Intelligence Index (per-task) | Sonnet 4.6 | - | ~$1.15/task | ~40% fewer output tokens than Sonnet5 | derived (~2x note) — approximate
https://artificialanalysis.ai/articles/claude-sonnet-5-agentic-cost | AA Intelligence Index (per-task) | Opus 4.8 | - | ~$1.99/task | - | Sonnet5 ~15% more expensive/task than Opus4.8 (same suite)
https://artificialanalysis.ai/articles/claude-opus-4-5-benchmarks-and-analysis | AA Terminal-Bench Hard + Intelligence Index total | Claude Opus 4.5 | 44% Terminal-Bench Hard | ~$1.5k to run full Intelligence Index | - | NEW Opus4.5 index-total cost point (adds to known 4.7/4.8/Sonnet5/Fable5)

# === SWE-bench Pro cost-per-task (aggregated, measured via vals.ai runs) ===
https://www.morphllm.com/best-ai-model-for-coding | SWE-bench Pro cost/task | Claude Opus 4.8 | 69.2% Pro (leads active) | ~$12/task | - | cost/task aggregated from vals.ai measured runs; Opus4.8 most-accurate-lowest-cost
https://www.morphllm.com/best-ai-model-for-coding | SWE-bench Pro cost/task | Claude Sonnet 5 | 63.2% Pro | $15.44/task | - | priciest per-task of the set despite lower score than Opus4.8 (token-inefficiency)

# === SOURCE NOTES (data exists but could not extract exact per-model numbers) ===
# https://swe-rebench.com/ | SWE-rebench (decontaminated) | has per-model "Cost per Problem" + "Tokens per Problem" columns for Claude Sonnet 3.5/4/4.5/4.6/5, Opus 4.8 | resolved rates: Sonnet5 72.7%, Sonnet4.6 62.3%, Opus4.8 79.4% (SWE-bench-Verified-equiv) | cost/tokens NOT extractable via WebFetch (page >10MB) — HIGH VALUE, revisit with browser/API
# https://www.tbench.ai/leaderboard/terminal-bench/2.0 | Terminal-Bench 2.0 | ~35 Claude rows across Opus 4.1/4.5/4.6/4.7, Sonnet 4.5/4.6, Haiku 4.5 (e.g. Opus4.7/WOZCODE 80.2%, Opus4.5/ClaudeCode 52.1%, Sonnet4.5/ClaudeCode 40.1%, Haiku4.5/ClaudeCode 27.5%) | NO cost/token columns — score-only, per-harness (heavy scaffold confound)
