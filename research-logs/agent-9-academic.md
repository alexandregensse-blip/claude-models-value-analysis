# Agent-9 Academic papers — per-Claude-model cost/token findings
# Format: arxiv-id/URL | benchmark | models/efforts | score | cost | tokens | table-ref | notes
# NEW distinct papers: 7 (EnergyAgentBench, Terminal-Bench 2.0, OSWorld 2.0, STAGE-Claw, WorkBench Revisited, DABstep, AstaBench)
# NEW measured data points: 26 rows (~24 with firm measured cost or tokens; AstaBench Opus4.6 cost implied, Sonnet4.6 cost n/a)
# HAL (2510.11977) NOT re-reported: PDF >10MB / no HTML render; its SWE-bench-Mini/tau-airline/DABstep leaderboard costs already captured via hal.cs.princeton.edu. DABstep listed here from the DABstep PAPER's own Table 1 (may overlap HAL).
# Excluded (had <2 Claude models OR no cost/tokens): OccuBench(6 Claude, no cost), MacAgentBench(1 Claude), WebMall(1 Claude Sonnet4), MMTB(1 Claude), General Agent Eval 2602.22953(1 Claude Opus4.5), BigFinanceBench(cost only in figure), SWE-Cycle/EHR-Complex/DecisionBench(no per-model cost), CFAgentBench(hypothetical cost only), Token Arena(no breakdown), PaperBench(judge cost only)

arxiv 2605.15230 (EnergyAgentBench) | EnergyAgentBench (70 agentic energy tasks, 1414 runs) | Claude Sonnet 4.6 | 0.900 composite | $0.059/run mean | n/a (per-run tokens logged, not aggregated in table) | Table 4 | harness: Anthropic Messages API tool-use, temp=0, 3 seeds, max 100 turns; May 2026 list prices Sonnet $3/$15 per M
arxiv 2605.15230 (EnergyAgentBench) | EnergyAgentBench | Claude Opus 4.7 | 0.889 composite | $0.267/run mean | n/a | Table 4 | 4.5x cost of Sonnet for -1.1pt; $52 of ~$75 total spend was Opus; Opus prices $15/$75 per M; temp param omitted for Opus
arxiv 2605.15230 (EnergyAgentBench) | EnergyAgentBench | Claude Haiku 4.5 | 0.830 composite | $0.018/run mean | n/a | Table 4 | Haiku $1/$5 per M; leads F1 Long-horizon (0.986) beating Opus/GPT-5
arxiv 2601.11868 (Terminal-Bench 2.0) | Terminal-Bench 2.0 (74 tasks) | Claude Opus 4.5 (Terminus 2) | 57.8%±2.5 | no USD in paper | 3.9M in / 1.3M out (total, 74 tasks) | Table 2 (App A.1) | resolution rate; multiple harnesses per model
arxiv 2601.11868 (Terminal-Bench 2.0) | Terminal-Bench 2.0 | Claude Opus 4.5 (Claude Code) | 52.1%±2.5 | — | 256.9M in / 0.8M out | Table 2 | note huge input tokens under Claude Code harness (caching artifact)
arxiv 2601.11868 (Terminal-Bench 2.0) | Terminal-Bench 2.0 | Claude Opus 4.5 (OpenHands) | 51.9%±2.9 | — | 151.4M in / 1.4M out | Table 2 |
arxiv 2601.11868 (Terminal-Bench 2.0) | Terminal-Bench 2.0 | Claude Sonnet 4.5 (Terminus 2) | 42.8%±2.8 | — | 3.1M in / 1.1M out | Table 2 |
arxiv 2601.11868 (Terminal-Bench 2.0) | Terminal-Bench 2.0 | Claude Sonnet 4.5 (Mini-SWE-Agent) | 42.5%±2.8 | — | 3.4M in / 1.4M out | Table 2 |
arxiv 2601.11868 (Terminal-Bench 2.0) | Terminal-Bench 2.0 | Claude Sonnet 4.5 (Claude Code) | 40.1%±2.9 | — | 2.0M in / 0.1M out | Table 2 |
arxiv 2601.11868 (Terminal-Bench 2.0) | Terminal-Bench 2.0 | Claude Opus 4.1 (Terminus 2) | 38.0%±2.6 | — | 2.3M in / 0.9M out | Table 2 |
arxiv 2601.11868 (Terminal-Bench 2.0) | Terminal-Bench 2.0 | Claude Haiku 4.5 (Mini-SWE-Agent) | 29.8%±2.5 | — | 3.6M in / 1.4M out | Table 2 | Haiku best under Mini-SWE-Agent 29.8%; 28.3% Terminus2
arxiv 2606.29537 (OSWorld 2.0) | OSWorld 2.0 (computer-use, 500-step, max reasoning) | Claude Opus 4.8 (batched actions) | 20.6% binary / 54.8% partial | ~$72.4/task | ~224K out tok/task | Table 3 | approx values (extracted); batched = strongest config
arxiv 2606.29537 (OSWorld 2.0) | OSWorld 2.0 | Claude Opus 4.7 (batched) | 18.2% binary / 48.91% partial | ~$33.6/task | ~150K out tok/task | Table 3 | approx
arxiv 2606.29537 (OSWorld 2.0) | OSWorld 2.0 (single action) | Claude Sonnet 4.6 | 8.3% binary / 41.5% partial | ~$22.3/task | ~185.9K out tok/task | Table 3 | approx; single-action setting
arxiv 2606.10394 (STAGE-Claw) | STAGE-Claw (state-based agent benchmark) | Claude Opus 4.7 | 77.1 score / 80.0% first-pass | $6.55/task avg | 1.242M tok/task avg | Table 2 | highest score of 11 frontier models; cost/token = avg per task
arxiv 2606.10394 (STAGE-Claw) | STAGE-Claw | Claude Sonnet 4.6 | 69.43 score / 65.0% first-pass | $3.98/task avg | 1.265M tok/task avg | Table 2 | only 2 Claude variants in main table
arxiv 2606.13715 (WorkBench Revisited) | WorkBench (workplace agent, 5-DB sandbox) | Claude Fable 5 | 97.7% task completion / 1.9% side-effects | $0.355/task | n/a (cost from token approx, tokens not itemized) | Table 1 | cost est = 4 chars/token + ~7k/call overhead
arxiv 2606.13715 (WorkBench Revisited) | WorkBench | Claude Opus 4.8 | 96.2% completion / 2.5% side-effects | $0.182/task | n/a | Table 1 | best pre-Fable agent
arxiv 2606.13715 (WorkBench Revisited) | WorkBench | Claude Sonnet 4.6 | 88.3% completion / 8.8% side-effects | $0.105/task | n/a | Table 1 |
arxiv 2606.13715 (WorkBench Revisited) | WorkBench | Claude Haiku 4.5 | 74.8% completion / 16.7% side-effects | $0.034/task | n/a | Table 1 | 21 models total spanning Mar2023-May2026
arxiv 2506.23719 (DABstep) | DABstep (data analysis, easy/hard splits) | Claude 3.7 Sonnet | 13.76% hard / 75.00% easy | $139 total run | n/a (tokens used for cost est only) | Table 1 | costs = Q1 2025 public pricing; NOTE cost figures also surfaced on HAL leaderboard (may overlap)
arxiv 2506.23719 (DABstep) | DABstep | Claude 3.5 Sonnet | 9.26% hard / 77.78% easy | $97 total run | n/a | Table 1 |
arxiv 2506.23719 (DABstep) | DABstep | Claude 3.5 Haiku | 5.03% hard / 77.78% easy | $35 total run | n/a | Table 1 |
arxiv 2510.21652 (AstaBench) | AstaBench (scientific research agent suite, 2400+ problems) | Claude Opus 4.7 | 58.0% overall | $3.54/problem avg | n/a | aggregate leaderboard (Ai2 live/spring-2026 update) | source = AstaBench leaderboard; verify exact table in paper; Opus 4.7 = +2.7pt vs 4.6 at ~62% more cost/problem
arxiv 2510.21652 (AstaBench) | AstaBench | Claude Opus 4.6 | 55.3% overall | ~$2.18/problem (implied, 62% less than 4.7) | n/a | aggregate leaderboard | cost implied from "Opus 4.7 costs ~62% more per problem"; treat as approx
arxiv 2510.21652 (AstaBench) | AstaBench | Claude Sonnet 4.6 | 54.5% overall | cost n/a (lower tier) | n/a | aggregate leaderboard | score confirmed; per-problem cost not captured in excerpt
