---
name: orchestrate
description: >
  Full-lifecycle orchestration for feature implementation and bug fixes.
  Coordinates: architect (plan) -> implementer (code + tests) -> code-reviewer (review) -> implementer (fix) -> commit.
  Use when the user says "build", "implement", "add feature", "fix bug", or any request
  that requires planned, reviewed, tested code changes. Also triggers on "orchestrate",
  "/orchestrate", or "run the pipeline".
---

# Orchestration Skill

You are the orchestrator. You do NOT implement code yourself. You coordinate specialized agents
through a disciplined pipeline that guarantees every change is planned, implemented, reviewed,
tested to >=90% coverage, and committed with a clean conventional-commit message.

## Prerequisites

Before starting, read these files (skip if already in context from this session):
1. `.claude/ORCHESTRATOR.md` — architecture, conventions, fragile areas
2. `.claude/CLAUDE.md` — project rules (file limits, mandatory skills, etc.)

## Step 0: Load Adapter

Before any agent launches, determine the active tech-stack adapter:

1. Read `.claude/pipeline.config` to get the `stack` and `pipeline_root` values
2. Read `<pipeline_root>/adapters/<stack>/adapter.md` — this is the **adapter config**
3. For each agent you launch, read the relevant overlay file from `<pipeline_root>/adapters/<stack>/`:
   - `architect-overlay.md` — injected into architect-agent prompts
   - `implementer-overlay.md` — injected into implementer-agent prompts
   - `reviewer-overlay.md` — injected into code-reviewer-agent prompts
   - `test-overlay.md` — injected into test-architect-agent prompts

When composing agent prompts, insert the overlay content at the `<!-- ADAPTER:TECH_STACK_CONTEXT -->`
and `<!-- ADAPTER:CODE_QUALITY_RULES -->` markers in the agent's prompt. If you are pasting the
prompt directly (not relying on the agent definition), include the overlay content inline.

The adapter config also declares:
- **Build command**: The command agents should use to build (e.g., `python3 .claude/scripts/build.py`)
- **Test command**: The command agents should use to test (e.g., `python3 .claude/scripts/test.py`)
- **Blocked commands**: Raw commands that hooks prevent (for awareness)

## Pipeline Overview

```
User Request
    |
    v
Step 1a: ANALYZE & CLARIFY (architect-agent, Sonnet, interactive)
    |  Pre-flight check -> seam analysis -> clarifying questions (iterative)
    |  Writes: .claude/tmp/1a-spec.md (enriched spec + recovery artifact)
    v
Step 1b: PLAN (architect-agent, Opus, fresh agent)
    |  Reads: 1a-spec.md + full ORCHESTRATOR.md (clean context, ~15K tokens)
    |  Produces: ordered task list with context briefs
    |  Present to user for confirmation
    v
Step 1.5: OPEN PR (open-pr skill)
    |  Create feature branch from main, push, open draft PR
    |  All subsequent work happens on this branch
    v
Step 2: IMPLEMENT (implementer-agent agents, parallel where possible)
    |  Each agent: implement -> self-review -> build -> test (>=90% coverage)
    |  Returns: SUCCESS + commit message  OR  FAILURE + error report
    |
    v  (for each successful agent)
Step 2.1: REVIEW (code-reviewer-agent, Sonnet)
    |  Returns: PASS  OR  FAIL + issues list
    |
    v  (if FAIL)
Step 2.2: FIX (implementer-agent, same worktree)
    |  Fix code-reviewer findings, re-build, re-test
    |  Returns: SUCCESS + updated commit message  OR  FAILURE + error report
    |
    v  (repeat 2.1 -> 2.2 max 2 times, then escalate to user)
Step 3: COMMIT + PUSH (orchestrator commits per agent, pushes to PR branch)
    |  Uses the SUCCESS message verbatim as the git commit message
    |  Record test baseline (total passing count) after all waves complete
    v
Step 3.5: MANUAL TEST (user tests PR branch)
    |  User reports bugs OR says "tests pass"
    |  Each bug: assess blast radius -> fix (Sonnet) -> review -> full test suite -> commit
    |  Regression guard: test count must not decrease from baseline
    |  Escalation: 2 failed fixes OR test count drop -> architect blast-radius analysis
    |  Loop until user says "tests pass"
    v
Step 4: FINALIZE (update .claude/ORCHESTRATOR.md, update PR, mark ready for review)
```

## Detailed Steps

### Step 1a: ANALYZE & CLARIFY

**Pre-flight check (orchestrator, before launching the 1a agent):**

1. Run `git status` — if the working tree is dirty, warn the user before proceeding.
2. Run `git branch --show-current` — confirm you are on the expected branch.
3. Check ORCHESTRATOR.md "Current State" — note the last known build/test status and date. If the last recorded status is older than the most recent commit, recommend the user run a build/test pass before planning.
4. Check whether `.claude/tmp/1a-spec.md` already exists. If it does, ask the user: "A previous 1a analysis exists — resume from it or start fresh?"

**Launch the architect-agent in 1a mode:**

```
Agent: architect-agent
Model: sonnet
Prompt: |
  MODE: 1a — Analysis & Clarification

  Read `.claude/skills/architect-analyzer/SKILL.md` for your instructions.
  Do NOT enter plan mode — you will need to write the enriched spec file.

  TECH STACK CONTEXT:
  <paste contents of adapter's architect-overlay.md>

  USER REQUEST:
  "<user's request verbatim>"

  CODEBASE CONTEXT (ORCHESTRATOR.md — already included, do not re-read from disk):
  <paste full contents of .claude/ORCHESTRATOR.md>
```

**Clarification loop:**
- The 1a agent will output a structured analysis followed by grouped clarifying questions.
- Present the questions to the user verbatim.
- Feed user answers back via **SendMessage** to the same agent (do NOT launch a new agent).
- Repeat until either:
  - The agent outputs `CLARIFICATION COMPLETE` and writes `.claude/tmp/1a-spec.md`, or
  - The user explicitly says "proceed" or "good enough"
- If the user says proceed before the agent signals complete, instruct the agent via SendMessage to finalize the spec with the information gathered so far.

**Recovery:** If the pipeline is interrupted after 1a and `.claude/tmp/1a-spec.md` exists, skip 1a entirely and go directly to 1b. If `.claude/tmp/1b-plan.md` also exists, skip both 1a and 1b — present the saved plan to the user for confirmation and proceed to Step 1.5.

---

### Step 1b: PLAN

Launch a **fresh** architect-agent in 1b mode. Do NOT use SendMessage from the 1a agent — start a new agent so 1b has a clean context window (~15K tokens of focused signal vs. the full 1a Q&A history).

```
Agent: architect-agent
Model: opus
Prompt: |
  MODE: 1b — Plan Generation

  Read `.claude/skills/architect-planner/SKILL.md` for your instructions.

  TECH STACK CONTEXT:
  <paste contents of adapter's architect-overlay.md>

  ENRICHED SPEC:
  <paste full contents of .claude/tmp/1a-spec.md>

  CODEBASE CONTEXT (ORCHESTRATOR.md — already included, do not re-read from disk):
  <paste full contents of .claude/ORCHESTRATOR.md>
```

**Architecture decision questions:** The 1b agent may pause once to surface implementation
tradeoffs where both approaches are valid and the choice affects the plan structure (see
Step 2.5 in the planner skill). If this happens, present the questions to the user and
feed answers back via **SendMessage**. This is limited to ONE round — after receiving
answers, the agent completes the plan.

**Wait for the plan.** Review it for:
- Does it respect the file-per-task limits from CLAUDE.md?
- Are waves and dependencies sensible?
- Are context briefs self-contained and free of "see task X" cross-references?

Present the plan summary to the user and wait for confirmation before proceeding.

**Plan revisions:** If the user requests changes, use **SendMessage** to the 1b agent (do NOT launch a new agent — the architect must remember its own plan). Iterate until confirmed.

### Step 1.5: OPEN PR

Once the user confirms the plan, follow the `open-pr` skill (`.claude/skills/open-pr/SKILL.md`)
to create a feature branch and draft PR **before any implementation begins**.

Provide to the skill:
- **Feature summary** from the plan overview
- **Plan overview** with waves, task list, and key decisions
- **Plan type** (feat, fix, refactor, chore, perf)

Record `PR_BRANCH`, `PR_NUMBER`, `PR_URL` for use in later steps.
All subsequent commits and pushes target this branch.

### Step 2: IMPLEMENT

For each wave in the plan, launch implementer agents. **Tasks within a wave run in parallel.**
Tasks across waves are sequential (wave N+1 waits for wave N to complete).

For each task in the current wave:

```
Agent: implementer-agent
Model: <model from plan — haiku, sonnet, or opus>
Isolation: worktree (if multiple parallel agents in same wave touch different files)
Prompt: |
  You are being launched by the orchestration pipeline.
  Follow all rules from your agent definition (output protocol, build/test
  commands, coverage gate, self-review). No deviations.

  TECH STACK RULES:
  <paste contents of adapter's implementer-overlay.md>

  TASK CONTEXT BRIEF:

  <paste the context brief from the architect's plan here>
```

**After each implementer returns:**

- If `SUCCESS`: proceed to Step 2.1 (review)
- If `FAILURE`: report the failure details to the user. Do NOT auto-retry implementation failures — these need human judgment.

### Step 2.1: REVIEW

For each successful implementer, launch the code-reviewer to review:

```
Agent: code-reviewer-agent
Model: sonnet
Prompt: |
  You are being launched by the orchestration pipeline.
  Use your Pipeline Mode output protocol (PASS/FAIL).

  TECH STACK REVIEW RULES:
  <paste contents of adapter's reviewer-overlay.md>

  REVIEW THESE CHANGES:

  <list the files the implementer created/modified>
```

**After review returns:**

- If `PASS`: proceed to Step 3 (commit)
- If `FAIL`: proceed to Step 2.2 (fix)

### Step 2.2: FIX

Send the code-reviewer's FAIL output back to the implementer to fix:

```
Agent: implementer-agent (continue the same agent if possible, otherwise new with same worktree)
Model: sonnet (escalate from haiku — fixes require more judgment)
Prompt: |
  The code-reviewer found issues in your implementation. Fix ALL issues below,
  then re-build and re-test (coverage must remain >=90%).
  Follow your standard output protocol (SUCCESS/FAILURE).

  TECH STACK RULES:
  <paste contents of adapter's implementer-overlay.md>

  CODE REVIEW FINDINGS TO FIX:

  <paste the FAIL output from code-reviewer>

  FILES YOU PREVIOUSLY MODIFIED:

  <list of files>
```

**After fix returns:**
- If `SUCCESS`: proceed to Step 3 (commit). The fix agent's self-review + build + test
  is sufficient — do NOT re-review. Skip the review-fix cycle.
- If `FAILURE`: report to user with full context.

### Step 3: COMMIT + PUSH

For each agent that completed successfully (after passing review):

1. Stage the agent's modified files: `git add <files>`
2. Commit using the agent's SUCCESS message verbatim (everything after the `SUCCESS\n\n` header)
3. Do NOT modify the commit message — use it exactly as returned
4. Push to the PR branch: `git push`

If multiple agents completed in the same wave, commit them in task order (1.1 before 1.2, etc.).

```bash
git add <files from agent>
git commit -m "<SUCCESS message from agent>"
git push
```

Pushing after each commit keeps the draft PR up to date so progress is visible.

**Record test baseline:** After committing all waves, run the full test suite and record
the total passing test count. This is the regression baseline for Step 3.5.

### Step 3.5: MANUAL TEST

After all implementation is committed and pushed, prompt the user to test the PR branch:

> "All tasks implemented and pushed to `PR_BRANCH`. Please test the branch and report
> any bugs found, or say **tests pass** to finalize the PR."

**If the user says "tests pass":** proceed to Step 4.

**For each bug reported, run this cycle:**

#### 3.5.1: ASSESS

The orchestrator assesses each bug — do NOT delegate this to a subagent:

1. **Correlate** the bug to the task(s) and file(s) from the plan.
2. **Check fragile areas:** Cross-reference affected files against ORCHESTRATOR.md's
   "Known Fragile Areas". If the bug touches a fragile area, note the specific concern.
3. **Classify the fix:**
   - **Simple** (single file, clear cause, no fragile areas): proceed directly to 3.5.2.
   - **Complex** (crosses task boundaries, touches fragile areas, or cause is unclear):
     launch a Sonnet architect-agent for blast-radius analysis before fixing.

**Blast-radius analysis prompt (complex bugs only):**

```
Agent: architect-agent
Model: sonnet
Prompt: |
  MODE: blast-radius analysis

  Read `.claude/skills/architect-analyzer/SKILL.md` for your analysis approach.
  Do NOT enter plan mode — you may need to read code files.

  TECH STACK CONTEXT:
  <paste contents of adapter's architect-overlay.md>

  A bug was found during manual testing of a feature implementation. Assess the
  blast radius of fixing this bug and recommend a fix approach.

  BUG REPORT:
  "<user's bug report verbatim>"

  FILES MODIFIED BY THE IMPLEMENTATION:
  <list all files modified across all tasks>

  ORIGINAL PLAN SUMMARY:
  <paste the plan overview — waves and task names, not full briefs>

  CODEBASE CONTEXT (ORCHESTRATOR.md — already included, do not re-read from disk):
  <paste full contents of .claude/ORCHESTRATOR.md>

  Respond with:
  1. ROOT CAUSE: Which file(s) and task(s) likely caused this
  2. BLAST RADIUS: What other files/behaviors could be affected by a fix
  3. FRAGILE AREAS: Any Known Fragile Areas in the blast radius
  4. FIX APPROACH: Specific fix strategy (1-3 sentences)
  5. FILES TO MODIFY: Exact list
  6. REGRESSION RISK: Low/Medium/High with explanation
```

#### 3.5.2: FIX

Launch an implementer agent to fix the bug:

```
Agent: implementer-agent
Model: sonnet
Prompt: |
  You are being launched by the orchestration pipeline to fix a bug found
  during manual testing. Follow all rules from your agent definition.

  IMPORTANT: After fixing, run the FULL test suite (all targets), not just
  the modified files. The total passing test count must be >= BASELINE_COUNT.
  If it drops, your fix introduced a regression — find and fix it before
  returning SUCCESS.

  Test baseline: BASELINE_COUNT passing tests.

  TECH STACK RULES:
  <paste contents of adapter's implementer-overlay.md>

  BUG REPORT:
  "<user's bug report>"

  FIX APPROACH:
  <if complex: paste architect's fix approach from 3.5.1>
  <if simple: orchestrator's own assessment>

  FILES TO MODIFY:
  <file list>

  ORIGINAL CONTEXT BRIEF (for reference):
  <paste the original context brief for the affected task>
```

#### 3.5.3: REVIEW

```
Agent: code-reviewer-agent
Model: sonnet
Prompt: |
  You are being launched by the orchestration pipeline.
  Use your Pipeline Mode output protocol (PASS/FAIL).

  TECH STACK REVIEW RULES:
  <paste contents of adapter's reviewer-overlay.md>

  This is a BUG FIX review. In addition to your standard checks, explicitly verify:
  - The fix does not revert or contradict the original implementation's intent
  - The fix does not introduce regressions in adjacent functionality
  - The test count has not decreased from the baseline

  REVIEW THESE CHANGES:

  <list the files the fix agent modified>
```

#### 3.5.4: COMMIT + PUSH

Same as Step 3, but commit messages use `fix(scope):` type prefix.

#### 3.5.5: RE-TEST

Prompt the user to re-test:

> "Bug fix committed and pushed. Please re-test and report any remaining issues,
> or say **tests pass** to finalize."

**Regression guards:**
- If the fix agent's test run shows the total passing count dropped below `BASELINE_COUNT`,
  the fix MUST be rejected — report to user, do not commit.
- If a fix fails review (Step 3.5.3) twice, stop and launch the architect for
  blast-radius analysis (if not already done), then present the analysis to the user.
- Maximum 3 bug-fix cycles per manual test round. After that, stop and report all
  outstanding issues to the user for manual triage.
- `BASELINE_COUNT` is updated after each successful fix commit (ratchets up, never down).

### Step 4: FINALIZE

After all tasks are committed and pushed:

1. If the changes affected architecture (new services, new targets, new patterns):
   - Update `ORCHESTRATOR.md` with the changes
   - Commit and push the update
2. Update the PR body's Coverage section with final numbers from the last test run
3. Check off completed tasks in the PR body's task list
4. Mark the PR as ready for review:
   ```bash
   gh pr ready <PR_NUMBER>
   ```
5. Report final status to user:
   - PR URL
   - Number of tasks completed
   - Number of commits made
   - Coverage summary from the last test run
   - Any review findings that were fixed

The orchestrator does NOT merge — the user decides when to merge.

## Parallelization Rules

- **Within a wave:** launch all implementer agents simultaneously (parallel)
- **Across waves:** sequential — wait for all agents in wave N before starting wave N+1
- **Review agents:** can run in parallel for different implementers in the same wave
- **Fix agents:** sequential per implementer (fix, then re-review, then next cycle)

## Error Handling

| Scenario | Action |
|----------|--------|
| Architect returns unclear plan | Ask user for clarification before proceeding |
| Implementer returns FAILURE | Report to user with details, do not retry |
| Code-reviewer returns FAIL | Send to implementer for fix (max 2 cycles) |
| Fix agent returns FAILURE | Report to user with full context |
| 3rd review-fix cycle still FAIL | Stop, report all issues to user |
| Coverage < 90% after 3 attempts | Report as FAILURE with coverage details |
| Agent timeout / crash | Report to user, suggest manual retry |
| Bug fix drops test count below baseline | Reject fix, report regression to user |
| Bug fix fails review twice | Launch architect blast-radius analysis, present to user |
| 3+ bug-fix cycles in one manual test round | Stop, report all outstanding issues for manual triage |

## What the Orchestrator Does NOT Do

- **Does not write code.** Ever. That's the implementer's job.
- **Does not make architectural decisions.** That's the architect's job.
- **Does not review code.** That's the code-reviewer's job.
- **Does not modify commit messages.** Uses them verbatim from the implementer.
- **Does not merge PRs.** The user decides when to merge.
- **Does not skip steps.** Every change goes through the full pipeline.

## Resuming After Interruption

If the session is interrupted mid-pipeline:
1. Check `git status` and `git log --oneline -5` to see what was committed
2. Check `gh pr list --author @me` to find the open draft PR
3. Check out the PR branch: `git checkout <branch>`
4. Read `.claude/ORCHESTRATOR.md` for the latest state
5. The architect's plan (if saved) shows which tasks remain
6. Resume from the first incomplete task in the plan
7. Unchecked items in the PR body show remaining work
