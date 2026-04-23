---
name: token-analysis
description: >
  Analyzes token usage data from a completed pipeline run. Identifies optimization
  opportunities, cost anomalies, and model distribution drift. Files a GitHub issue
  on the pipeline repo if significant findings exist. Used as Step 5 (mandatory) of
  the orchestration pipeline after finalization.
---

# Token Analysis Skill

You receive a `TOKEN_LEDGER` and `TOKEN_SUMMARY` from a completed orchestration pipeline run.
Your job is to identify actionable optimization opportunities and, if significant, file
them as a GitHub issue on the pipeline repository.

## Inputs

The orchestrator provides:
1. **TOKEN_LEDGER** — per-agent-call breakdown (step, agent, model, input/output tokens, retry/escalation flags)
2. **TOKEN_SUMMARY** — aggregated totals, model breakdown, step breakdown, cost estimates
3. **PIPELINE CONTEXT** — plan file path, pipeline repo `owner/repo`, stack name

## Analysis Process

### 1. Cost Breakdown

Compute estimated cost per step and per model using these rates:

| Model  | Input (per M tokens) | Output (per M tokens) |
|--------|---------------------|-----------------------|
| Haiku  | $1.00               | $5.00                 |
| Sonnet | $3.00               | $15.00                |
| Opus   | $15.00              | $75.00                |

Identify the top 3 most expensive steps by total cost.

### 2. Model Distribution Analysis

Compare actual model usage **by estimated dollar cost** (not call count or raw token count)
against the 70/20/10 target:
- **Haiku** should be ~70% of total dollar spend
- **Sonnet** should be ~20%
- **Opus** should be ~10%

**Plan-type adjustment:** The 70/20/10 target assumes feature work where implementation
dominates cost. For **refactor** plan types, planning and review inherently exceed
implementation cost — use **50/40/10** as the comparison baseline instead. Identify the
plan type from the 1b-plan.md `## Overview` section or the PR title prefix (`refactor:`).
Flag deviations only against the appropriate baseline.

Compute each model's share as: `model_cost / total_cost × 100`. Report BOTH cost-weighted
percentages AND call-count percentages — but flag deviations based on the cost metric only.
Call-count percentages can create a false sense of efficiency (e.g., "69% Haiku calls" while
Haiku accounts for only 12% of spend).

Flag if any model deviates more than 15 percentage points from its target on the cost metric.

### 3. Prompt Efficiency Analysis

For each agent call, compute the input-to-output ratio. Flag:
- **Oversized prompts**: `input_tokens > 10× output_tokens` — the prompt is doing too much work
  for too little output; the context brief or overlay may be bloated
- **Oversized context briefs**: any single implementer prompt > 8,000 input tokens — suggests the
  planner included unnecessary context
- **Overlay bloat**: if the same overlay content appears in > 5 agent calls and totals > 20,000
  tokens across all calls, note the cumulative cost of that overlay

### 4. Escalation & Retry Analysis

Review all entries where `is_escalation` or `is_retry` is true:
- **Escalation patterns**: If a Haiku task needed escalation to Sonnet for fixes, this suggests
  the planner should have assigned Sonnet originally or decomposed further
- **Retry storms**: If any task went through 2+ review-fix cycles, compute the total cost of the
  retry chain vs. the original task cost
- **Blast-radius triggers**: If Step 3.5 triggered architect blast-radius analysis, note this as
  a planning quality signal

### 5. Performance Analysis

Evaluate pipeline execution characteristics:
- **Step token weight**: which steps consume the most tokens relative to their role (e.g.,
  clarification consuming more than implementation suggests unclear scope)
- **Planning overhead**: ratio of planning tokens (1a + 1b) to implementation tokens (2 + 2.1 + 2.2).
  Flag if planning > 40% of implementation for feature plan types. For refactor plan types,
  planning > 100% of implementation is expected (dependency verification before deletes IS
  the value of Step 1a) — use 100% as the flag threshold.
- **Review cost ratio**: total review + fix tokens vs. implementation tokens. A ratio > 0.5
  suggests implementations are frequently failing review — possible quality issue in context briefs

### 6. Anomaly Detection

Flag any of these anomalies:
- A single agent call consuming > 30% of the total pipeline tokens
- Step 1a (clarification) consuming more tokens than Step 2 (implementation)
- Step 1b (planning) output tokens exceeding all implementer output tokens combined
- Any Haiku agent call with output > 5,000 tokens (Haiku should produce < 150 lines)
- Total pipeline cost exceeding $5.00 for a single feature

### 7. Hidden Token Sources

Examine the `files_read` and `agent_input_self` fields from agent TOKEN_REPORTs to assess
consumption invisible to the orchestrator's prompt-level tracking:

- **Agent definition reads**: If multiple agents of the same type each read their definition
  from disk (e.g., `implementer-agent.md` read 9 times), compute the cumulative cost. This is
  overhead the orchestrator cannot eliminate without inlining definitions.
- **Redundant file reads**: If the same source file is read by multiple agents (e.g., a shared
  types file read by 4 implementers), flag this as a planning opportunity — the planner could
  inline the relevant types into each brief instead.
- **Large file ingestion**: Any single file read > 5,000 chars by a Haiku agent is suspect —
  Haiku tasks should be self-contained from their brief, not reading large files.
- **Self-assessed vs orchestrator-tracked delta**: Compare each agent's `agent_input_self` to the
  orchestrator's `input_chars`. The difference represents hidden consumption (file reads, tool
  outputs, agent definition ingestion). Compute the total delta across all agents — this is the
  "blind spot" the orchestrator's prompt-level tracking misses.

If total hidden consumption exceeds 30% of orchestrator-tracked consumption, flag this as a
significant finding.

## Significance Threshold

Only file a GitHub issue if **at least ONE** of these conditions is met:
- Model distribution deviates > 15 percentage points from the 70/20/10 target on any model
- Total escalation + retry cost exceeds 25% of total pipeline cost
- Any anomaly from Section 6 is detected
- 3 or more prompt efficiency flags from Section 3
- Review cost ratio > 0.5 from Section 5
- Hidden consumption exceeds 30% of orchestrator-tracked consumption (Section 7)

If none of these thresholds are met, output `FINDINGS: NONE` and stop.

## Issue Filing

If significant findings exist, file a backlog issue via the shared backlog-file
utility. Opt-in detection, label application, and traceability fields are all
handled by the utility — do not shell out to `gh issue create` directly.

### Invoke the Utility

```bash
python3 <pipeline_root>/scripts/backlog_file.py \
  --title "pipeline-tokens: <one-line summary of top finding>" \
  --type chore \
  --priority p2 \
  --body-context-json '{
    "phase": "token-analysis",
    "pr_number": "<PR_NUMBER>",
    "run_id": "<RUN_ID>",
    "reasoning": "<one-line: why this is Sonnet/Opus-tier, always defers>",
    "summary": "<top finding summary>",
    "context": "<full findings markdown body — use the template below>"
  }'
```

The utility:
- Detects opt-in via `.github/pipeline-backlog.yml` — skips silently if absent.
- Applies labels `type: chore`, `priority: p2`, `source: ai-deferred`.
- Includes the D8 traceability block in the body.
- Retries without `source: ai-deferred` if the label isn't yet provisioned.
- Returns a JSON result (`{"status": "filed" | "skipped" | "failed", ...}`).

Token-analysis findings are always tier=defer (the classification decision is
trivially always "defer" per the issue spec — token-level anomalies never fold).

If the utility returns `status: skipped` (repo not opted in), output
`FINDINGS: SKIPPED (backlog integration not enabled)` and stop. If `status: failed`,
surface the reason in the run log but do not error out.

The `context` field should hold the full findings markdown (cost breakdown,
model distribution, findings list) that was previously the body of the issue.

### Issue Body Template

Use this structure for the issue body:

```markdown
## Pipeline Token Analysis

**Date:** <date>
**Project stack:** <stack>
**Total pipeline cost:** $X.XX (estimated)
**Total tokens:** X input / X output
**Agent calls:** X total

## Cost Breakdown by Step

| Step | Agent Calls | Input Tokens | Output Tokens | Est. Cost |
|------|-------------|-------------|---------------|-----------|
| 1a: Analyze | X | X | X | $X.XX |
| 1b: Plan | X | X | X | $X.XX |
| 1.5: Open PR | X | X | X | $X.XX |
| 2: Implement | X | X | X | $X.XX |
| 2.1: Review | X | X | X | $X.XX |
| 2.2: Fix | X | X | X | $X.XX |
| 3.5: Bug Fix | X | X | X | $X.XX |
| **Total** | **X** | **X** | **X** | **$X.XX** |

## Model Distribution

| Model | Target % (cost) | Actual % (cost) | Delta | Calls (%) | Est. Cost |
|-------|----------------|-----------------|-------|-----------|-----------|
| Haiku | 70% | X% | +/-Xpp | X (X%) | $X.XX |
| Sonnet | 20% | X% | +/-Xpp | X (X%) | $X.XX |
| Opus | 10% | X% | +/-Xpp | X (X%) | $X.XX |

## Findings

### <Finding 1 Title>
**Severity:** High / Medium / Low
**Category:** cost | efficiency | performance | anomaly

<Description of the finding, why it matters, and what data supports it>

**Recommendation:** <specific, actionable recommendation for improving the pipeline>

### <Finding 2 Title>
...

## Raw Data

<details>
<summary>Full TOKEN_LEDGER</summary>

<paste the TOKEN_LEDGER table here for reference>

</details>

---
*Generated by the orchestration pipeline token-analysis skill.*
```

### Issue Title Convention

Use the prefix `pipeline-tokens:` followed by the most significant finding:
- `pipeline-tokens: opus usage 35% above target (45% vs 10%)`
- `pipeline-tokens: 3 escalations from haiku suggest planner under-decomposition`
- `pipeline-tokens: step 1a consumed more tokens than implementation`
- `pipeline-tokens: review-fix cycles cost 40% of total pipeline spend`

## Output Protocol

After analysis, output exactly one of:

**No significant findings:**
```
FINDINGS: NONE
```

**Findings filed:**
```
FINDINGS: FILED
<issue URL>
```
