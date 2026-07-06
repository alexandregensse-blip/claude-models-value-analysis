# Model-run configuration extraction — 4 benchmark sources

## 1. swe-rebench.com

URLs used: https://swe-rebench.com/about (fetched directly, full text), https://swe-rebench.com (via r.jina.ai reader, for leaderboard model-name strings), https://swe-rebench.com/methodology (404 — page does not exist).

**Scaffold:**
> "fixed scaffolding, i.e., every model is assessed by using the same minimal ReAct-style agentic framework" with "identical prompts and default generation hyperparameters as recommended by the model developers."

The scaffold is NOT explicitly named "SWE-agent" anywhere in the fetched /about text — it is described generically as a "minimal ReAct-style agentic framework". So: name-match to "SWE-agent" is NOT STATED (may or may not be SWE-agent under the hood; the site doesn't say).

**Context length standardization:**
> "We standardize the context length to 128K tokens for all evaluations (unless a model only supports a shorter context)."

**Philosophy on tuning:**
> "While model-specific tuning or a different scaffolding could potentially yield higher scores for a given model, our focus is on establishing a reliable baseline of model capabilities in a common setting."

**Per-model thinking/effort setting — evidence from the leaderboard itself:**
Distinct Claude model-name strings found verbatim on the leaderboard/model list:
- `Claude Opus 4.8-xhigh`
- `Claude Opus 4.7-high`
- `Claude Opus 4.6-high`
- `Claude Sonnet 4.6` (no suffix)
- also present without effort suffixes: Claude Opus 4.1, Claude Opus 4.5, Claude Sonnet 3.5, Claude Sonnet 4, Claude Sonnet 4.5
- Non-Anthropic models follow the same convention, e.g. `gpt-5.5-2026-04-23-xhigh`, `gpt-5.5-2026-04-23-medium`, `gpt-5.4-2026-03-05-medium`.

No footnote or explanatory text defining what the `-xhigh` / `-high` suffix means, nor any text explicitly stating that a bare model name (e.g. `Claude Sonnet 4.6`) means "run at the provider's default reasoning/effort setting". This is an **inference from naming convention**, not a quoted statement — the site does not explain it in prose anywhere I could fetch (checked /about, root page, /methodology [404]).

**Verdict for this source:** thinking/effort IS clearly per-model-configurable (visible in the model-name strings: Opus 4.8 run at `xhigh`, Opus 4.7/4.6 run at `high`, Sonnet 4.6 carries no suffix — implying default). Scaffold = "minimal ReAct-style agentic framework", identical across all models, but not confirmed by name to be "SWE-agent". No prose text explicitly defines "default" — NOT STATED as an explicit sentence, only inferable from the leaderboard naming.

---

## 2. Vals.ai EMB (Excel Modeling Benchmark)

URLs used: https://vals.ai/benchmarks/emb (direct — failed, `maxContentLength` exceeded), https://r.jina.ai/https://vals.ai/benchmarks/emb (reader proxy, full text), https://vals.ai/models/anthropic_claude-opus-4-8 (direct fetch), https://vals.ai/methodology (direct fetch, general methodology only).

**Harness (from the EMB page itself):**
> "Agents are evaluated on a shared harness, and nearly all of their work runs through two tools. **bash** is the primary tool, used to read data files, inspect the workbook, and write the Excel model. **execute** opens the workbook and recalculates its formulas"

This confirms a single shared harness across models for EMB, but the EMB page text fetched did NOT contain any per-model thinking/effort/reasoning mention for Opus 4.8 or Sonnet 5 specifically, and did not explicitly confirm/deny that "all models are run under identical settings" beyond describing the shared tool harness.

**Effort setting (from the Opus 4.8 model-specific page, not the EMB page):**
> "Compute Effort: max"

This is the only reasoning/effort configuration value found, and it comes from `vals.ai/models/anthropic_claude-opus-4-8`, not from a EMB-specific note. Whether "extended thinking" is on/off as a boolean is NOT STATED — only the "Compute Effort: max" label is given. I did not fetch a Sonnet-5-specific model page in this pass, so the equivalent setting for Sonnet 5 is **NOT STATED** (not directly verified) — a general vals.ai methodology page (`/methodology`) was fetched and contains only generic benchmarking framework text (task design, error bars) with no EMB- or model-specific effort detail.

A web-search snippet (unverified against a direct vals.ai fetch in this session) suggested: "evaluations were run with compute effort set to 'max' on all benchmarks except Terminal-Bench 2.1 (run at 'high')" — but I could not confirm this sentence's exact source/page directly, so treat it as **unverified / possibly not vals.ai's own text** (may originate from an Anthropic model-card rather than vals.ai). Not used in the summary as a quoted fact.

**Verdict for this source:** effort = "Compute Effort: max" confirmed for Opus 4.8 specifically (model page); Sonnet 5's setting NOT STATED (not directly checked); harness = shared bash+execute tool harness, described as uniform, but no explicit "identical settings across models" sentence found.

---

## 3. CodeSOTA (codesota.com)

URLs used: https://codesota.com (direct — failed, `maxContentLength` exceeded), https://r.jina.ai/https://codesota.com (reader proxy), https://codesota.com/methodology (direct), https://codesota.com/about (direct), https://www.codesota.com/agentic/openrouter-models (direct fetch + reader), plus web-search snippets for `/agentic/openrouter-apps/*` subpages.

**Main site (methodology/about/homepage):** none of the fetched pages (methodology, about, homepage via reader, openrouter-models page) contained explicit text about how $/token costs are computed for Claude Opus 4.8 vs Claude Sonnet 4.6, nor any reasoning-effort/thinking configuration, nor an explicit harness statement for the core SOTA leaderboard. Direct quote from the fetch of `/methodology`:
> the page "focuses on how they measure machine learning benchmarks, verify results, and maintain their registry. It contains no pricing information, model comparisons, or cost computation details related to Claude models."

**Cost/pricing table on openrouter-models page:** shows raw list-price columns only —
> Claude Opus 4.8: $5.00/$25.00 ($/M in / $/M out); Claude Sonnet 4.6: $3.00/$15.00 — with no accompanying explanation of what these figures represent or how derived from usage.

**Blended-pricing formula (found on adjacent CodeSOTA "OpenRouter app" sub-pages, e.g. `/agentic/openrouter-apps/*`, via search-engine synthesis, NOT directly fetched page-by-page in this session):**
> "Blended $/M = price_in × 72% + price_out × 28%" — described as "vendor-weighted by real usage, so premium vendors show their true price per token," with the 72/28 split justified as "a reasonable approximation for tool-heavy agentic workloads... A 50/50 split inflates dollar totals by ~10–15%."
> Data sourcing: "OpenRouter publishes per-app token counts for every AI tool routing through it. CodeSOTA reads the public app listings, joins each model to live pricing, and ranks the top 30 apps by estimated 30-day spend."

Caveat: this blended-formula text was retrieved via a web-search synthesis over CodeSOTA's OpenRouter-app-mix pages, not a direct WebFetch quote-checked against the live page in this session — treat as **reported, not independently re-verified against the raw HTML**. It also describes CodeSOTA's OpenRouter app-spend analysis, not explicitly confirmed to be the same formula used for the Opus-4.8-vs-Sonnet-4.6 cost comparison the task asked about (that specific comparison page was not located).

**Effort/thinking setting for Opus 4.8 vs Sonnet 4.6 comparison:** NOT STATED — not found on any fetched CodeSOTA page.

**Harness:** OpenRouter is used as the pricing/usage data source ("OpenRouter publishes per-app token counts..."); whether OpenRouter is also the execution harness for capability/benchmark scoring (vs. just the cost/spend analytics) is NOT STATED distinctly — CodeSOTA appears to layer two things (a capability registry + an OpenRouter spend/pricing analytics section) and I could not confirm the two share one harness definition.

**Verdict for this source:** cost formula found (72/28 blended, OpenRouter-sourced) but only on OpenRouter-app-analytics sub-pages, not confirmed as the exact methodology for the Opus 4.8 vs Sonnet 4.6 comparison specifically; effort/thinking NOT STATED anywhere found.

---

## 4. TrueFoundry (truefoundry.com)

URL used: https://www.truefoundry.com/blog/claude-opus-4-8-and-swe-bench-pro-we-ran-anthropics-headline-through-our-gateway (direct fetch, full text). Also identified via blog index (https://www.truefoundry.com/blog) but no dedicated "Opus 4.8 vs Opus 4.7" title exists — this SWE-bench-Pro post is the one that runs both models head-to-head.

**Single-turn, no tools/no revision:**
> "Each problem describes a real bug in a real repository. We sent the description to the model in a single turn and asked for a unified diff"
> "No browsing. No terminal access. No second chance to revise."

This directly answers "thinking/reasoning enabled?" — the setup is a bare single-turn completion (no tool use, no multi-step agentic loop), which implies no extended-thinking/agentic scaffold was used, though the post does not use the literal words "thinking" or "reasoning effort" — so an explicit effort-level label (e.g. "low/high/max") is **NOT STATED**; only the operational description above is given.

**Grading:**
> "We then graded each response with a simple rule: does this look like a legitimate patch?"

**Harness/gateway:**
> "We routed Claude Opus 4.8 and Claude Opus 4.7 through TrueFoundry AI Gateway — the same OpenAI-compatible API surface"

**Identical execution across the two models:**
> "Behind the gateway, the two models landed on different provider routes. From the application's point of view, the integration was identical: same URL, same credentials, different model name."

**Results (context, not config):**
> "On our 50-problem sample, Opus 4.8 returned a patch-shaped answer every time — 50 out of 50. Opus 4.7 missed three, landing at 47 out of 50."

**Verdict for this source:** thinking/reasoning explicit effort level = NOT STATED (no "high"/"max" label used); the test design itself (single-turn, no tools) strongly implies no extended-thinking/agentic mode was invoked, but the post never uses the word "thinking" or "effort". Harness = TrueFoundry AI Gateway, "OpenAI-compatible API surface", confirmed identical integration path for both Opus 4.8 and Opus 4.7.
