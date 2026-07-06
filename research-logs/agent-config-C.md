# Model-run configuration extraction — 4 papers

Fetched via https://ar5iv.labs.arxiv.org/abs/<ID> (ar5iv.org redirected there, 301). Raw HTML head confirmed genuine (curl), title matches for paper 1: "[2603.08655] OfficeQA Pro: An Enterprise Benchmark for End-to-End Grounded Reasoning", LaTeXML-generated March 2026.

---

## 1. arXiv 2603.08655 — OfficeQA Pro (Opus 4.6, Sonnet 4.6, Haiku 4.5)

**Title**: "OfficeQA Pro: An Enterprise Benchmark for End-to-End Grounded Reasoning"
Authors: Krista Opsahl-Ong, Arnav Singhvi, Jasmine Collins, Ivan Zhou, Cindy Wang, Ashutosh Baheti, Owen Oertell, Jacob Portes, Sam Havens, Erich Elsen, Michael Bendersky, Matei Zaharia, Xing Chen.

- **Extended thinking / reasoning enabled?** YES. Section 3.1 (LLM Baselines):
  > "Claude Opus 4.6 uses high reasoning by default"
- **Effort level / budget_tokens**: HIGH reasoning (no numeric budget_tokens given). Section 3.1:
  > "GPT 5.4 was configured to run with high reasoning because Claude Opus 4.6 uses high reasoning by default and Gemini 3.1 Pro Preview uses high thinking level by default."
  Also: "For each setting, we configure the models to have 50k maximum output tokens." (output-token cap, not a thinking budget).
- **Agent harness/scaffold**: Section 3.2 references "Claude Opus 4.6 Agent [evaluated using] Claude Agent SDK" — no version number given.
- **Temperature/sampling**: NOT STATED — no explicit temperature values found anywhere in the document per the fetch.
- **Identical-settings note**: Models were made *comparable* (each provider's own high-reasoning/high-thinking default), not run under one literal identical numeric setting — Section 3.1 frames it as matching each provider's own default "high" tier across Claude/GPT/Gemini.

---

## 2. arXiv 2605.10912 — WildClawBench / OpenClaw (Opus 4.7, Opus 4.6)

- **Extended thinking / reasoning enabled?** NOT STATED for Claude models specifically. The fetch found thinking-mode discussion (Table 5, low/medium/high) only for GPT 5.4; no mention of Claude models using extended thinking.
- **Effort level / budget_tokens**: NOT STATED for Claude.
- **Agent harness/scaffold**: Multiple harnesses tested:
  > "Each task runs in an isolated Docker container under one of four agent harnesses (OpenClaw, Claude Code, Codex, and Hermes Agent)."
  Default/main-results harness = OpenClaw. No version numbers reported for any harness.
- **Temperature/sampling**: NOT STATED — "the paper does not disclose temperature or sampling parameter settings for any models."
- **Identical-settings note**: YES, explicit —
  > "All models are shipped through a unified OpenRouter endpoint, and each harness ships as a dedicated Docker image with pinned OS, Python toolchain, and pre-installed binaries."
  > "Tool schemas, system prompts, and context-management policies are held fixed within each harness, so within-harness differences across models reflect model behavior rather than scaffold variation."

---

## 3. arXiv 2604.18934 — AutomationBench (Opus 4.7, Sonnet 4.6, Haiku 4.5)

- **Extended thinking / reasoning enabled?** NOT STATED. No documentation found of whether extended thinking was enabled for the evaluation runs.
- **Effort level / budget_tokens**: NOT STATED.
- **Agent harness/scaffold**: NOT STATED (no scaffold/harness details found for the evaluation itself). Note: "Opus 4.6, GPT 5.3 Codex, and Gemini 3" are mentioned in Section 2 but only as models used for *task generation*, not as the evaluated harness/config.
- **Temperature/sampling**: NOT STATED.
- **Identical-settings note**: NOT STATED — the fetch reports the paper's Section 6 leaderboard (Opus 4.7 9.9%/$1.80, Gemini 3.1 Pro 9.6%/$0.54, GPT 5.4 variants, Sonnet 4.6 5.3%, Haiku 4.5 1.5%) but no accompanying methodology text on config parity. Overall: "The experimental methodology sections lack the standard model configuration documentation typically found in LLM benchmarking papers."

---

## 4. arXiv 2606.15689 — "Bigger Isn't Always Better" code-review study (Haiku 4.5, Sonnet 4.6)

**Title**: "Bigger Isn't Always Better: A Comparative Evaluation of LLMs for Automated Code Review"
Authors: Shivam Pankaj Kumar, Swati Bararia, Kislay Raj.
Abstract (verbatim excerpt): evaluates "Claude Sonnet 4.6, Claude Haiku 4.5, GPT-5.4 mini, Minimax M2.7, and GLM-5 Turbo across 150 code review samples." Finding: Haiku 4.5 "consistently outperforms the larger Claude Sonnet 4.6, achieving higher F1 (0.365 vs. 0.343), 18% higher recall" at "3.2x lower cost per review."

- **Extended thinking / reasoning enabled?** NOT STATED — no references to extended thinking, reasoning tokens, or thinking-budget configuration found for any of the 5 models under test.
- **Effort level / budget_tokens**: NOT STATED for the models under test. (Separate: the LLM-judge model is given an explicit temperature, see below — no effort/thinking setting there either.)
- **Agent harness/scaffold**: Not a scaffold in the agentic sense — models are called via a fixed production prompt:
  > "All models received the identical production prompt (the VibeOps review system prompt)" (Section 3.3)
  No named/versioned agent harness beyond this "VibeOps review system prompt."
- **Temperature/sampling**: STATED — Section 3.3 (Models Under Test):
  > "Temperature was set to 0.1 for all models."
  Separately, the judge model: Section 3.2 — "Claude Opus 4.6 (temperature 0.0) adjudicates deferred cases."
- **Identical-settings note**: YES, explicit — same temperature (0.1) and same prompt for all 5 models under test (Section 3.3).

---

## Fetch method note
All 4 papers successfully fetched on the first alternate attempt: `https://ar5iv.org/abs/<ID>` returned a 301 redirect to `https://ar5iv.labs.arxiv.org/abs/<ID>`, which was then fetched directly and succeeded for all 4 IDs. No fallback to arxiv.org/pdf or arxiv.org/abs was needed for full-text extraction (arxiv.org/abs was used only as a spot-check for title/abstract verification on papers 1 and 4).
