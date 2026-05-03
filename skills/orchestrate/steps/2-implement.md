---
step: "2"
requires: []
produces: []
sendmessage: n/a
---

# Step 2: IMPLEMENT

This file is read by the orchestrator just-in-time before executing Step 2.
The orchestrator's residual `SKILL.md` (Step Dispatch table) routes here. Shared
protocols (SendMessage notes, Step 0.6 token tracking, Backlog Integration) live
in `SKILL.md` and remain accessible.

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
