# Proof: effort/thinking config of the "NS" scientific sources (paper text + repo code)

## WorkBench Revisited (2606.13715) — repo github.com/olly-styles/WorkBench
Model call: `src/evals/inference.py`
- L108: `temperature=0,`
- L231: `"supports_temperature": route.supports_temperature,`  (temperature passed only where the model permits it)
- NO `thinking`, NO `effort`, NO `output_config`, NO `budget_tokens`, NO `reasoning` anywhere in the call.
Paper §2.1 (verbatim): "native tool-calling (structured output)… up to 20 steps… temperature set to zero where the model permits it."
→ VERDICT: no extended thinking configured. On raw API (mid-2026) that = adaptive OFF for Opus 4.6/4.7/4.8 & Sonnet 4.6 (thinking off), while Fable 5 always thinks (default effort high). MIXED regime within the source.

## WildClawBench (2605.10912) — repo github.com/internlm/WildClawBench
Driver: `eval/run_batch.py`
- L183: `thinking: str | None = None,`   (thinking is an optional CLI arg, DEFAULT None = not set)
- L376: `thinking=args.thinking,`
- DEFAULT_MODEL = `openrouter/anthropic/claude-sonnet-4.6`; models shipped via OpenRouter.
- Harnesses include `src/agents/claudecode/` and `src/agents/openclaw/` (multi-harness).
Paper §4.1 (verbatim): "All models are shipped through a unified OpenRouter endpoint."
→ VERDICT: thinking defaults to None (off) unless `--thinking` passed; paper doesn't report passing it → no extended thinking.

## code-review / VibeOps (2606.15689)
Paper §3.3 (verbatim): "Temperature was set to 0.1 for all models. No provider-specific prompt tuning was applied."
Repo: "vibeops-mcp/evals/" mentioned, no explicit GitHub URL in paper; not code-verified.
→ VERDICT (text proof): only temperature 0.1 set, no thinking/effort mentioned → no extended thinking.

## TOBench (2605.16909)
Paper §5.1 (verbatim): "each run is capped at 100 interaction turns" — execution constraints only.
→ VERDICT (text proof): no inference config at all → defaults (no extended thinking).

## AutomationBench (2604.18934) — CORRECTION
Paper §6 leaderboard labels: "Opus 4.7 (max)", "Sonnet 4.6 (max)".
→ VERDICT: max effort (not default). raw-data.csv corrected opus-4.7 & sonnet-4.6 → max.

## Consequence
The "grey @default" points from WorkBench / TOBench / code-review / WildClaw are NOT "unknown effort":
they are a **no-extended-thinking / minimal** regime (proven). Distinct from the low→max effort ladder
(which only applies when thinking is on). Confound to flag: Fable 5 always thinks, so any Fable-vs-Opus
ratio from these sources compares thinking-Fable vs no-thinking-Opus (e.g. WorkBench C47 fable/opus4.8).
