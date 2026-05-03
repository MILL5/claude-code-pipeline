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

### SendMessage availability

This skill relies on `SendMessage` for token-efficient agent continuation in Steps 1a,
1b, 2.1, and 3.5. It's gated behind `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.

**Enable** (add to `~/.claude/settings.json`, then restart Claude Code):
```json
{ "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" } }
```
Verify with `ToolSearch: select:SendMessage` — the schema should load.

**Addressing:** `SendMessage` must use the agent's **UUID** (the `agentId:` value in the
`Agent` tool's output), NOT the `name:` field. Named routing requires `TeamCreate` registration
and is not used by this skill. Capture `agentId` from the Agent return and reuse it for all
subsequent `SendMessage({ to: "<uuid>", ... })` calls. Calling `SendMessage` with the `name:`
will fail with `No agent named '...' is currently addressable`.

**Async semantics:** `SendMessage` is fire-and-notify. The call returns immediately; the
agent's reply arrives later as a `<task-notification>`. In clarification loops, wait for
the notification before proceeding.

**Fallback when unavailable:** If `ToolSearch: select:SendMessage` returns no matches, launch a
fresh `Agent` with prior context re-embedded for each continuation (~30–40% higher input cost).
Do not attempt `SendMessage` when the tool is unavailable.

### Do not call `ScheduleWakeup` during `/orchestrate`

`ScheduleWakeup` re-invokes `/orchestrate` (it's a `/loop` primitive). Wait for the agent's
`<task-notification>` instead. For external polling, use `Bash` with `run_in_background`.

## Step 0: Load Adapters

Before any agent launches, determine the active tech-stack adapters:

1. Read `.claude/pipeline.config` to get `stacks`, `pipeline_root`, `pipeline_mode`, `overlays`, `stack_paths.*`, and `capabilities` values
2. **Resolve `pipeline_root`:** If `pipeline_root` does not start with `/`, it is a relative path — resolve it against the project root (the directory containing `.claude/`). For example, if `pipeline_root=.claude/pipeline` and the project root is `/home/user/myapp`, the resolved path is `/home/user/myapp/.claude/pipeline`. All subsequent `<pipeline_root>` references in this skill use the **resolved** absolute path.
3. Parse the `stacks` value (comma-separated) into a list. The first stack is the **primary** (fallback).
   - **Backward compatibility:** If the config has `stack` (singular) instead of `stacks`, treat it as a single-element list.
3. Parse the `capabilities` value (comma-separated) into **ACTIVE_CAPABILITIES** — a set of capability
   strings (e.g., `azure-auth`). These are aggregated from adapter and overlay `manifest.json` files
   by `init.sh` and written to the config. Use these for conditional behavior instead of checking
   stack names. If `capabilities` is missing from the config, read each adapter's and overlay's
   `manifest.json` directly to build the set.
4. For each stack in the list, read `<pipeline_root>/adapters/<stack>/adapter.md` — this is that stack's **adapter config**
5. Build the **STACK_REGISTRY** — a mapping from stack name to its overlays:
   ```
   STACK_REGISTRY = {
     "<stack1>": { adapter: <adapter.md>, architect: <architect-overlay.md>, implementer: <implementer-overlay.md>, implementer_essential: <implementer-overlay-essential.md>, reviewer: <reviewer-overlay.md>, test: <test-overlay.md> },
     "<stack2>": { ... },
     ...
   }
   ```
6. Parse the `stack_paths.*` entries into a **STACK_PATHS** mapping:
   ```
   STACK_PATHS = {
     "<stack1>": ["glob1", "glob2", ...],
     "<stack2>": ["glob3", "glob4", ...],
   }
   ```

When composing agent prompts, insert the overlay content at the `<!-- ADAPTER:TECH_STACK_CONTEXT -->`
and `<!-- ADAPTER:CODE_QUALITY_RULES -->` markers in the agent's prompt. If you are pasting the
prompt directly (not relying on the agent definition), include the overlay content inline.

**Overlay injection strategy by agent role:**

| Agent Role | Which stacks' overlays to inject |
|------------|----------------------------------|
| Architect (1a, 1b) | **ALL stacks** — the architect must see the full system to design cross-stack interactions |
| Implementer (2, 2.2, 3.5) | **Task's stack only** — resolved from the task's file paths via STACK_PATHS |
| Reviewer (2.1, 3.5) | **Wave's active stacks** — union of stacks for all tasks in the current wave |
| Test architect | **Task's stack only** |

**Stack resolution algorithm** (used by implementer, reviewer, and bug-fix steps):

```
resolve_stack(file_path):
    for each stack in stacks (in config order):
        for each pattern in STACK_PATHS[stack]:
            if file_path matches pattern:
                return stack
    return stacks[0]  # fallback to primary stack
```

Each adapter config declares:
- **Build command**: `python3 .claude/scripts/<stack>/build.py`
- **Test command**: `python3 .claude/scripts/<stack>/test.py`
- **Blocked commands**: Raw commands that hooks prevent (for awareness)

## Step 0.1: Load Cross-Cutting Overlays

After loading adapters, check `pipeline.config` for the `overlays` key:

1. Read the `overlays` value (comma-separated). If empty or missing, skip this step.
2. For each overlay name (e.g., `azure-sdk`):
   - Read `<pipeline_root>/overlays/<overlay_name>/architect-overlay.md`
   - Read `<pipeline_root>/overlays/<overlay_name>/implementer-overlay.md`
   - Read `<pipeline_root>/overlays/<overlay_name>/implementer-overlay-essential.md`
   - Read `<pipeline_root>/overlays/<overlay_name>/reviewer-overlay.md`

3. When composing agent prompts, **append** the cross-cutting overlay content AFTER the
   stack adapter overlay(s) at the same `<!-- ADAPTER:TECH_STACK_CONTEXT -->` marker.
   Use this format:

   ```
   <stack adapter overlay content>

   ---
   ## Cross-Cutting: Azure SDK Context
   <overlay content>
   ```

4. For Haiku tasks in Step 2, append the overlay's `implementer-overlay-essential.md`
   after the adapter's essential variant. The combined essential content should remain concise
   to preserve signal-to-noise ratio for Haiku.

5. The overlay's reviewer content is appended after the adapter's reviewer overlay in Step 2.1,
   giving the code reviewer awareness of both stack-specific and Azure SDK patterns.

## Step 0.2: Load Local Overlays

After loading cross-cutting overlays, check for project-specific local overlays in `.claude/local/`:

1. Check if `.claude/local/` directory exists. If not, skip this step.
2. Read the following files (if they exist — each is optional):
   - `.claude/local/project-overlay.md` — injected into ALL agents
   - `.claude/local/coding-standards.md` — injected into implementer + reviewer agents
   - `.claude/local/architecture-rules.md` — injected into architect agent
   - `.claude/local/review-criteria.md` — injected into reviewer agent

3. For each file, **strip HTML comment blocks** (`<!-- ... -->`) and leading/trailing whitespace
   before storing. This removes template placeholder comments that would waste tokens.
   Build a **LOCAL_OVERLAYS** registry from the stripped content:
   ```
   LOCAL_OVERLAYS = {
     all: <project-overlay.md stripped content or empty>,
     implementer: <coding-standards.md stripped content or empty>,
     architect: <architecture-rules.md stripped content or empty>,
     reviewer: <review-criteria.md stripped content or empty>,
   }
   ```

4. When composing agent prompts, **append** local overlay content AFTER cross-cutting
   overlays at the same `<!-- ADAPTER:TECH_STACK_CONTEXT -->` marker. Use this format:

   ```
   <adapter overlay content>

   ---
   ## Cross-Cutting: <name> Context
   <cross-cutting overlay content>

   ---
   ## Project: Local Standards
   <project-overlay.md content>

   ---
   ## Project: Coding Standards
   <coding-standards.md content>
   ```

5. **Composition order by agent role:**

   | Agent Role | Local overlays injected |
   |------------|------------------------|
   | Architect (1a, 1b) | `project-overlay.md` + `architecture-rules.md` |
   | Implementer (2, 2.2, 3.5) | `project-overlay.md` + `coding-standards.md` |
   | Reviewer (2.1, 3.5) | `project-overlay.md` + `coding-standards.md` + `review-criteria.md` |
   | Test architect | `project-overlay.md` |

6. **For Haiku tasks:** Include local overlays at full content (not truncated). Local overlays
   are project-specific and team-curated, so they should be concise by nature. If a local
   overlay exceeds 500 characters, consider trimming — the pipeline does not enforce a size
   limit on local overlays, but bloated overlays degrade Haiku signal-to-noise ratio.

7. **If all local overlay files are empty after stripping:** Skip injection entirely — do not
   add empty `## Project:` headers. A file that contains only the template placeholder
   comments will be empty after stripping and is treated as absent.

## Step 0.3: Azure Authentication Pre-Flight

**When:** `ACTIVE_CAPABILITIES` includes `azure-auth` AND the pipeline will perform Azure-dependent
operations (what-if, deploy, drift-check, infra-test). Skip for local-only operations (build,
lint, scan, cost estimate). Runs lazily — only before the first Azure-dependent step.

**How:** Invoke the `azure-login` skill (verifies `az` CLI, `az account show`, displays
subscription/tenant/user/auth method, caches result as `AZURE_AUTH_STATUS`).

- **On failure:** pause, present skill's remediation guidance, ask user to `! az login` in the
  Claude Code prompt, retry after confirmation. Do NOT proceed with Azure-dependent steps.
- **On success:** record `AZURE_AUTH_STATUS = OK`, `AZURE_SUBSCRIPTION_ID`,
  `AZURE_SUBSCRIPTION_NAME`, `AZURE_TENANT_ID`, `AZURE_USER`, `AZURE_AUTH_METHOD`. Subsequent
  Azure-dependent skills check `AZURE_AUTH_STATUS` and skip re-validation if already OK.
  Re-validate if the target subscription or resource group changes mid-pipeline.

## Step 0.6: Initialize Token Tracking

Immediately after loading the adapter, initialize the `TOKEN_LEDGER` — an in-session list that
accumulates token usage data for every agent call throughout the pipeline. Also record
`PIPELINE_START` as the current timestamp.

**Ledger entry schema** (one entry per agent call):

| Field | Type | Description |
|-------|------|-------------|
| `step` | string | Pipeline step ID (e.g., `1a`, `1b`, `2:1.1`, `2.1:1.1`, `3.5:fix:bug1`) |
| `agent` | string | Agent type (`architect-agent`, `implementer-agent`, `code-reviewer-agent`, `orchestrator`) |
| `model` | string | Model used (`haiku`, `sonnet`, `opus`) |
| `input_chars` | number | Character count of the composed prompt sent to the agent |
| `output_chars` | number | Character count of the agent's complete response |
| `input_tokens` | number | `input_chars / 4` (approximate) |
| `output_tokens` | number | `output_chars / 4` (approximate) |
| `is_retry` | boolean | `true` if this is a review-fix cycle retry |
| `is_escalation` | boolean | `true` if the model was escalated (e.g., haiku → sonnet for fix) |
| `notes` | string | Context (e.g., `escalated from haiku`, `review-fix cycle 2`, `clarify round 3`) |
| `files_read` | list | Files the agent read from disk (from TOKEN_REPORT), with approximate sizes |
| `tool_calls` | map | Tool call counts from the agent's TOKEN_REPORT |

**How to record:** After every Agent launch or SendMessage call, measure prompt length as
`input_chars` and complete response as `output_chars` (tokens = chars / 4). Parse the agent's
`---TOKEN_REPORT---` block (compact 3-line format) for `files_read` and `tool_calls`. If the
TOKEN_REPORT is missing or malformed, leave those fields empty — do not fail. Append the
entry to `TOKEN_LEDGER`.

## Step 0.65: Initialize Backlog Integration State

Before Step 1a runs, bootstrap two artifacts in `.claude/tmp/` that the backlog
integration depends on:

1. **Run ID** — `.claude/tmp/run-id`: a timestamp-based identifier for this
   orchestrate run (`YYYYMMDD-HHMMSS`, e.g. `20260423-181500`). Generate at
   pipeline start. Every backlog issue filed during this run embeds this ID in
   its traceability block (D8).
2. **Run log** — `.claude/tmp/run-log.yml`: accumulates fold/defer decisions
   across phases. Initialize with an empty `backlog_decisions: []` array if the
   file does not already exist (a resumed run should preserve prior entries).

```bash
date +%Y%m%d-%H%M%S > .claude/tmp/run-id
test -f .claude/tmp/run-log.yml || printf 'backlog_decisions: []\n' > .claude/tmp/run-log.yml
```

**Backlog opt-in detection**: check for `.github/pipeline-backlog.yml` at the
project root. Set `BACKLOG_ENABLED=true|false` for downstream phases. Re-check
at the start of each filing call — `/bootstrap-backlog` can be run mid-session,
and subsequent phases should pick up the new sentinel without restart.

If `BACKLOG_ENABLED=false`, phases still emit fold/defer classifications into
`run-log.yml` (so the user sees what would have been filed), but no `gh issue
create` call is made. Emit exactly one hint on the first skipped filing:
`backlog integration not enabled for this repo — run /bootstrap-backlog to enable`.
Subsequent skips in the same run are silent.

## Step 0.7: Prepare ORCHESTRATOR.md Extracts

Read `.claude/ORCHESTRATOR.md` once at pipeline start. Instead of pasting the full file into
every agent prompt, extract only the sections each agent needs. Parse by `##` headers and
produce three scoped extracts:

**1a Extract** (for architect-analyzer — seam analysis, fragile area scan):
- `## Project Overview`
- `## Targets / Entry Points`
- `## Directory Structure`
- `## Architecture`
- `## Key Services / Modules`
- `## Known Fragile Areas`
- `## Current State`

**1b Extract** (for architect-planner — decomposition, brief writing):
- `## Data Flow`
- `## Conventions` (all subsections)
- `## Testing`
- `## Anti-Patterns (Do NOT)`

The 1b agent receives the 1a-spec which already contains Project Overview, Directory Structure,
Architecture, Key Services / Modules, Known Fragile Areas, and Current State — so those sections
are excluded from the 1b Extract to avoid duplication. Only sections NOT present in the 1a-spec
are included.

**3.5 Extract** (for blast-radius analysis — file correlation, fragile area check):
- `## Directory Structure`
- `## Key Services / Modules`
- `## Known Fragile Areas`

**Missing-header handling:** If an expected `##` header is not found in ORCHESTRATOR.md
(customized or partially populated), include only the headers that DID match plus a
one-line note appended to the extract: `> NOTE: ORCHESTRATOR.md was missing sections: <list>.
Treat as best-effort context.` Do NOT load the entire file as a fallback — that defeats the
extract budget and adds ~6.5K tokens per agent.

If ZERO expected headers match (the file is empty or completely customized), pause and ask
the user whether to proceed without codebase context or update ORCHESTRATOR.md first.

## Pipeline Overview

| Step | Agent / Skill | Model | Output |
|------|---------------|-------|--------|
| 1a | architect-agent (analyze + clarify, ≤3 rounds, feature-only Q&A) | Sonnet | `.claude/tmp/1a-spec.md` |
| 1b | architect-agent (impl Q&A ≤2 rounds, decompose, write plan) | Sonnet (Opus on novel arch) | `.claude/tmp/1b-plan.md` + `PLAN_WRITTEN` stub |
| 1.4 | orchestrator (pre-flight build per stack against base branch) | — | PASS or user-prompted (abort / continue / inject Wave 0) |
| 1.5 | open-pr skill | — | feature branch + draft PR |
| 2 | implementer-agent per task (parallel within wave, ≤4 per batch) | Haiku / Sonnet / Opus | SUCCESS + commit msg, or FAILURE |
| 2.1 | code-reviewer-agent (one per wave, reused via SendMessage, cap 4) | Sonnet | PASS or FAIL + issues |
| 2.2 | implementer-agent (same worktree, escalates Haiku→Sonnet on fix) | Sonnet | SUCCESS, or FAILURE after ≤2 cycles |
| 3 | orchestrator (commit verbatim per agent, push, record test baseline) | — | commits on PR branch |
| 3.4 | chrome-ui-test (conditional: `browser-ui` capability + UI files + MCP loadable) | Sonnet | PASS or routes FAIL into 3.5 cycle |
| 3.5 | orchestrator + agents (manual test loop, blast-radius on complex bugs) | Sonnet | bug fixes committed; loop until user says "tests pass" |
| 4 | orchestrator (update ORCHESTRATOR.md, finalize PR, mark ready) | — | PR ready for review |
| 5 | token-analysis skill (mandatory, runs in background concurrent with 4) | Sonnet | GitHub issue on pipeline repo if findings exist |

## Step Dispatch

The orchestrator runs the steps below in sequence. Every step is extracted to `skills/orchestrate/steps/<file>.md` — read each one just-in-time, immediately before executing that step.

| Step | File | Description |
|------|------|-------------|
| 1a | `steps/1a-clarify.md` | Analyze user request, surface clarifying Qs, write `1a-spec.md` |
| 1b | `steps/1b-plan.md` | Plan generation from `1a-spec.md` |
| 1.4 | `steps/1.4-preflight.md` | Pre-flight build verification |
| 1.5 | `steps/1.5-open-pr.md` | Open draft PR |
| 2 | `steps/2-implement.md` | Implement waves |
| 2.1 | `steps/2.1-review.md` | Code review (per-wave reused agent) |
| 2.2 | `steps/2.2-fix.md` | Fix issues from review |
| 3 | `steps/3-commit.md` | Commit + push per task |
| 3.4 | `steps/3.4-browser-ui.md` | Browser UI test (conditional) |
| 3.5 | `steps/3.5-manual-test.md` | Manual test loop with bug fixes |
| 4 | `steps/4-finalize.md` | Finalize PR |
| 5 | `steps/5-token-analysis.md` | Token analysis (background) |

**Protocol:** Before executing a step, read its file in full. The file's front-matter declares `step:`, `requires:` (`.claude/tmp/` artifacts that must exist), `produces:` (artifacts written), and `sendmessage:` (required/optional/n/a). If a `requires:` artifact is missing at runtime, halt with a clear error citing the artifact name and the step that produces it.

## Detailed Steps

### Step 1a: ANALYZE & CLARIFY

**Extracted to `steps/1a-clarify.md`.** Read that file before executing this step. Front-matter: `requires=[]`, `produces=[.claude/tmp/1a-spec.md]`, `sendmessage=required`.

### Step 1b: PLAN

**Extracted to `steps/1b-plan.md`.** Read that file before executing this step. Front-matter: `requires=[.claude/tmp/1a-spec.md]`, `produces=[.claude/tmp/1b-plan.md]`, `sendmessage=required`.

### Step 1.4: PRE-FLIGHT BUILD VERIFICATION

**Extracted to `steps/1.4-preflight.md`.** Read that file before executing this step. Front-matter: `requires=[.claude/tmp/1b-plan.md]`, `produces=[]`, `sendmessage=n/a`.

### Step 1.5: OPEN PR

**Extracted to `steps/1.5-open-pr.md`.** Read that file before executing this step. Front-matter: `requires=[]`, `produces=[]`, `sendmessage=n/a`.

### Step 2: IMPLEMENT

**Extracted to `steps/2-implement.md`.** Read that file before executing this step. Front-matter: `requires=[]`, `produces=[]`, `sendmessage=n/a`.

### Step 2.1: REVIEW

**Extracted to `steps/2.1-review.md`.** Read that file before executing this step. Front-matter: `requires=[.claude/tmp/1b-plan.md]`, `produces=[]`, `sendmessage=required`.

### Step 2.2: FIX

**Extracted to `steps/2.2-fix.md`.** Read that file before executing this step. Front-matter: `requires=[]`, `produces=[]`, `sendmessage=optional`.

### Step 3: COMMIT + PUSH

**Extracted to `steps/3-commit.md`.** Read that file before executing this step. Front-matter: `requires=[]`, `produces=[]`, `sendmessage=n/a`.

### Step 3.4: AUTOMATED BROWSER UI TEST (conditional)

**Extracted to `steps/3.4-browser-ui.md`.** Read that file before executing this step. Front-matter: `requires=[]`, `produces=[]`, `sendmessage=n/a`.

### Step 3.5: MANUAL TEST

**Extracted to `steps/3.5-manual-test.md`.** Read that file before executing this step. Front-matter: `requires=[.claude/tmp/1b-plan.md]`, `produces=[]`, `sendmessage=required`.

### Step 4: FINALIZE

**Extracted to `steps/4-finalize.md`.** Read that file before executing this step. Front-matter: `requires=[.claude/tmp/run-log.yml]`, `produces=[]`, `sendmessage=n/a`.

### Step 5: TOKEN ANALYSIS (mandatory)

**Extracted to `steps/5-token-analysis.md`.** Read that file before executing this step. Front-matter: `requires=[.claude/tmp/1b-plan.md]`, `produces=[]`, `sendmessage=n/a`.

## Backlog Integration

When `/orchestrate` runs in a repo opted in via `.github/pipeline-backlog.yml`,
out-of-scope items surfaced by the planner and reviewer are classified as
**fold** (spawn a new implementer task in this run) or **defer** (file a GitHub
issue via `scripts/backlog_file.py`). This closes the durable-capture gap —
items like "extract this common helper" or "this file has a stale comment"
stop evaporating between runs.

### Fold vs. Defer Decision Rule

Use the planner's existing Haiku/Sonnet classification rubric
(`architect-planner/SKILL.md` Step 5 "Assign Models") as the boundary:

- **Haiku-tier** — mechanical, <150 lines, single-file, fully-specified → **fold**.
- **Sonnet/Opus-tier** — design decisions, multi-file, moderate-to-high reasoning
  → **defer** (file to backlog).

Reviewer guidance:
- `[should-fix]` entries with Haiku-tier fix:
  - **Trivial patches (≤5 LOC AND single-file): default-defer.** A fold cycle costs
    ~$0.30 in implementer tokens; trivial patches are cheaper for the user to capture
    as a follow-up commit than to spawn a fold. Surface the deferred entry at PR
    finalization so the user can choose to fold before merge.
  - **Non-trivial patches: fold.** Deferring substantial should-fix items pushes
    context-rebuilding cost onto a future PR.
- `[nice-to-have]` entries default-defer regardless of tier.
- `[simplify]` entries are fold candidates by definition (Haiku-tier,
  single-file, behavior-preserving). The reviewer self-attests behavior
  preservation; the **build + test gate is the enforcement**. Two safety
  guards apply:
  1. **Haiku-reviewer guard:** if the reviewer that emitted the entry was
     Haiku (micro-plan reviewer per the M3 cost-proportional rule), force
     the entry to **defer** instead of fold. Haiku judgment on behavior
     preservation is not yet trusted enough to auto-apply in-run.
  2. **Abandon-on-failure:** when the spawned simplify implementer
     returns `FAILURE` (build or test failed), do **NOT** enter the
     standard Step 2.2 fix loop. Discard the simplify worktree, log
     `action: simplify_abandoned` with reasoning `"tests/build failed —
     original code retained"`, and continue. The premise of `[simplify]`
     is behavior preservation; if tests fail, the rewrite is wrong, and
     the original code is correct by construction.

`[simplify]` empty-diff path: if the implementer cannot find a
behavior-preserving rewrite, it returns `SUCCESS` with no diff and a
one-line note. Skip the empty commit and log
`action: simplify_no_change`.

### Run-Level Fold Cap

Read `fold_cap` from `.github/pipeline-backlog.yml` (default 3, `0` = never
fold). Before folding a new item, count entries in `.claude/tmp/run-log.yml`
where `action: folded`. If that count is already at the cap, treat this item
as **defer** regardless of its tier.

Fold cap applies across ALL phases combined — not per-phase. This prevents
reviewer and planner from collectively turning into a second round of
implementation work.

### Filing a Deferred Item

Use the shared utility (do not shell out to `gh` directly):

```bash
python3 .claude/pipeline/scripts/backlog_file.py \
  --title "<short imperative title>" --type chore --priority p2 \
  --body-context-json '{"phase": "<reviewer|planner|implementer>", "pr_number": "'"$PR_NUMBER"'",
    "run_id": "'"$(cat .claude/tmp/run-id)"'", "reasoning": "<why defer not fold>",
    "summary": "<one-line>", "context": "<multi-line context>"}'
```

Parse the utility's JSON output and append to `backlog_decisions`:
- `{"status": "filed", "url": ..., "number": N}` → `action: deferred`, record `issue_url`.
- `{"status": "skipped", "reason": ...}` → `action: skipped`; emit the one-time hint on first
  skip of the run.
- `{"status": "failed", "reason": ...}` → `action: failed`, `issue_url: null`, log warning,
  continue the run.

### Folding an Item (spawn new implementer task)

Add the item to the next available wave as a new Haiku task with a fresh brief
that satisfies all 6 contract points (see `agents/implementer-contract.md`).
Append a `backlog_decisions` entry with `action: folded` and a one-line
reasoning. Count this entry against the fold cap.

**Token tracking for folds:** When recording the implementer and reviewer entries for a
folded task, set `notes: "fold:<source-phase>:<short-title>"` (e.g.
`fold:reviewer:Extract validation helper`). The token-analysis skill aggregates entries
where `notes` starts with `fold:` into a separate "Fold cost" line in the cost breakdown,
so users can see fold spend independently of the planned wave cost.

### Run-Log Schema

`.claude/tmp/run-log.yml` accumulates decisions across phases:

```yaml
backlog_decisions:
  - phase: reviewer              # planner | reviewer | implementer | token-analysis
    title: "Extract common Grok error mapper"
    classification: sonnet       # haiku | sonnet | opus | trivial
    action: deferred             # folded | deferred | skipped | failed | simplify_abandoned | simplify_no_change
    issue_url: "https://github.com/.../issues/42"   # present when action=deferred
    issue_number: 42
    reasoning: "Cross-cuts 4 files, adds new abstraction — Sonnet-tier"
  - phase: implementer
    title: "Typo in error message at src/tools/grok_client.py:42"
    classification: trivial
    action: folded
    reasoning: "<5 LOC mechanical fix in file already being edited"
```

### PR Description — Folded Checklist

At Step 4 (Finalize), when `BACKLOG_ENABLED=true`, read `run-log.yml` and
render a "Folded in this run" checklist into the PR body before marking it
ready for review:

```markdown
## Folded in this run
- [x] Extracted common validation helper (implementer, wave 2) — <commit SHA>
- [x] Fixed typo in error message at src/tools/grok_client.py (implementer, wave 1) — inline
```

Deferred items are NOT listed in the PR body — they have their own GitHub
issues (linked via traceability block, which auto-backlinks to the originating
PR). If no folds occurred, omit the section entirely.

### Phase Integration Summary

- **Step 1b (planner)**: planner outputs a `Deferred Items` section. Orchestrator
  iterates each, classifies, folds or files per the rule above.
- **Step 2.1 (reviewer)**: each `[should-fix]` / `[nice-to-have]` /
  `[simplify]` entry in OPTIONAL IMPROVEMENTS is classified. Orchestrator
  folds or files. `[simplify]` entries from a Haiku reviewer always defer
  (option B safety guard); folded `[simplify]` tasks abandon on test
  failure rather than entering the fix loop.
- **Step 2 (implementer)**: implementer's SUCCESS commit message may include a
  "Follow-up" suggestion line — surface to reviewer, who classifies it with the
  rest.
- **Step 5 (token-analysis)**: token-analysis findings always defer (per spec).
  The skill itself invokes `scripts/backlog_file.py`; orchestrator records the
  outcome in `run-log.yml`.

## Parallelization Rules

- **Within a wave:** launch all implementer agents simultaneously (parallel)
- **Across waves:** sequential — wait for all agents in wave N before starting wave N+1
- **Review agents:** one reviewer per wave, reused via SendMessage (sequential within wave, max 8 per agent)
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
| Token analysis skill fails | Log warning, report to user, do not block pipeline completion |
| Pre-flight build (Step 1.4) FAIL | Pause, present build errors, ask user: abort / continue anyway / inject Wave 0 fix |
| Pre-flight build script times out | Treat as FAIL with `build script timed out` note; fall through to user prompt |
| Pre-flight build output unrecognized | Treat as FAIL with `unrecognized build output — check adapter contract` note |
| chrome-ui-test FAIL | Route into Step 3.5.1-3.5.5 bug-fix cycle using its reproduction recipe as the bug report |
| chrome-ui-test FAIL twice on same scenario after fix | Stop Step 3.4 retries, present findings, hand to user manual test |
| claude-in-chrome MCP tools not loadable | Skip Step 3.4 silently — user has not authorized chrome for this session |
| `gh issue create` fails (missing label, auth, etc.) | Retry without `--label`, report failure if still errors |
| Pipeline repo has no GitHub remote | Skip issue filing, report token summary to user directly |
| Backlog sentinel absent | Phase classifications still recorded in run-log; no `gh` calls; emit one-line hint on first skip |
| Backlog filing returns `failed` | Record `action: failed` in run-log with reason; continue pipeline |
| Fold cap reached mid-run | Treat subsequent fold candidates as deferrals regardless of tier |

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

### Resume dispatch matrix (artifact-driven)

The orchestrator dispatches to a step based on which `.claude/tmp/` artifacts exist on resume. Cases are evaluated top to bottom; first match wins.

| State | Action |
|-------|--------|
| Only `1a-spec.md` present | Resume from Step 1b (use existing spec). |
| `1a-spec.md` AND `1b-plan.md` present | Resume from Step 1.4 (pre-flight build); plan is authoritative. |
| Only `1b-plan.md` present (no `1a-spec.md`) | **Illegal state** — fail loudly. The plan was written without a spec; treat as corrupt. Tell the user: "Recovery artifact `1b-plan.md` exists without `1a-spec.md`. This should not happen. Delete `.claude/tmp/1b-plan.md` and rerun, or restore `1a-spec.md` from your last `/orchestrate` run." Do not proceed. |
| Neither present | Start fresh from Step 1a. |

If both `1a-spec.md` and `1b-plan.md` are present and the user wants to discard one, instruct them to delete the relevant file in `.claude/tmp/` before rerunning `/orchestrate`. The orchestrator never deletes recovery artifacts on its own.
