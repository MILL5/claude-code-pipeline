---
step: "1a"
requires: []
produces: [.claude/tmp/1a-spec.md]
sendmessage: required
---

# Step 1a: ANALYZE & CLARIFY

This file is read by the orchestrator just-in-time before executing Step 1a.
The orchestrator's residual `SKILL.md` (Step Dispatch table) routes here. Shared
protocols (SendMessage notes, Step 0.6 token tracking, Step 0.7 ORCHESTRATOR.md
extracts) live in `SKILL.md` and remain accessible.

**Pre-flight check (orchestrator, before launching the 1a agent):**

1. Run `git status` — if the working tree is dirty, warn the user before proceeding.
2. Run `git branch --show-current` — confirm you are on the expected branch.
3. Check ORCHESTRATOR.md "Current State" — note the last known build/test status and date. If the last recorded status is older than the most recent commit, recommend the user run a build/test pass before planning.

**1a passthrough detection (orchestrator, runs BEFORE the resume check below):**

Check whether the user's `/orchestrate` request body is structurally a near-complete
spec — i.e., the user supplied a detailed plan (e.g., an existing `OPTIMIZATION_PLAN.md`)
rather than a brief request. Detection follows
`tests/parsers.py::detect_user_supplied_spec` exactly:

- Length ≥ 1500 chars, AND
- Contains ≥2 of the headers (case-sensitive, exact substring): `## Summary`,
  `## Acceptance criteria`, `## Out of scope`

If detected, present:

> Treating your input as the 1a-spec — skipping Step 1a (saves ~$0.26 of derivation
> work that 1a would have largely just verified). Reply `run 1a` to override.

If the user replies `run 1a` (case-insensitive, leading/trailing whitespace ignored),
discard the detection and fall through to the resume check below. Otherwise:

1. Write the user's request body verbatim to `.claude/tmp/1a-spec.md` (overwriting any
   prior file — the user's fresh spec is authoritative; the resume check is bypassed).
2. Skip the architect-agent launch + clarification loop below.
3. Record a passthrough entry in `TOKEN_LEDGER` (step=`1a:passthrough`,
   agent=`orchestrator`, model=`—`, total_tokens=0, dur_ms=0) for ledger continuity.
4. Proceed directly to Step 1b.

Detection is intentionally conservative — false positives (skipping 1a when needed)
are worse than false negatives (running 1a unnecessarily). The override path
guarantees the user can always force normal 1a execution. Do NOT invent permissive
header variants; follow the parser's exact header list.

**Resume check (only if passthrough did not fire):**

Check whether `.claude/tmp/1a-spec.md` already exists from a prior run. If it does,
ask the user: "A previous 1a analysis exists — resume from it or start fresh?"

- **Resume** → skip the agent launch and proceed directly to Step 1b with the existing spec.
- **Start fresh** → delete `.claude/tmp/1a-spec.md` and run Step 1a normally below.

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

**Recovery:** Resume behavior on interrupted runs is governed by the Resume dispatch matrix in `SKILL.md` — that matrix is authoritative. Do not duplicate or redefine resume rules here.
