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
  <paste each STACK_REGISTRY stack's architect-overlay.md under "## <Stack> Architecture Context";
   append cross-cutting overlays under "## Cross-Cutting: <name> Context";
   append local overlays for the architect role per Step 0.2 matrix (skip empty)>

  STACK MAPPING (for awareness during analysis):
  <for each stack, list its stack_paths patterns, e.g.:
   - react: src/frontend/**
   - python: src/backend/**
   - bicep: infra/**>

  USER REQUEST:
  "<user's request verbatim>"

  CODEBASE CONTEXT (ORCHESTRATOR.md 1a extract — do not re-read from disk):
  <paste 1a Extract from Step 0.7>
```

**Clarification loop:**
- The 1a agent will output a structured analysis followed by grouped clarifying questions.
- Present the questions to the user verbatim.
- Feed user answers back via **SendMessage** to the same agent (do NOT launch a new agent).
- Repeat until either:
  - The agent outputs `CLARIFICATION COMPLETE` and writes `.claude/tmp/1a-spec.md`, or
  - The user explicitly says "proceed" or "good enough"
- If the user says proceed before the agent signals complete, instruct the agent via SendMessage to finalize the spec with the information gathered so far.

**Round cap (cost guardrail):** Soft-cap at **2 SendMessage rounds** beyond the initial
launch. Before sending a 3rd round, check whether the new questions are sub-questions on
topics already asked (vs. introducing new decision points). If they are sub-questions,
prompt the user: "The architect has follow-up questions on topics already covered — proceed
with current understanding or continue clarifying? (proceed | continue)". Respect the
user's choice. If new topics, allow the round but cap cumulative 1a tokens at ~150K total
(input + output across all 1a entries in `TOKEN_LEDGER`). On hitting the token cap,
SendMessage `FINALIZE NOW` and force the agent to write the spec with current information.

**Token tracking:** Per Step 0.6 — record one entry for the initial launch (step `1a`) and one per clarification SendMessage (step `1a:clarify-N`). agent=`architect-agent`, model=`sonnet`.

**TOKEN_LEDGER gate:** After Step 1a completes and `.claude/tmp/1a-spec.md` is written,
verify that `TOKEN_LEDGER` contains at least one entry. If the ledger is empty, warn the user:

> ⚠ TOKEN_LEDGER is empty after Step 1a — token tracking was skipped. Step 5 analysis
> will reconstruct from `<usage>` blocks with reduced accuracy.

Do NOT abort the pipeline. Continue with implementation but note the tracking gap.

**Recovery:** If the pipeline is interrupted after 1a and `.claude/tmp/1a-spec.md` exists, skip 1a entirely and go directly to 1b. If `.claude/tmp/1b-plan.md` also exists, skip both 1a and 1b — present the saved plan to the user for confirmation and proceed to Step 1.5.

---

### Step 1b: PLAN

Launch a **fresh** architect-agent in 1b mode. Do NOT use SendMessage from the 1a agent — start a new agent so 1b has a clean context window (~15K tokens of focused signal vs. the full 1a Q&A history).

**Model selection:** Default to **Sonnet**. Escalate to **Opus** only when the 1a-spec indicates
at least one of:
- Novel architecture with no existing patterns in the codebase to follow
- Cross-cutting changes affecting 3+ services/modules with shared state
- Concurrent/async coordination requiring holistic correctness reasoning
- Security-critical design where subtle errors have severe consequences

If plan quality is poor on Sonnet (vague briefs, missed dependencies), the user can request a
re-plan with Opus.

```
Agent: architect-agent
Model: <sonnet (default) or opus (if escalation criteria above are met)>
Prompt: |
  MODE: 1b — Plan Generation

  Read `.claude/skills/architect-planner/SKILL.md` for your instructions.

  TECH STACK CONTEXT:
  <paste each STACK_REGISTRY stack's architect-overlay.md under "## <Stack> Architecture Context";
   append cross-cutting overlays under "## Cross-Cutting: <name> Context";
   append local overlays for the architect role per Step 0.2 matrix (skip empty)>

  STACK MAPPING (for task assignment — assign each task a stack based on its files):
  <for each stack, list its stack_paths patterns, e.g.:
   - react: src/frontend/**
   - python: src/backend/**
   - bicep: infra/**>

  ENRICHED SPEC:
  <paste full contents of .claude/tmp/1a-spec.md>

  EFFICIENCY CONSTRAINT: The 1a-spec was produced by reading the files in its
  "Files & Services In Scope" section. Use the spec's extracts — do NOT re-read
  those files end-to-end. If you need additional context, read only the specific
  line ranges you need.

  CODEBASE CONTEXT (ORCHESTRATOR.md 1b extract — do not re-read from disk):
  <paste 1b Extract from Step 0.7>
```

Note: The 1a-spec already contains project overview, directory structure, fragile areas, and
current state — the 1b extract omits these to avoid duplication.

**Implementation clarification loop:**
The 1b agent will first analyze the enriched spec against the codebase, then pause to surface
implementation-specific questions (technical approach, patterns, integration strategy, data
modeling). See Step 2.5 in the planner skill.

- Present the implementation questions to the user verbatim.
- Feed user answers back via **SendMessage** to the same agent (do NOT launch a new agent).
- The agent may ask a second round of follow-up questions if the user's answers reveal new
  decision points. Maximum TWO rounds total.
- After receiving answers (or if the agent has no questions), it proceeds to decomposition
  and plan generation.

**Wait for the `PLAN_WRITTEN` stub.** The architect emits a compact stub (feature, plan type,
wave sizes, task count, model distribution, estimated cost) instead of the full plan. The
full plan is written to `.claude/tmp/1b-plan.md` — read that file from disk to access waves,
context briefs, and task metadata for the rest of the pipeline.

After receiving the `PLAN_WRITTEN` stub, read `.claude/tmp/1b-plan.md` and review:
- Does it respect the file-per-task limits from CLAUDE.md?
- Are waves and dependencies sensible?
- Are context briefs self-contained and free of "see task X" cross-references?

If the plan includes a `## Deferred Items` section, process each entry per the
**Backlog Integration** section below (fold or defer). Do this before presenting
the plan to the user so the folded items appear in the wave list.

Present the stub-derived plan summary to the user and wait for confirmation before
proceeding. For all subsequent steps that need brief content (Step 2, Step 2.2, Step 3.5),
the orchestrator reads `.claude/tmp/1b-plan.md` directly — never ask the architect to re-emit
the plan.

**Token tracking:** Per Step 0.6 — one entry for the initial launch (step `1b`); one per impl-clarification SendMessage (step `1b:impl-clarify-N`); one per revision (step `1b:revision-N`). agent=`architect-agent`, model=as selected above.

**Plan revisions:** If the user requests changes, use **SendMessage** to the 1b agent (do NOT launch a new agent — the architect must remember its own plan). Iterate until confirmed.

### Step 1.4: PRE-FLIGHT BUILD VERIFICATION

Catches pre-existing build breakage on the base branch before Wave 1 launches —
swaps a multi-task Haiku escalation for a single targeted fix.

**Skip if:** resuming from a recovery artifact, or the user said "skip pre-flight"
during plan confirmation.

**Procedure:**

1. For each unique stack in `STACK_REGISTRY`, run the stack's build script
   against the current working tree (which still equals base-branch state at
   this point — the PR branch hasn't been cut yet):

   ```bash
   python3 .claude/scripts/<stack>/build.py
   ```

   Use `Bash` with the default 2-minute timeout. If the build script itself
   times out, treat as a `FAIL` with note `build script timed out`.

2. Parse the last line of stdout against the build adapter contract:
   - `BUILD SUCCEEDED  |  N warning(s)` → record `PASS` for that stack
   - `BUILD FAILED  |  N error(s)  |  M warning(s)` → record `FAIL` with the
     full stdout/stderr captured for the user prompt
   - Any other terminating line → record `FAIL` with note `unrecognized build
     output — check adapter contract`

3. Aggregate results across stacks:
   - All stacks PASS → proceed silently to Step 1.5.
   - Any stack FAILED → enter the failure-handling flow below.

**Failure handling:** Present a concise prompt directly (no agent):

> ⚠ Pre-flight build check failed on the base branch. Implementers would hit this in Wave 1.
> Failing stack(s): `<stack> — N error(s)`. Top errors: ```<first 10 lines of stderr/stdout>```
> Choose: **(a) abort** (you fix manually then re-run; no PR created yet),
> **(b) continue anyway** (Haiku may fail and escalate; cost risk $0.20+),
> **(c) inject Wave 0 fix** (Sonnet task prepended; existing waves shift +1).

Wait for the user's choice:
- **(a):** exit `/orchestrate` cleanly. Print a 1a/1b summary so the user can resume. Do NOT
  delete `1a-spec.md` or `1b-plan.md`.
- **(b):** log a `TOKEN_LEDGER` warning entry (`1.4`, notes `continued with broken build`).
  Proceed to Step 1.5.
- **(c):** prepend a new Wave 0 to `.claude/tmp/1b-plan.md` with a single Sonnet implementer
  task. Brief: "Fix pre-existing build failure on the base branch.
  BUILD SCRIPT: `python3 .claude/scripts/<failing_stack>/build.py`.
  BUILD OUTPUT (first 50 lines): <captured>.
  ACCEPTANCE: build script outputs `BUILD SUCCEEDED | N warning(s)` with zero errors.
  Smallest viable fix only — do NOT modify unrelated source or introduce new abstractions."
  Re-number existing waves; original feature work starts at the now-renumbered Wave 1.

**Token tracking:** Per Step 0.6 — one entry per stack build (step `1.4:<stack>`). agent=`orchestrator`, model=`sonnet`. `input_chars=0` (no prompt — direct subprocess), `output_chars`=captured build output length. If failure handling fires, also record `1.4:user-decision` with notes `<a|b|c>`.

Runs pre-PR so `(a) abort` exits cleanly with no GitHub-side cleanup.

### Step 1.5: OPEN PR

Once the user confirms the plan, follow the `open-pr` skill (`.claude/skills/open-pr/SKILL.md`)
to create a feature branch and draft PR **before any implementation begins**.

Provide to the skill:
- **Feature summary** from the plan overview
- **Plan overview** with waves, task list, and key decisions
- **Plan type** (feat, fix, refactor, chore, perf)

Record `PR_BRANCH`, `PR_NUMBER`, `PR_URL` for use in later steps.
All subsequent commits and pushes target this branch.

**Token tracking:** Per Step 0.6 — one entry for step `1.5`. agent=`orchestrator`, model=`sonnet`.

### Step 2: IMPLEMENT

For each wave in the plan, launch implementer agents. **Tasks within a wave run in parallel.**
Tasks across waves are sequential (wave N+1 waits for wave N to complete).

**Streaming reviews:** Do NOT wait for all tasks in a wave to complete before starting reviews.
As each implementer returns SUCCESS, immediately send it to the reviewer (via the wave's shared
reviewer agent). This overlaps review work with still-running implementer tasks, reducing
wall-clock time. The reviewer agent is launched on the first SUCCESS result; subsequent results
use SendMessage. Failed implementers are reported to the user immediately without waiting.

**Batch cap:** If a wave has more than 4 tasks at the same model, split into batches of ≤4
to reduce blast radius and keep individual agent calls under ~50K input tokens. The planner
should keep waves ≤4 tasks; the orchestrator enforces the cap if not.

For each task (or batch of up to 4 tasks) in the current wave:

1. Read the task's `Stack:` field from the plan to determine `<task_stack>`.
   If the plan omits the stack field, resolve it from the task's file paths using the
   `resolve_stack()` algorithm from Step 0.
2. Look up `<task_stack>` in the STACK_REGISTRY to get the correct overlay.
3. Compose the prompt:

```
Agent: implementer-agent
Model: <model from plan — haiku, sonnet, or opus>
Isolation: worktree (if multiple parallel agents in same wave touch different files)
Prompt: |
  You are being launched by the orchestration pipeline.
  Follow all rules from your agent definition (output protocol, build/test
  commands, coverage gate, self-review). No deviations.

  TECH STACK RULES:
  <paste STACK_REGISTRY[<task_stack>]'s implementer overlay — essential variant for Haiku, full for Sonnet/Opus;
   append cross-cutting overlays (matching model variant);
   append local overlays for the implementer role per Step 0.2 matrix (skip empty)>

  BUILD COMMAND: python3 .claude/scripts/<task_stack>/build.py
  TEST COMMAND: python3 .claude/scripts/<task_stack>/test.py

  TASK CONTEXT BRIEF:

  <paste the context brief from the architect's plan here>
```

**Overlay selection:** Haiku tasks get the essential variant (~500-800 chars); Sonnet/Opus tasks
get the full overlay. The reviewer in Step 2.1 has the full overlay and catches any Haiku
violations. The implementer only loads the overlay for its task's stack — loading all stacks
would dilute Haiku's signal-to-noise ratio.

**After each implementer returns** (as soon as it completes, not after the full wave):

- If `SUCCESS`: immediately send to the wave's reviewer agent (Step 2.1). If this is the first
  SUCCESS in the wave, launch the reviewer agent. Otherwise, use SendMessage.
- If `FAILURE`: report the failure details to the user immediately. Do NOT auto-retry implementation failures — these need human judgment. Do NOT block other tasks' reviews.

**Token tracking:** Per Step 0.6 — one entry per implementer (step `2:<task_id>`, e.g. `2:1.1`). agent=`implementer-agent`, model=as assigned by the plan.

### Step 2.1: REVIEW

To reduce repeated context, reuse a single code-reviewer agent within each wave via
**SendMessage** instead of launching a fresh agent per task.

**Reviewer model selection:** Default to **Sonnet**. Use **Haiku** only when ALL of
these conditions hold (the micro-plan rule):

1. The plan contains exactly **one wave** (read the wave count from `1b-plan.md` — not
   just "this is the first wave", but "there is only one wave total").
2. Every task brief in the plan is **< 3,000 chars** (check the `TASK CONTEXT BRIEF`
   field for each task in `1b-plan.md`).
3. This is the **initial review pass** for the wave — not a re-review after a fix
   (Step 2.2 re-reviews always use Sonnet regardless of plan size).

**Why:** On a single-wave micro-plan with small briefs, Sonnet reviewer cost
(~$0.046/call) is 10–15× the Haiku implementer cost (~$0.003/call). A Haiku reviewer
catching syntax, type, and obvious logic errors brings the ratio back toward parity.
The Sonnet reviewer remains available for escalation if Haiku returns FAIL: the
Step 2.2 fix cycle always re-reviews with Sonnet (see below), so quality is not
sacrificed — the Haiku pass just filters the easy cases cheaply.

If the Haiku reviewer returns FAIL, route to Step 2.2 as normal. The re-review after
the fix (Step 2.2 completion) uses Sonnet unconditionally.

**Token tracking note:** When Haiku is selected, record `model: haiku` in the
TOKEN_LEDGER entry for this review (step `2.1:<task_id>`).

**First review in a wave** — determine which stacks appear in the wave's tasks, then
launch a new code-reviewer agent with those stacks' reviewer overlays:

```
Agent: code-reviewer-agent
Model: <sonnet (default) or haiku (micro-plan rule above)>
Prompt: |
  You are being launched by the orchestration pipeline.
  Use the PASS/FAIL output protocol from your agent definition.
  Append a TOKEN_REPORT block after your output.

  You will review multiple tasks in this wave. Each review is independent — when
  you receive a "NEW REVIEW" message, discard all prior review context and review
  ONLY the new changes presented.

  TECH STACK REVIEW RULES:
  <for each unique stack in this wave's tasks, paste its reviewer-overlay.md under "## <Stack> Review Rules" (apply only to matching files);
   append cross-cutting overlays under "## Cross-Cutting: <name> Review Rules";
   append local overlays for the reviewer role per Step 0.2 matrix (skip empty)>

  REVIEW THESE CHANGES:

  <list the files the implementer created/modified>
```

**Subsequent reviews in the same wave** — use SendMessage to the same agent:

```
SendMessage to: <reviewer agent from first review>
Message: |
  NEW REVIEW — discard all prior review context. Review ONLY the following changes.

  REVIEW THESE CHANGES:

  <list the files the next implementer created/modified>
```

**Cap at 4 reviews per agent.** If a wave has more than 4 tasks, launch a fresh reviewer
agent for tasks 5+. This prevents context window saturation from accumulated review output —
empirically, reviewer SendMessage context grows ~50-100% per added review, so the cap is
aligned with the wave-size cap (≤4 tasks) to keep cumulative growth bounded.

**After each review returns:**

- If `PASS`: proceed to Step 3 (commit)
- If `FAIL`: proceed to Step 2.2 (fix)

**Backlog classification:** after handling PASS/FAIL, parse the
`--- OPTIONAL IMPROVEMENTS ---` section. Each entry is tagged `[should-fix]`,
`[nice-to-have]`, or `[simplify]`. For each, apply the fold-vs-defer rule in
the Backlog Integration section below. This happens after the pass/fail
handshake — do not let it block the review cycle.

**Token tracking:** Per Step 0.6 — one entry per review (step `2.1:<task_id>`). agent=`code-reviewer-agent`, model=`sonnet`/`haiku` per micro-plan rule above. For SendMessage reviews, `input_chars` is the SendMessage content only.

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
  <paste STACK_REGISTRY[<task_stack>].implementer overlay (full — fixes always get full overlay);
   append cross-cutting overlays;
   append local overlays for the implementer role per Step 0.2 matrix (skip empty)>

  BUILD COMMAND: python3 .claude/scripts/<task_stack>/build.py
  TEST COMMAND: python3 .claude/scripts/<task_stack>/test.py

  CODE REVIEW FINDINGS TO FIX:

  <paste the FAIL output from code-reviewer>

  FILES YOU PREVIOUSLY MODIFIED:

  <list of files>
```

**After fix returns:**
- If `SUCCESS`: proceed to Step 3 (commit). The fix agent's self-review + build + test
  is sufficient — do NOT re-review. Skip the review-fix cycle.
- If `FAILURE`: report to user with full context.

**Token tracking:** Per Step 0.6 — one entry per fix (step `2.2:<task_id>`). agent=`implementer-agent`, model=`sonnet`, `is_retry=true`. If original task was Haiku, also `is_escalation=true` with notes `escalated from haiku`.

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

### Step 3.4: AUTOMATED BROWSER UI TEST (conditional)

**Gating rule:** Evaluate these checks in order. Skip Step 3.4 silently at the
first one that fails — do not run later checks (each is more expensive than
the last).

1. **Capability check** — `ACTIVE_CAPABILITIES` includes `browser-ui` (at
   least one active stack's `manifest.json` declares this capability — `react`
   does by default). Fast in-memory lookup.
2. **Wave-relevance check** — at least one file in `FILES_MODIFIED` (across
   all waves this run) resolves via `resolve_stack()` to a stack with the
   `browser-ui` capability. Pure backend-only runs skip Step 3.4.
3. **Tool availability check** — probe whether the `claude-in-chrome` MCP
   tools are authorized in the current session:
   ```
   ToolSearch query: "select:mcp__claude-in-chrome__tabs_context_mcp"
   ```
   If the result contains a `<function>` schema for that tool, chrome is
   authorized. If the result is "No matching deferred tools found" (or
   equivalent empty result), the MCP server is not configured for this
   session — skip Step 3.4 silently. No flag, no warning: the user simply
   has not opted into chrome for this session.

The probe in check 3 is the source of truth for "is chrome authorized?" —
mirroring how `ACTIVE_CAPABILITIES` drives `azure-auth`. There is no
`--chrome` flag because the MCP tool list is itself the authorization signal:
if the user added `claude-in-chrome` to their MCP config and approved it,
the tools are loadable; if they did not, they are not.

**Invocation:**

```
Skill: chrome-ui-test
Prompt: |
  Read `.claude/skills/chrome-ui-test/SKILL.md` for your instructions.

  IMPLEMENTATION_SUMMARY:
  <one paragraph from the plan + commit messages, focused on user-visible behavior>

  FILES_MODIFIED:
  <list of files touched across all waves, filtered to browser-ui stacks>

  TASK_BRIEFS:
  <paste the original context briefs for tasks whose stack has browser-ui capability>

  DEV_SERVER_HINT:
  <if the project has a `dev` script in package.json, paste the script line and
   default port; otherwise the skill will inspect package.json itself>

  RECORD_GIF: <true if the user explicitly asked for a recording in their request, else false>
```

**Outcome handling:**

- **PASS** — record the result in TOKEN_LEDGER and proceed to Step 3.5. The
  user-facing prompt for manual test should mention the automated smoke
  passed: "Automated browser smoke test passed (golden path + N edge cases).
  Please test the branch and report any bugs..."
- **FAIL** — treat the failure as a bug report and route it through the
  existing Step 3.5.1 (ASSESS) → 3.5.2 (FIX) → 3.5.3 (REVIEW) → 3.5.4
  (COMMIT) → 3.5.5 (RE-TEST) cycle. Use the skill's "Reproduction" block as
  the bug report. After the fix is committed, re-run Step 3.4 once before
  handing back to the user. If Step 3.4 fails twice on the same scenario,
  stop and present the findings — do NOT loop.

**Token tracking:** Per Step 0.6 — one entry for step `3.4` (re-runs as `3.4:retry-N`). agent=`orchestrator` (skill, not an Agent launch), model=`sonnet`.

The automated smoke catches wiring failures; the user's manual test in 3.5 remains authoritative
for UX, copy, and business-rule edge cases.

### Step 3.5: MANUAL TEST

After all implementation is committed and pushed, prompt the user to test the PR branch:

> "All tasks implemented and pushed to `PR_BRANCH`. Please test the branch and report
> any bugs found, or say **tests pass** to finalize the PR."

**If the user says "tests pass":** proceed to Step 4.

**For each bug reported, run this cycle:**

**Parallel bug fixes:** When the user reports multiple bugs at once, group them by independence:
- **Independent bugs** have non-overlapping file sets (no shared files to modify). These can be
  fixed in parallel using worktree isolation (same pattern as Step 2 parallel tasks).
- **Dependent bugs** share files or have causal relationships. These must be fixed sequentially.

To parallelize: run Step 3.5.1 (ASSESS) for all bugs first. After assessment, identify which
bugs have non-overlapping FILES TO MODIFY lists. Launch parallel implementer agents (with
worktree isolation) for independent bugs. Review them using the shared bug-fix reviewer agent
via SendMessage. Commit in assessment order (not completion order) for deterministic history.

If the user reports bugs one at a time (interactive), process them sequentially as before.

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
  <paste each STACK_REGISTRY stack's architect-overlay.md under "## <Stack> Architecture Context";
   append cross-cutting overlays;
   append local overlays for the architect role per Step 0.2 matrix (skip empty)>

  A bug was found during manual testing of a feature implementation. Assess the
  blast radius of fixing this bug and recommend a fix approach.

  BUG REPORT:
  "<user's bug report verbatim>"

  FILES MODIFIED BY THE IMPLEMENTATION:
  <list all files modified across all tasks>

  ORIGINAL PLAN SUMMARY:
  <paste the plan overview — waves and task names, not full briefs>

  CODEBASE CONTEXT (ORCHESTRATOR.md 3.5 extract — do not re-read from disk):
  <paste 3.5 Extract from Step 0.7>

  Respond with EXACTLY these 6 fields, each capped to keep the response bounded.
  Do NOT add prose outside these fields. Total response should fit in ~200 words.
  1. ROOT CAUSE (1-3 sentences): Which file(s) and task(s) likely caused this
  2. BLAST RADIUS (1-3 sentences): What other files/behaviors could be affected by a fix
  3. FRAGILE AREAS (1-3 sentences, or `none` if no overlap): Any Known Fragile Areas
     in the blast radius
  4. FIX APPROACH (1-3 sentences): Specific fix strategy
  5. FILES TO MODIFY (bullet list, paths only — no prose)
  6. REGRESSION RISK (one line): Low/Medium/High with one-sentence justification
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
  <resolve stack via resolve_stack() on affected files, paste STACK_REGISTRY[<resolved_stack>].implementer overlay (full);
   append cross-cutting overlays;
   append local overlays for the implementer role per Step 0.2 matrix (skip empty)>

  BUILD COMMAND: python3 .claude/scripts/<resolved_stack>/build.py
  TEST COMMAND: python3 .claude/scripts/<resolved_stack>/test.py

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

**Reviewer reuse:** Use the same SendMessage pattern as Step 2.1 wave reviews to avoid
re-ingesting the agent definition and overlays for each bug-fix review. Launch ONE
code-reviewer agent for the first bug-fix review, then reuse it via SendMessage for subsequent
bug-fix reviews in the same manual test round.

**First bug-fix review** — launch a fresh reviewer:

```
Agent: code-reviewer-agent
Model: sonnet
Prompt: |
  You are being launched by the orchestration pipeline.
  Use the PASS/FAIL output protocol from your agent definition.

  TECH STACK REVIEW RULES:
  <resolve stack via resolve_stack() on affected files, paste STACK_REGISTRY[<resolved_stack>].reviewer overlay under "## <Stack> Review Rules";
   append cross-cutting overlays;
   append local overlays for the reviewer role per Step 0.2 matrix (skip empty)>

  This is a BUG FIX review. In addition to your standard checks, explicitly verify:
  - The fix does not revert or contradict the original implementation's intent
  - The fix does not introduce regressions in adjacent functionality
  - The test count has not decreased from the baseline

  REVIEW THESE CHANGES:

  <list the files the fix agent modified>
```

**Subsequent bug-fix reviews** — reuse the same agent via SendMessage:

```
SendMessage to: <bug-fix reviewer agent from first review>
Message: |
  NEW REVIEW — discard all prior review context. Review ONLY the following changes.
  This is a BUG FIX review (same explicit checks as the first review above).

  REVIEW THESE CHANGES:

  <list the files the fix agent modified>
```

**Cap at 4 reviews per agent** (same as wave reviews). If a manual test round produces more
than 4 bug-fix reviews, launch a fresh reviewer for reviews 5+. The cap matches Step 2.1
to bound SendMessage context drift (empirically ~50-100% growth per added review).

**Token tracking:** Per Step 0.6 — one entry per bug-fix sub-step:
- `3.5:assess:<bug_id>` — `architect-agent`, `sonnet` (only if blast-radius triggered)
- `3.5:fix:<bug_id>` — `implementer-agent`, `sonnet`, `is_retry=true`
- `3.5:review:<bug_id>` — `code-reviewer-agent`, `sonnet` (SendMessage `input_chars` is the message content only)

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
3.5. If `BACKLOG_ENABLED=true` and `.claude/tmp/run-log.yml` has any entries with
   `action: folded`, render the "Folded in this run" checklist into the PR body
   (see the Backlog Integration section for the format). Skip this if no folds
   occurred.
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

### Step 5: TOKEN ANALYSIS (mandatory)

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

---

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
