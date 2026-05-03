---
step: "5"
requires: []
produces: []
sendmessage: n/a
---

# Step 5: TOKEN ANALYSIS (mandatory)

This file is read by the orchestrator just-in-time before executing Step 5.
The orchestrator's residual `SKILL.md` (Step Dispatch table) routes here. Shared
protocols (SendMessage notes, Step 0.6 token tracking, Backlog Integration) live
in `SKILL.md` and remain accessible.

Launch token analysis **in the background** concurrently with Step 4 finalization — the
TOKEN_LEDGER is complete after Step 3.5, so analysis can run while ORCHESTRATOR.md is updated
and `gh pr ready` runs. Always runs, not skippable.

**5.1 Compute Summary.** Record `PIPELINE_END`. Compute `TOKEN_SUMMARY` from `TOKEN_LEDGER`:
totals across all entries, per-model breakdown (call count + input/output tokens), per-step
breakdown by prefix (`1a`, `1b`, `1.5`, `2`, `2.1`, `2.2`, `3.5`), estimated cost (Haiku $1/$5,
Sonnet $3/$15, Opus $15/$75 per M tokens in/out), actual cost-weighted model distribution vs.
the 70/20/10 target, and counts of `is_escalation`/`is_retry` entries.

**5.2 Derive Pipeline Repo.** `PIPELINE_REMOTE=$(git -C <pipeline_root> remote get-url origin)`.
Parse SSH (`git@github.com:owner/repo.git`) or HTTPS (`https://github.com/owner/repo.git`),
strip trailing `.git`.

**5.3 Launch Token Analysis.** Invoke the skill with the ledger, summary, and pipeline context:

```
Skill: token-analysis
Prompt: |
  Read `.claude/skills/token-analysis/SKILL.md` for your instructions.

  TOKEN LEDGER: <paste the full TOKEN_LEDGER as a markdown table>
  TOKEN SUMMARY: <paste the computed TOKEN_SUMMARY>

  PIPELINE CONTEXT:
  - Plan file: .claude/tmp/1b-plan.md (planned vs actual model assignments)
  - Pipeline repo: <owner/repo>
  - Pipeline root: <pipeline_root>
  - Target project stacks: <stacks (comma-separated)>
  - Pipeline duration: <PIPELINE_START> to <PIPELINE_END>
```

**5.4 Report Results.** `FINDINGS: NONE` → "no significant optimization opportunities found".
`FINDINGS: FILED` with issue URL → "findings filed as <issue URL>". Skill failure or
`gh issue create` error → log a warning and report; do NOT mark the pipeline failed.
