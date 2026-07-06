# Model-run configuration extraction — 3 arXiv papers

Fetch method: `https://ar5iv.org/abs/<ID>` → 301 redirect → `https://ar5iv.labs.arxiv.org/abs/<ID>` (fetched successfully for all 3). Quotes below are as returned by the ar5iv HTML rendering.

---

## Paper 1 — 2606.13715 (WorkBench Revisited) — Opus 4.8, Sonnet 4.6, Haiku 4.5, Fable 5

- **Extended/adaptive thinking enabled?** NOT STATED. No mention of extended thinking / adaptive thinking / reasoning for the Claude models or any model.
- **Effort level / budget_tokens?** NOT STATED.
- **Agent harness / scaffold + version:** Native tool-calling ReAct-style loop; no version number given. Section 2.1 (Experimental Setup):
  - "The original paper ran each model as a ReAct loop that parsed a tool call out of free-form text. We instead use the native tool-calling (structured output) interface that every current model provider exposes."
- **Temperature / sampling:** Section 2.1:
  - "The loop is otherwise unchanged: the agent is given the task, all 26 tools, and up to 20 steps to reach a final state, with temperature set to zero where the model permits it."
- **Identical settings across models?** Yes (stated):
  - "We adopt it for every model so that the comparison is like-for-like."

Note: temperature is "zero where the model permits it" — i.e. NOT strictly identical, since some models don't permit temperature control (relevant to ratio validity: Fable 5 / Opus 4.8 reject sampling params).

---

## Paper 2 — 2602.12670 (SkillsBench) — Opus 4.8, Opus 4.7, Sonnet 4.6

- **Extended/adaptive thinking enabled?** NOT STATED. No mention of thinking/reasoning modes being activated.
- **Effort level / budget_tokens?** NOT STATED.
- **Agent harness / scaffold + version:** Reported harnesses (Appendix C.7 / Table 8): **Claude Code 2.1.19**, Gemini CLI (version not given), Codex CLI / OpenAI (version not given).
  - ⚠️ DISCREPANCY vs the task brief, which said "harness: OpenHands". The fetched content reports Claude Code / Gemini CLI / Codex CLI, NOT OpenHands. Flagging for the coordinator — either the brief is wrong or the fetch surfaced a different harness table. Not independently re-verified against the PDF.
- **Temperature / sampling:** §C.9 (Inference Configuration): "Temperature: 0 (deterministic sampling)".
- **Identical settings across models?** Yes (stated), §C.9: all configs used "Temperature: 0 for deterministic sampling" plus identical max rounds and timeout protocols.

---

## Paper 3 — 2603.24755 (SlopCode) — Opus 4.6, Sonnet 4.6

- **Extended/adaptive thinking enabled?** YES (stated). "For Claude Code, we configure the thinking-token budget via the environment variable following Anthropic's published mapping."
- **Effort level / budget_tokens?** Effort = **high**. Table 3 shows "Reasoning: high" for all Claude models (listed: Sonnet 4.5, Sonnet 4.6, Opus 4.5, Opus 4.6, GLM 4.7). No explicit numeric budget_tokens value quoted (configured via env-var mapping, not a raw number).
- **Agent harness / scaffold + version:** Claude Code harness; versions vary by model — reported values 2.0.65, 2.1.44, 2.0.51, 2.1.32, 2.0.76 (Section 3.2 "Agent Harnesses" / Appendix A). Also: "For older models whose launch-era harness was unavailable or incompatible, we used the nearest later compatible version."
- **Temperature / sampling:** NOT STATED (no temperature/sampling parameters given).
- **Identical settings across models?** Partial. "Shared configuration. Three settings are held constant across all runs: a two-hour wall-clock limit per checkpoint, no maximum turn or cost cap, and a minimal prompt." — but harness VERSION differs per model, so runs are not fully identical.

---

## Caveat
Extraction relies on the ar5iv HTML rendering read by WebFetch's summarizer; exact quote wording (esp. table values and version strings) should be confirmed against the source PDF before being treated as verbatim. The SkillsBench harness (OpenHands vs Claude Code) discrepancy is the most material item to resolve.
