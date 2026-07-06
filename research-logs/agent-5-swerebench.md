<!-- 10 Claude model rows. ROUTE THAT WORKED: route 1 variant — curl-downloaded the swe-rebench.com homepage HTML (13.1 MB) and parsed the embedded Next.js RSC data payload (self.__next_f). No public JSON/API endpoint exists (all /api, /*.json, /_next/data 404'd); HF dataset nebius/SWE-rebench-leaderboard holds only TASK instances, not model results. All measured numbers below are from that embedded payload; DOM-rendered cells cross-checked and matched exactly. -->
<!-- effort/config: modelId agentVersion is "tools" for all (SWE-agent tool-use scaffold), except "Claude Code" which is the Claude Code agent. -high / -xhigh = reasoning effort as labeled by the board. -->
<!-- cost/problem = instanceCosts (avg USD/problem); tokens/problem = totalTokenUsage (avg tokens/problem, incl. cached); cached% shown as note. resolved% = mean resolved rate (pass@1 avg) ±sem; passN% = resolved-any / pass@N second column. -->
<!-- SAME-INSTANCE group: the 5 recent models were all evaluated on the SAME default window task set (range 1772323200000:1778803200000, ~2026 latest window) -> directly comparable measured cost/tokens. Older models were run on earlier task windows (their all-time cumulative record, range 1735689600000:1778803200000) -> NOT same-instance with the recent 5. -->
<!-- Absent from board: Claude Sonnet 5, Claude Haiku 4.5, Fable 5 (not present). -->

| model | effort/config | resolved% | passN% | cost/problem | tokens/problem | cached% | source-URL |
|---|---|---|---|---|---|---|---|
| Claude Opus 4.8-xhigh | tools, xhigh effort; SAME-INSTANCE window | 56.5% ±1.20 | 67.3% | $2.02 | 2,479,387 | 95.3% | https://swe-rebench.com/ (embedded RSC payload) |
| Claude Opus 4.7-high | tools, high effort; SAME-INSTANCE window | 53.1% ±1.45 | 66.4% | $1.32 | 1,526,135 | 94.2% | https://swe-rebench.com/ (embedded RSC payload) |
| Claude Opus 4.6-high | tools, high effort; SAME-INSTANCE window | 47.8% ±1.37 | 60.9% | $1.53 | 1,828,649 | 93.6% | https://swe-rebench.com/ (embedded RSC payload) |
| Claude Sonnet 4.6 | tools; SAME-INSTANCE window | 51.3% ±0.55 | 63.6% | $1.29 | 2,644,577 | 95.6% | https://swe-rebench.com/ (embedded RSC payload) |
| Claude Code | Claude Code agent (primary model Opus 4.6); SAME-INSTANCE window | 59.6% ±1.98 | 72.7% | $1.74 | 1,878,248 | 93.6% | https://swe-rebench.com/ (embedded RSC payload) |
| Claude Opus 4.5 | tools; own earlier window (all-time cumulative) | 53.1% | — | $1.15 | 1,358,096 | 95.2% | https://swe-rebench.com/ (embedded RSC payload) |
| Claude Sonnet 4.5 | tools; own earlier window (all-time cumulative) | 52.4% | — | $0.98 | 1,995,407 | n/a | https://swe-rebench.com/ (embedded RSC payload) |
| Claude Opus 4.1 | tools; own earlier window (all-time cumulative) | 43.5% | — | $4.25 | 1,779,063 | n/a | https://swe-rebench.com/ (embedded RSC payload) |
| Claude Sonnet 4 | tools; own earlier window (all-time cumulative) | 44.6% | — | n/a (not tracked) | n/a (not tracked) | n/a | https://swe-rebench.com/ (embedded RSC payload) |
| Claude Sonnet 3.5 | tools; own earlier window (all-time cumulative) | 30.3% | — | n/a (not tracked) | n/a (not tracked) | n/a | https://swe-rebench.com/ (embedded RSC payload) |
