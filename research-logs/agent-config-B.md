# Extracted model-run configuration — 3 papers

Fetch method: ar5iv.labs.arxiv.org/abs/<ID> worked for all three (after a 301 redirect from ar5iv.org/abs/<ID>). Verified each paper's identity independently (title/authors/abstract matched across two separate fetches) before trusting the extracted quotes.

---

## 1. STAGE-Claw — arXiv 2606.10394
Title (verified): "STAGE-Claw: Automated State-based Agent Benchmarking for Realistic Scenarios"
URL used: https://ar5iv.labs.arxiv.org/abs/2606.10394

- **Extended thinking / reasoning enabled?** NO — explicitly disabled.
  Quote (Section 3.3, "Evaluation Settings"):
  > "All models were tested within the framework of OpenClaw, with reasoning disabled and temperature set to 0 when configurable"

- **Effort level / thinking budget_tokens:** NOT STATED. No `budget_tokens`, no effort-level (low/medium/high/xhigh/max) keyword found anywhere for Claude models.

- **Agent harness / scaffold:** "OpenClaw" framework, named but **no version number given**.
  Quote: "All models were assessed in the framework of OpenClaw, with reasoning disabled and temperature set to 0"

- **Temperature / sampling:** 
  Quote: "temperature set to 0 when configurable (otherwise using the provider-fixed temperature)"

- **Identical settings across models?** Partially — reasoning disabled for all, but temperature note explicitly carves out an exception ("otherwise using the provider-fixed temperature"), and the paper separately remarks GPT-5.5 ran with "reasoning (thinking) modules turned off" (Section 3.4, Main Results) as a caveat affecting cross-model comparison — so NOT a clean "identical settings" claim.

---

## 2. TOBench — arXiv 2605.16909
Title (verified): "TOBench: A Task-Oriented Omni-Modal Benchmark for Real-World Tool-Using Agents"
URL used: https://ar5iv.labs.arxiv.org/abs/2605.16909

- **Extended thinking / reasoning enabled?** NOT STATED anywhere for Claude models (Haiku 4.5 / Opus 4.6 / Sonnet 4.6).

- **Effort level / thinking budget_tokens:** NOT STATED.

- **Agent harness / scaffold:** Only a generic "ReAct" agent framework is named (Appendix C, Agent System Prompt), no product/version:
  Quote: "You are an intelligent Omni-Modality ReAct (Reasoning and Acting) Agent"
  Also: "The Agent System Prompt defines the ReAct reasoning framework and incorporates task-specific Domain Rules."
  No named/versioned harness like "Claude Code" or similar.

- **Temperature / sampling:** NOT STATED.

- **Identical settings across models?** NOT STATED — Table 2 (Section 5.2, Main Results) reports "15 representative proprietary and openly accessible models together with average tool calls and token usage" but no inference-hyperparameter uniformity statement is made.

---

## 3. CEO-Bench — arXiv 2606.18543
Title (verified): "CEO-Bench: Can Agents Play the Long Game?" (Haozhe Chen, Karthik Narasimhan, Zhuang Liu — Princeton)
URL used: https://ar5iv.labs.arxiv.org/abs/2606.18543

- **Extended thinking / reasoning enabled?** Mixed / model-dependent, per Section 3.1 (Experimental Setup) model list:
  Quote: "Claude Opus 4.8 max, Claude Opus 4.7 max, Claude Sonnet 4.6 max, Claude Haiku 4.5 thinking"
  → Opus 4.8 / Opus 4.7 / Sonnet 4.6 run at "max" (effort), Haiku 4.5 explicitly run with "thinking" mode. So thinking/extended-reasoning is effectively ON in some form for all four, but the exact mode label differs (max vs thinking) — not a single uniform flag.

- **Effort level / thinking budget_tokens:** Effort labels given as above ("max" for three, "thinking" for Haiku 4.5). No numeric `budget_tokens` value stated anywhere.

- **Agent harness / scaffold:** A custom minimal harness, unnamed/unversioned as a product:
  Quote: "To align the harness across all models, we implement a minimal terminal agent interface: we give each agent a Linux working directory and tools including bash, read-file, and edit-file."
  Also notes a harness ablation (Section 4.3) against off-the-shelf scaffolds:
  Quote: "Agents take significantly fewer actions when using Claude Code and Codex, resulting in inferior performance."
  → Main results harness = the paper's own minimal terminal interface, NOT Claude Code/Codex.

- **Temperature / sampling:** NOT STATED.

- **Identical settings across models?** Harness is explicitly stated as aligned/identical across models ("To align the harness across all models…"), BUT the effort/thinking configuration is NOT identical (max vs thinking differ by model) — so harness-identical but inference-config not fully identical.

---

## Compact cross-paper note
Only CEO-Bench gives any effort/thinking label at all (max / thinking), and even there it's not uniform across the four Claude models. STAGE-Claw explicitly turns reasoning OFF for everything (uniform). TOBench states nothing on this axis. None of the three states a `budget_tokens` numeric value. None claims full identical-settings validity without caveat.
