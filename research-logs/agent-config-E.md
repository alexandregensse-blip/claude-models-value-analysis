# Model-run configuration extraction — 4 community sources

## 1. ctala — ai-benchmarks-alternativos
Repo: https://github.com/ctala/ai-benchmarks-alternativos
Files fetched: https://raw.githubusercontent.com/ctala/ai-benchmarks-alternativos/main/benchmarks/runner.py
and https://raw.githubusercontent.com/ctala/ai-benchmarks-alternativos/main/providers/adapters.py (both resolved on `main`, no 404).

- **Thinking/reasoning**: NOT enabled for Claude specifically. The only reasoning-control flag found is `force_reasoning`, and it is explicitly scoped to *other* (hybrid) models, not Claude:
  > "If model_config has force_reasoning=True (modelos hybrid como Hermes 4, Kimi K2.5), el adapter activa reasoning vía OpenRouter extra_body."
  No `thinking=`, `budget_tokens=`, or Claude-specific reasoning toggle exists in either file.
- **Effort/budget_tokens**: NOT STATED / absent. Generic `temperature=0.7` and `max_tokens=2048` apply uniformly across models; no per-model reasoning-budget allocation.
- **Harness**: Claude models run through a dedicated `ClaudeCodeProvider` class that shells out to the CLI:
  > invokes `claude -p` with flags `"--disallowedTools", "*", "--exclude-dynamic-system-prompt-sections"`
  Marked `"subscription_measured": True` — confirms the README's "via Claude Code subscription" note. (Other, non-Claude models go through OpenRouter via `providers/adapters.py`'s `UnifiedProvider`.)
- **All models identical config?**: NOT STATED explicitly for Opus 4.8 / Fable 5 / Haiku 4.5 individually — the `ClaudeCodeProvider` code path applies uniformly to all Claude models (no per-Claude-model override seen), but no explicit statement that Opus/Fable/Haiku settings are identical beyond that.
- README (fetched from https://github.com/ctala/ai-benchmarks-alternativos) additionally states:
  > "Thinking models allocated 4× max_tokens (8192 minimum output)" and "Documented that 'thinking forzado EMPEORA multi-turn agéntico' (forced reasoning degrades multi-turn agent performance in 8/9 tested models)"
  This 4x-max_tokens / forced-reasoning-hurts finding is a general benchmark note, not shown to be Claude-model-specific in the fetched code.

## 2. drona23 — claude-token-efficient
Repo: https://github.com/drona23/claude-token-efficient
Files fetched: README (via github.com page), and https://raw.githubusercontent.com/drona23/claude-token-efficient/main/benchmark/run.py (resolved on `main`, no 404).

- **Thinking/reasoning**: NOT mentioned/NOT STATED. README: "contains no references to thinking mode, reasoning mode, or extended thinking capabilities being enabled or disabled." `run.py` also contains **no** thinking/reasoning/effort/budget_tokens/temperature configuration of any kind.
- **Effort**: NOT STATED — no effort tier defined anywhere in README or script.
- **Harness**: Claude Code CLI, confirmed directly in code:
  ```python
  cmd = [
      "claude", "-p", prompt,
      "--model", model,
      "--output-format", "json",
      "--setting-sources", "project",
  ]
  ```
  This delegates to the local `claude` CLI (OAuth/subscription session) — not raw Anthropic API, not OpenRouter.
- **All models identical?**: Yes — model is just a runtime `--model haiku|sonnet|opus` argument swap; "no special parameters tune their behavior in the benchmark code itself," so Haiku 4.5 / Sonnet 4.6 / Opus 4.6 get identical invocation code, differing only in the `--model` value.
- Methodology caveat quoted from README: "This is a 5-prompt directional indicator (T1-T3, T5 for word reduction; T4 is a format test), not a statistically controlled study." and "Claude's output length varies naturally between identical prompts. No variance controls or repeated runs were applied."

## 3. ponytail — DietrichGebert/ponytail
Repo: https://github.com/DietrichGebert/ponytail (README + `benchmarks/` directory listing fetched)

- **Thinking/reasoning**: NOT explicitly stated as enabled or disabled for the measured runs. Only an incidental/general remark appears:
  > "a terse reasoning model that spends thinking tokens deliberating the rungs can go the other way"
  This is commentary on reasoning-model economics generally, not a statement that thinking was toggled on/off for the Claude runs.
- **Effort/budget**: NOT STATED.
- **Harness**: Claude Code, confirmed:
  > "The honest measurement is a real agent doing real work: a headless Claude Code session editing tiangolo's full-stack-fastapi-template"
  For the older single-shot comparison, `benchmarks/` contains `promptfooconfig.yaml` (main setup) plus provider-specific configs (`promptfooconfig.gpt.yaml`, `promptfooconfig.gpt-newest.yaml`, `promptfooconfig.gemini.yaml`) — i.e., that portion of the suite runs via promptfoo, not confirmed as Claude Code for the cross-model comparison. The agentic/headless-Claude-Code portion is explicitly Claude Code.
- **All models identical?**: NOT STATED explicitly. Quoted: "Five everyday tasks, three models, three arms (no skill, caveman, ponytail), ten runs, median reported" with a chart "Median lines of code per arm across Haiku, Sonnet and Opus" — but the README text fetched does not name exact version numbers (4.5/4.6) for that specific chart, nor confirm identical thinking/effort settings across the three.
- No explicit `--model` flag or extended-thinking configuration was found in the fetched content.

## 4. ianlpaterson — ianlpaterson.com
Page identified via search: https://ianlpaterson.com/blog/llm-benchmark-2026-38-actual-tasks-15-models-for-2-29/
(Initial fetch of the bare domain https://ianlpaterson.com did not surface this specific post; found via WebSearch then fetched the direct blog URL.)

- **Thinking/reasoning**: NOT enabled — explicitly stated:
  > "All 15 models were called through the same OpenRouter API with identical parameters: a system prompt, a user prompt, and max_tokens=8192. No model received special reasoning configuration."
- **Effort/budget_tokens**: NOT STATED / none used — no budget_tokens or effort parameter for any model, Claude included.
- **Harness**: OpenRouter, explicitly:
  > "All models run through OpenRouter for apples-to-apples comparison."
  (Confirmed as the finalized method after a v2 rerun corrected earlier infrastructure issues.)
- **All models identical?**: Yes, explicitly:
  > "every model was called through the same OpenRouter API with identical parameters" — applies uniformly to Haiku 4.5, Sonnet 4.6, and Opus 4.6, same system/user prompt and max_tokens=8192, no model-specific adjustment.
