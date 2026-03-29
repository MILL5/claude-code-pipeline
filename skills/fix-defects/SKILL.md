---
name: fix-defects
description: >
  Reads defect reports from GitHub PR comments and runs the pipeline to fix them.
  Use when the user says "fix defects", "fix PR defects", "fix reported bugs",
  "/fix-defects", or any request to process manual test feedback from a PR.
  Requires a PR with comments following the defect report schema
  (see templates/defect-report.md).
---

# Fix Defects Skill

You are the orchestrator running in **defect-fix mode**. You read structured defect reports
from GitHub PR comments, triage them by severity, and run the fix pipeline for each one.

This skill reuses the same agent coordination pattern as Step 3.5 of the orchestrate skill
but operates standalone — it does not require a prior orchestrate run.

## Prerequisites

Before starting, read these files (skip if already in context):
1. `.claude/ORCHESTRATOR.md` — architecture, conventions, fragile areas
2. `.claude/CLAUDE.md` — project rules
3. `.claude/pipeline.config` — stack and pipeline root

## Step 0: Identify the PR

Determine the target PR:

1. **If the user provides a PR number or URL:** use that directly.
2. **If on a feature branch with an open PR:** detect it:
   ```bash
   gh pr list --head "$(git branch --show-current)" --json number,url --jq '.[0]'
   ```
3. **If neither:** ask the user which PR to process.

Store `PR_NUMBER` and `PR_URL` for the session.

## Step 1: Load Adapter

Same as orchestrate Step 0:

1. Read `.claude/pipeline.config` to get `stack` and `pipeline_root`
2. Read `<pipeline_root>/adapters/<stack>/adapter.md`
3. Load overlay files for agent composition

## Step 2: Initialize Token Tracking

Initialize `TOKEN_LEDGER` and record `PIPELINE_START` timestamp. Use step prefix `defect:`
for all ledger entries (e.g., `defect:assess:1`, `defect:fix:1`, `defect:review:1`).

## Step 3: Fetch and Parse Defect Reports

Read all comments on the PR:

```bash
gh api repos/{owner}/{repo}/pulls/{PR_NUMBER}/comments --paginate
gh api repos/{owner}/{repo}/issues/{PR_NUMBER}/comments --paginate
```

Note: PR "review comments" (on specific lines) and "issue comments" (on the PR conversation)
are different GitHub API endpoints. Fetch both.

**Parse each comment** that contains `### DEFECT REPORT` (case-insensitive) as the header.

### Parsing Rules

For each defect report comment, extract:

| Field | How to extract | Required |
|-------|---------------|----------|
| `id` | Sequential number (1, 2, 3...) in order found | auto |
| `comment_id` | GitHub comment ID (for later reaction/reply) | auto |
| `severity` | Value after `**Severity:**` — must be CRITICAL, HIGH, MEDIUM, or LOW | yes |
| `component` | Value after `**Component:**` | no |
| `found_in` | Value after `**Found in:**` | no |
| `steps` | Numbered list items under `#### Steps to Reproduce` | yes |
| `expected` | Text under `#### Expected Behavior` | yes |
| `actual` | Text under `#### Actual Behavior` | yes |
| `screenshots` | All `![...](url)` image references under `#### Screenshots` | no |
| `environment` | Key-value pairs under `#### Environment` | no |
| `additional_context` | Text under `#### Additional Context` | no |
| `author` | GitHub username of the comment author | auto |

**Validation:** If a required field is missing, skip the defect and add a reply to the comment:

```bash
gh api repos/{owner}/{repo}/issues/{PR_NUMBER}/comments -f body="⚠️ Skipped: missing required field(s). See templates/defect-report.md for the schema."
```

**Report to user** the parsed defects:

> Found **N** defect report(s) on PR #X:
>
> | # | Severity | Component | Summary |
> |---|----------|-----------|---------|
> | 1 | CRITICAL | login flow | App crashes on submit |
> | 2 | HIGH | dashboard | Chart renders empty |
>
> Proceeding to fix in severity order (CRITICAL → HIGH → MEDIUM → LOW).

If no defect reports are found, tell the user and stop.

## Step 4: Triage and Order

Sort defects by severity: CRITICAL first, then HIGH, MEDIUM, LOW.
Within the same severity, preserve the order they appear in comments.

**For CRITICAL defects:** Always run blast-radius analysis (Step 5.1) before fixing.
**For HIGH defects:** Run blast-radius analysis if the defect crosses multiple components.
**For MEDIUM/LOW defects:** Skip blast-radius analysis unless the component maps to a
known fragile area in ORCHESTRATOR.md.

## Step 5: Fix Each Defect

For each defect, run this cycle:

### 5.1: ASSESS

The orchestrator assesses the defect — do NOT delegate to a subagent:

1. **Correlate** the defect to files in the codebase using the component, found_in field,
   and the steps to reproduce.
2. **Check fragile areas:** Cross-reference affected files against ORCHESTRATOR.md's
   "Known Fragile Areas". Note any matches.
3. **Classify:**
   - **Simple** (single file, clear cause, no fragile areas): proceed to 5.2.
   - **Complex** (multi-file, unclear cause, fragile area, or CRITICAL severity):
     launch blast-radius analysis.

**Blast-radius analysis prompt (complex defects):**

```
Agent: architect-agent
Model: sonnet
Prompt: |
  You are being launched by the pipeline to assess the blast radius of a defect fix.
  Do NOT write code. Do NOT enter plan mode — you may need to read code files.

  TECH STACK CONTEXT:
  <paste contents of adapter's architect-overlay.md>

  A defect was reported during manual testing. Assess the blast radius of fixing it
  and recommend a fix approach.

  DEFECT REPORT:
  Severity: <severity>
  Component: <component>
  Steps to Reproduce:
  <steps>
  Expected: <expected>
  Actual: <actual>
  Screenshots: <screenshot URLs and descriptions, or "none">
  Additional Context: <additional_context or "none">

  FILES IN REPOSITORY (relevant area):
  <list files in the component's directory>

  CODEBASE CONTEXT (ORCHESTRATOR.md fragile areas extract):
  <paste Known Fragile Areas section from ORCHESTRATOR.md>

  Respond with:
  1. ROOT CAUSE: Which file(s) likely caused this
  2. BLAST RADIUS: What other files/behaviors could be affected by a fix
  3. FRAGILE AREAS: Any Known Fragile Areas in the blast radius
  4. FIX APPROACH: Specific fix strategy (1-3 sentences)
  5. FILES TO MODIFY: Exact list
  6. REGRESSION RISK: Low/Medium/High with explanation
```

Record TOKEN_LEDGER entry: step `defect:assess:<id>`, agent `architect-agent`, model `sonnet`.

### 5.2: FIX

Launch an implementer agent to fix the defect:

```
Agent: implementer-agent
Model: sonnet (CRITICAL/HIGH/MEDIUM) or haiku (LOW, if single-file and clear cause)
Prompt: |
  You are being launched by the orchestration pipeline to fix a defect found
  during manual testing. Follow all rules from your agent definition.

  IMPORTANT: After fixing, run the FULL test suite (all targets), not just
  the modified files. Report the total passing test count in your output.
  If existing tests break, your fix introduced a regression — fix it before
  returning SUCCESS.

  TECH STACK CONTEXT:
  <paste adapter overlay — use essential variant for Haiku, full for Sonnet>

  DEFECT REPORT:
  Severity: <severity>
  Component: <component>
  Steps to Reproduce:
  <steps>
  Expected: <expected>
  Actual: <actual>
  Screenshots: <screenshot URLs — describe what they show if the tester included descriptions>
  Additional Context: <additional_context or "none">

  FIX APPROACH:
  <if complex: paste architect's fix approach from 5.1>
  <if simple: orchestrator's own assessment>

  FILES TO MODIFY:
  <file list from 5.1 or orchestrator's assessment>
```

Record TOKEN_LEDGER entry: step `defect:fix:<id>`, agent `implementer-agent`,
model per above, set `is_retry: false`.

### 5.3: REVIEW

```
Agent: code-reviewer-agent
Model: sonnet
Prompt: |
  You are being launched by the pipeline to review a defect fix.
  Follow your agent definition's Pipeline Mode protocol.

  TECH STACK CONTEXT:
  <paste adapter's reviewer-overlay.md>

  ORIGINAL DEFECT:
  Severity: <severity>
  Component: <component>
  Expected: <expected>
  Actual: <actual>

  FIX APPROACH:
  <the approach that was used>

  FILES MODIFIED:
  <list from implementer's SUCCESS output>
```

Record TOKEN_LEDGER entry: step `defect:review:<id>`, agent `code-reviewer-agent`, model `sonnet`.

**If FAIL:** Re-run 5.2 with the reviewer's issues as additional context.
Model escalates to Sonnet if it was Haiku. Max 2 fix-review cycles, then report to user.

### 5.4: COMMIT + PUSH

After a successful review:

```bash
git add <modified files>
git commit -m "fix(<component>): <description of fix>

Fixes defect #<id> (<severity>): <short summary of actual behavior>

Co-Authored-By: Claude <noreply@anthropic.com>"
git push
```

### 5.5: REPLY TO COMMENT

After committing the fix, reply to the original defect comment on the PR:

```bash
gh api repos/{owner}/{repo}/issues/{PR_NUMBER}/comments \
  -f body="✅ Fixed in commit $(git rev-parse --short HEAD). Please re-test.

**Fix summary:** <1-2 sentence description of what was changed>
**Files modified:** <comma-separated list>"
```

Also add a reaction to the original comment:

```bash
gh api repos/{owner}/{repo}/issues/comments/{comment_id}/reactions -f content="+1"
```

## Step 6: Summary Report

After processing all defects, report:

> **Defect Fix Summary for PR #X**
>
> | # | Severity | Component | Status | Commit |
> |---|----------|-----------|--------|--------|
> | 1 | CRITICAL | login flow | Fixed | abc1234 |
> | 2 | HIGH | dashboard | Fixed | def5678 |
> | 3 | MEDIUM | settings | Escalated to user | — |
>
> **X of Y defects fixed.** Remaining issues require manual intervention.

If all defects are fixed:

> All **N** defect(s) fixed and pushed. Please re-test the PR branch and report
> any remaining issues, or say **tests pass** to finalize.

## Step 7: Token Analysis

Record `PIPELINE_END` timestamp. Compute and display `TOKEN_SUMMARY`:

- Total tokens (input + output)
- Per-defect cost breakdown
- Model distribution

If this skill was invoked standalone (not within an orchestrate run), invoke the
`token-analysis` skill with the TOKEN_LEDGER data.

## Error Handling

| Condition | Action |
|-----------|--------|
| `gh` not installed | Print "Install GitHub CLI: brew install gh" and stop |
| Not authenticated | Print "Run: gh auth login" and stop |
| No PR found | Ask user for PR number |
| No defect reports on PR | Tell user, suggest template location, stop |
| Defect missing required fields | Skip, reply to comment with error, continue with others |
| Fix fails review twice | Escalate: report to user, continue with next defect |
| Fix introduces regression (test count drops) | Reject fix, report regression to user, continue with next defect |
| All fixes exhausted retries | Stop, report summary with escalated items |

## What This Skill Does NOT Do

- Does NOT run the full orchestrate pipeline (no planning, no architect step 1a/1b)
- Does NOT create new PRs — it fixes defects on an existing PR
- Does NOT close the PR or mark it as ready — that's the user's or orchestrate's job
- Does NOT modify defect comments — it only replies to them
- Does NOT re-run defects that have already been replied to with a fix commit
  (checks for existing "Fixed in commit" replies to skip already-processed defects)
