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
1b, 2.1, and 3.5. `SendMessage` is an experimental Claude Code tool gated behind the
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` environment variable.

**To enable** (persists across sessions — add to `~/.claude/settings.json`):
```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```
Restart Claude Code, then verify with `ToolSearch: select:SendMessage` — the schema should load.

**Addressing:** `SendMessage` must use the agent's **UUID** (the `agentId:` value in the
`Agent` tool's output), NOT the `name:` field. Named routing requires `TeamCreate` registration
and is not used by this skill. Example:

> After `Agent({ name: "wave-reviewer", ... })` returns, the output includes a line like:
> `agentId: ad67fc84c7259e8ad`
> Capture that UUID. All subsequent `SendMessage` calls use it:
> `SendMessage({ to: "ad67fc84c7259e8ad", message: "..." })`

**Async semantics:** `SendMessage` is fire-and-notify, not request-and-wait. The call returns
immediately; the resumed agent's reply arrives later as a `<task-notification>`. The
clarification loops in Steps 1a and 1b work as follows: relay questions to the user, receive
answers, call `SendMessage` with the UUID, then wait for the `<task-notification>` before
proceeding to the next step.

**Fallback when unavailable:** If `ToolSearch: select:SendMessage` returns no matches (env var
not set), launch a fresh `Agent` with prior context re-embedded in the prompt for each
continuation. Accept the ~30–40% higher input token cost. Do NOT attempt `SendMessage` when
the tool is unavailable — the call will fail with "No matching deferred tools found".

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

**When to run:** If `ACTIVE_CAPABILITIES` includes `azure-auth`, AND the pipeline will
perform Azure-dependent operations (what-if, deploy, drift-check, infra-test).

**Skip if:** The pipeline only involves local operations (build, lint, scan, cost estimate).
Build and review steps do NOT require Azure auth.

**How to run:** Invoke the `azure-login` skill. It will:

1. Verify `az` CLI is installed
2. Verify the user is authenticated (`az account show`)
3. Display the active subscription, tenant, user, and auth method
4. Cache the result as `AZURE_AUTH_STATUS` for the session

**On failure:** The `azure-login` skill prints remediation guidance. The pipeline should:
- **Pause** and present the guidance to the user
- **Ask** the user to authenticate (e.g., `! az login` in the Claude Code prompt)
- **Retry** the pre-flight check after the user confirms they have logged in
- **Do NOT** proceed with Azure-dependent steps if auth fails

**On success:** Record the auth context:
- `AZURE_AUTH_STATUS = OK`
- `AZURE_SUBSCRIPTION_ID`, `AZURE_SUBSCRIPTION_NAME`, `AZURE_TENANT_ID`
- `AZURE_USER`, `AZURE_AUTH_METHOD`

Subsequent Azure-dependent skills check `AZURE_AUTH_STATUS` and skip re-validation if already OK.
If the target subscription or resource group changes mid-pipeline, re-validate.

**Timing:** This check runs lazily — only before the first Azure-dependent step, not at pipeline
start. This avoids blocking developers who are only doing local build/lint/review cycles.

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
| `agent_input_self` | number | Agent's self-assessed total input chars (from TOKEN_REPORT) |
| `agent_output_self` | number | Agent's self-assessed total output chars (from TOKEN_REPORT) |

**How to record:** After every Agent launch or SendMessage call:
1. Measure the composed prompt length as `input_chars` and the agent's complete response as
   `output_chars`. Compute approximate tokens as `chars / 4`.
2. Parse the agent's `---TOKEN_REPORT---` block (if present) to extract `files_read`,
   `tool_calls`, `agent_input_self`, and `agent_output_self`. These capture consumption
   invisible to the orchestrator (file reads from disk, tool-generated output).
3. If the TOKEN_REPORT is missing or malformed, leave those fields empty — do not fail.
4. Append the entry to `TOKEN_LEDGER`.

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

**Fallback:** If any expected `##` header is not found in ORCHESTRATOR.md (e.g., the file was
customized), paste the full file instead of a partial extract.

## Pipeline Overview

```
User Request
    |
    v
Step 1a: FEATURE CLARIFICATION (architect-agent, Sonnet, interactive)
    |  Pre-flight check -> feature decomposition -> feature-only Q&A (iterative, max 3 rounds)
    |  Questions: scope, behavior, edge cases, business rules, DoD — NO technical questions
    |  Writes: .claude/tmp/1a-spec.md (enriched spec + recovery artifact)
    v
Step 1b: IMPLEMENTATION CLARIFICATION & PLAN (architect-agent, Sonnet default / Opus, fresh agent)
    |  Reads: 1a-spec.md + 1b Extract from ORCHESTRATOR.md (clean context, ~12K tokens)
    |  Phase 1: Analyze codebase + enriched spec -> implementation Q&A (max 2 rounds)
    |  Questions: architecture approach, patterns, integration, data modeling, tradeoffs
    |  Phase 2: Decompose into task plan with context briefs
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
    |
    v
Step 5: TOKEN ANALYSIS (mandatory, token-analysis skill)
    |  Reads: TOKEN_LEDGER accumulated during pipeline
    |  Analyzes: cost efficiency, model distribution, prompt bloat, escalation patterns
    |  Files: GitHub issue on pipeline repo if significant findings exist
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
  <for each stack in STACK_REGISTRY, paste its architect-overlay.md under a
   "## <Stack> Architecture Context" header>

  <append cross-cutting overlays under "## Cross-Cutting: <name> Context" headers>

  <append local overlays: LOCAL_OVERLAYS.all under "## Project: Local Standards",
   LOCAL_OVERLAYS.architect under "## Project: Architecture Rules" — skip if empty>

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

**Token tracking:** Record a `TOKEN_LEDGER` entry after the initial agent launch (step `1a`) and after each SendMessage round in the clarification loop (step `1a:clarify-N`). For each entry, measure the composed prompt as `input_chars` and the agent's response as `output_chars`. Agent: `architect-agent`, model: `sonnet`.

**TOKEN_LEDGER gate:** After Step 1a completes and `.claude/tmp/1a-spec.md` is written,
verify that `TOKEN_LEDGER` contains at least one entry. If the ledger is empty, warn the user:

> ⚠ TOKEN_LEDGER is empty after Step 1a — token tracking was skipped. Step 5 analysis
> will reconstruct from `<usage>` blocks with reduced accuracy.

Do NOT abort the pipeline. Continue with implementation but note the tracking gap.

**Recovery:** If the pipeline is interrupted after 1a and `.claude/tmp/1a-spec.md` exists, skip 1a entirely and go directly to 1b. If `.claude/tmp/1b-plan.md` also exists, skip both 1a and 1b — present the saved plan to the user for confirmation and proceed to Step 1.5.

---

### Step 1b: PLAN

Launch a **fresh** architect-agent in 1b mode. Do NOT use SendMessage from the 1a agent — start a new agent so 1b has a clean context window (~15K tokens of focused signal vs. the full 1a Q&A history).

**Model selection:** Default to **Sonnet** for Step 1b. Only escalate to **Opus** when the
1a-spec indicates at least one of:
- Novel architecture with no existing patterns in the codebase to follow
- Cross-cutting changes affecting 3+ services/modules with shared state
- Concurrent/async coordination requiring holistic correctness reasoning
- Security-critical design where subtle errors have severe consequences

Most feature work — CRUD endpoints, UI components, config changes, test additions,
mechanical refactors — does not need Opus-level planning. The planner skill's decomposition
logic works equally well on Sonnet for well-understood problem types. When in doubt, start
with Sonnet; if the plan quality is poor (vague briefs, missed dependencies), the user can
request a re-plan with Opus.

```
Agent: architect-agent
Model: <sonnet (default) or opus (if escalation criteria above are met)>
Prompt: |
  MODE: 1b — Plan Generation

  Read `.claude/skills/architect-planner/SKILL.md` for your instructions.

  TECH STACK CONTEXT:
  <for each stack in STACK_REGISTRY, paste its architect-overlay.md under a
   "## <Stack> Architecture Context" header>

  <append cross-cutting overlays under "## Cross-Cutting: <name> Context" headers>

  <append local overlays: LOCAL_OVERLAYS.all under "## Project: Local Standards",
   LOCAL_OVERLAYS.architect under "## Project: Architecture Rules" — skip if empty>

  STACK MAPPING (for task assignment — assign each task a stack based on its files):
  <for each stack, list its stack_paths patterns, e.g.:
   - react: src/frontend/**
   - python: src/backend/**
   - bicep: infra/**>

  ENRICHED SPEC:
  <paste full contents of .claude/tmp/1a-spec.md>

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

**Wait for the plan.** Review it for:
- Does it respect the file-per-task limits from CLAUDE.md?
- Are waves and dependencies sensible?
- Are context briefs self-contained and free of "see task X" cross-references?

Present the plan summary to the user and wait for confirmation before proceeding.

**Token tracking:** Record a `TOKEN_LEDGER` entry for the initial 1b agent launch (step `1b`). If implementation clarification questions occur, record each SendMessage round as step `1b:impl-clarify-N`. If plan revisions are requested, record each revision round as step `1b:revision-N`. Agent: `architect-agent`, model: as selected above (`sonnet` or `opus`).

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

**Token tracking:** Record a `TOKEN_LEDGER` entry for the open-pr step (step `1.5`). Agent: `orchestrator`, model: `sonnet`. Measure the skill invocation prompt and output.

### Step 2: IMPLEMENT

For each wave in the plan, launch implementer agents. **Tasks within a wave run in parallel.**
Tasks across waves are sequential (wave N+1 waits for wave N to complete).

**Streaming reviews:** Do NOT wait for all tasks in a wave to complete before starting reviews.
As each implementer returns SUCCESS, immediately send it to the reviewer (via the wave's shared
reviewer agent). This overlaps review work with still-running implementer tasks, reducing
wall-clock time. The reviewer agent is launched on the first SUCCESS result; subsequent results
use SendMessage. Failed implementers are reported to the user immediately without waiting.

**Batch cap:** If a wave contains more than 4 tasks assigned to the same model, split them
into multiple agent calls of at most 4 tasks each. This reduces blast radius (a failure at
task 3 doesn't require re-running tasks 5-8) and keeps individual agent calls under ~50K
input tokens. The planner should ideally keep waves to ≤4 tasks, but if it produces larger
waves, the orchestrator enforces the cap here.

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
  <select overlay by model assignment from STACK_REGISTRY[<task_stack>]:
    - Haiku tasks: paste implementer_essential overlay
    - Sonnet/Opus tasks: paste implementer overlay (full)>

  <append cross-cutting overlays (essential or full, matching model)>

  <append local overlays: LOCAL_OVERLAYS.all under "## Project: Local Standards",
   LOCAL_OVERLAYS.implementer under "## Project: Coding Standards" — skip if empty>

  BUILD COMMAND: python3 .claude/scripts/<task_stack>/build.py
  TEST COMMAND: python3 .claude/scripts/<task_stack>/test.py

  TASK CONTEXT BRIEF:

  <paste the context brief from the architect's plan here>
```

**Overlay selection rationale:** Haiku tasks receive only the essential rules (~500-800 chars)
to maximize signal-to-noise ratio. The reviewer in Step 2.1 has the full overlay and will catch
any violations. Sonnet/Opus tasks receive the full overlay since they handle complex tasks where
examples and patterns are valuable.

**Stack scoping rationale:** The implementer only needs rules for the stack it is working in.
Loading all stacks' overlays would dilute Haiku's signal-to-noise ratio and waste tokens.

**After each implementer returns** (as soon as it completes, not after the full wave):

- If `SUCCESS`: immediately send to the wave's reviewer agent (Step 2.1). If this is the first
  SUCCESS in the wave, launch the reviewer agent. Otherwise, use SendMessage.
- If `FAILURE`: report the failure details to the user immediately. Do NOT auto-retry implementation failures — these need human judgment. Do NOT block other tasks' reviews.

**Token tracking:** Record a `TOKEN_LEDGER` entry for each implementer agent (step `2:<task_id>`, e.g., `2:1.1`). Agent: `implementer-agent`, model: as assigned by the plan.

### Step 2.1: REVIEW

To reduce repeated context, reuse a single code-reviewer agent within each wave via
**SendMessage** instead of launching a fresh agent per task.

**First review in a wave** — determine which stacks appear in the wave's tasks, then
launch a new code-reviewer agent with those stacks' reviewer overlays:

```
Agent: code-reviewer-agent
Model: sonnet
Prompt: |
  You are being launched by the orchestration pipeline.
  Use your Pipeline Mode output protocol (PASS/FAIL).
  Append a TOKEN_REPORT block after your output.

  You will review multiple tasks in this wave. Each review is independent — when
  you receive a "NEW REVIEW" message, discard all prior review context and review
  ONLY the new changes presented.

  TECH STACK REVIEW RULES:
  <for each unique stack in this wave's tasks, paste its reviewer-overlay.md
   under a "## <Stack> Review Rules" header. Apply only the rules matching the
   tech stack of the files under review.>

  <append cross-cutting overlays under "## Cross-Cutting: <name> Review Rules" headers>

  <append local overlays: LOCAL_OVERLAYS.all under "## Project: Local Standards",
   LOCAL_OVERLAYS.implementer under "## Project: Coding Standards",
   LOCAL_OVERLAYS.reviewer under "## Project: Review Criteria" — skip if empty>

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

**Cap at 8 reviews per agent.** If a wave has more than 8 tasks, launch a fresh reviewer
agent for tasks 9+. This prevents context window saturation from accumulated review output.

**After each review returns:**

- If `PASS`: proceed to Step 3 (commit)
- If `FAIL`: proceed to Step 2.2 (fix)

**Token tracking:** Record a `TOKEN_LEDGER` entry for each review (step `2.1:<task_id>`). Agent: `code-reviewer-agent`, model: `sonnet`. For SendMessage reviews, `input_chars` is the SendMessage content (not the full accumulated context).

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
  <paste STACK_REGISTRY[<task_stack>].implementer overlay (full — fixes always get full overlay)>

  <append cross-cutting overlays>

  <append local overlays: LOCAL_OVERLAYS.all under "## Project: Local Standards",
   LOCAL_OVERLAYS.implementer under "## Project: Coding Standards" — skip if empty>

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

**Token tracking:** Record a `TOKEN_LEDGER` entry for each fix (step `2.2:<task_id>`). Agent: `implementer-agent`, model: `sonnet`. Set `is_retry: true`. If the original task was assigned to haiku, also set `is_escalation: true` and note `escalated from haiku` in notes.

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
  <for each stack in STACK_REGISTRY, paste its architect-overlay.md under a
   "## <Stack> Architecture Context" header>

  <append cross-cutting overlays>

  <append local overlays: LOCAL_OVERLAYS.all under "## Project: Local Standards",
   LOCAL_OVERLAYS.architect under "## Project: Architecture Rules" — skip if empty>

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
  <resolve stack from affected files using resolve_stack(), then paste
   STACK_REGISTRY[<resolved_stack>].implementer overlay (full)>

  <append cross-cutting overlays>

  <append local overlays: LOCAL_OVERLAYS.all under "## Project: Local Standards",
   LOCAL_OVERLAYS.implementer under "## Project: Coding Standards" — skip if empty>

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
  Use your Pipeline Mode output protocol (PASS/FAIL).

  TECH STACK REVIEW RULES:
  <resolve stack from affected files, then paste
   STACK_REGISTRY[<resolved_stack>].reviewer overlay under
   "## <Stack> Review Rules" header>

  <append cross-cutting overlays>

  <append local overlays: LOCAL_OVERLAYS.all under "## Project: Local Standards",
   LOCAL_OVERLAYS.implementer under "## Project: Coding Standards",
   LOCAL_OVERLAYS.reviewer under "## Project: Review Criteria" — skip if empty>

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

  This is a BUG FIX review. Explicitly verify:
  - The fix does not revert or contradict the original implementation's intent
  - The fix does not introduce regressions in adjacent functionality
  - The test count has not decreased from the baseline

  REVIEW THESE CHANGES:

  <list the files the fix agent modified>
```

**Cap at 8 reviews per agent** (same as wave reviews). If a manual test round produces more
than 8 bug-fix reviews, launch a fresh reviewer for reviews 9+.

**Token tracking:** Record `TOKEN_LEDGER` entries for each sub-step of the bug-fix cycle:
- Blast-radius analysis (if triggered): step `3.5:assess:<bug_id>`, agent: `architect-agent`, model: `sonnet`
- Bug fix: step `3.5:fix:<bug_id>`, agent: `implementer-agent`, model: `sonnet`, set `is_retry: true`
- Bug fix review: step `3.5:review:<bug_id>`, agent: `code-reviewer-agent`, model: `sonnet`. For SendMessage reviews, `input_chars` is the SendMessage content only.

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

### Step 5: TOKEN ANALYSIS (mandatory)

**Timing:** Launch token analysis **in the background** at the same time as Step 4 finalization.
The TOKEN_LEDGER is complete after Step 3.5 — it does not depend on PR finalization. This
overlaps analysis work with ORCHESTRATOR.md updates, PR body updates, and `gh pr ready`,
reducing wall-clock time. If analysis files a GitHub issue, report it to the user after
Step 4 completes (or immediately if Step 4 finishes first).

This step always runs — it is not skippable.

#### 5.1: Compute Summary

Record `PIPELINE_END` as the current timestamp. Compute `TOKEN_SUMMARY` from the `TOKEN_LEDGER`:

- **Total tokens**: sum of all `input_tokens` and `output_tokens` across all ledger entries
- **Model breakdown**: for each model (haiku, sonnet, opus) — call count, total input tokens,
  total output tokens
- **Step breakdown**: for each step prefix (1a, 1b, 1.5, 2, 2.1, 2.2, 3.5) — call count, total
  input tokens, total output tokens
- **Estimated cost**: using pricing Haiku $1/$5, Sonnet $3/$15, Opus $15/$75 per M tokens (in/out)
- **Actual model distribution**: percentage of total token spend per model vs. the 70/20/10 target
- **Escalation count**: entries where `is_escalation` is true
- **Retry count**: entries where `is_retry` is true

#### 5.2: Derive Pipeline Repo

Resolve the pipeline repo's GitHub `owner/repo` for issue filing:

```bash
PIPELINE_REMOTE=$(git -C <pipeline_root> remote get-url origin)
```

Parse `PIPELINE_REMOTE` to extract `owner/repo`:
- SSH format `git@github.com:owner/repo.git` → `owner/repo`
- HTTPS format `https://github.com/owner/repo.git` → `owner/repo`
- Strip trailing `.git` if present

#### 5.3: Launch Token Analysis

Read `.claude/skills/token-analysis/SKILL.md` for the skill's full instructions, then invoke it:

```
Skill: token-analysis
Prompt: |
  Read `.claude/skills/token-analysis/SKILL.md` for your instructions.

  TOKEN LEDGER:
  <paste the full TOKEN_LEDGER as a markdown table>

  TOKEN SUMMARY:
  <paste the computed TOKEN_SUMMARY>

  PIPELINE CONTEXT:
  - Plan file: .claude/tmp/1b-plan.md (read for planned vs actual model assignments)
  - Pipeline repo: <owner/repo>
  - Pipeline root: <pipeline_root>
  - Target project stacks: <stacks (comma-separated)>
  - Pipeline duration: <PIPELINE_START> to <PIPELINE_END>
```

#### 5.4: Report Results

- If the skill returns `FINDINGS: NONE`, report to the user:
  > "Token analysis complete — no significant optimization opportunities found."
- If the skill returns `FINDINGS: FILED` with an issue URL, report to the user:
  > "Token analysis complete — findings filed as <issue URL>."
- If the skill fails or `gh issue create` errors, log a warning and report to the user. Do NOT
  consider the pipeline failed — all substantive work (implementation, review, commit, PR) is
  already complete.

---

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
| `gh issue create` fails (missing label, auth, etc.) | Retry without `--label`, report failure if still errors |
| Pipeline repo has no GitHub remote | Skip issue filing, report token summary to user directly |

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
