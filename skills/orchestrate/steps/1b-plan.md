---
step: "1b"
requires: [.claude/tmp/1a-spec.md]
produces: [.claude/tmp/1b-plan.md]
sendmessage: required
---

# Step 1b: PLAN

This file is read by the orchestrator just-in-time before executing Step 1b.
The orchestrator's residual `SKILL.md` (Step Dispatch table) routes here. Shared
protocols (SendMessage notes, Step 0.6 token tracking, Backlog Integration) live
in `SKILL.md` and remain accessible.

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
