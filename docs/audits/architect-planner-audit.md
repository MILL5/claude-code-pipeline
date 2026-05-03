# Architect-Planner Skill Audit (issue #76)

**Date:** 2026-05-03
**Skill audited:** `skills/architect-planner/SKILL.md`
**Total size:** 540 lines / 32,747 chars / ~8,186 tokens (chars/4 estimate)
**Decision:** **NO-GO on splitting.** Largest-realistic split bundle is ~1,200 tokens, below the issue's ≥1,500-token threshold. Two opportunistic non-split wins (~456 tokens total) are flagged for a possible follow-up.

## Measurement method

`chars / 4` per the `token-analysis` skill convention. Section boundaries computed by stepping through every `##`/`###`/`####` header and summing the line range until the next header. Verified against `wc -c` (32,900 chars including final newline) and `wc -l` (540 lines).

## Section breakdown

| Section | Level | Lines | Chars | ~Tok | Classification |
|---|---|---|---|---|---|
| (preamble: frontmatter + intro) | – | 27 | 1,453 | 363 | static |
| Philosophy | H2 | 8 | 738 | 184 | static |
| Model Capability Reference (intro) | H2 | 4 | 130 | 32 | static |
| └ What Haiku Can Reliably Do | H3 | 10 | 663 | 165 | static |
| └ What Haiku Cannot Reliably Do | H3 | 8 | 430 | 107 | static |
| └ What Needs Opus | H3 | 7 | 396 | 99 | static |
| Planning Process (intro) | H2 | 2 | 20 | 5 | static |
| └ Step 1: Verify Enriched Spec Coverage | H3 | 14 | 809 | 202 | static |
| └ Step 2: Identify Irreducible Complexities | H3 | 11 | 795 | 198 | static |
| └ Step 2.5: Implementation Clarification (Checkpoint) | H3 | 47 | 3,184 | 796 | static |
| └ Step 3: Decompose Into Haiku-Sized Tasks (intro) | H3 | 4 | 137 | 34 | static |
| &nbsp;&nbsp;&nbsp;&nbsp;└ Strategy A: Vertical Slicing | H4 | 6 | 257 | 64 | reference |
| &nbsp;&nbsp;&nbsp;&nbsp;└ Strategy B: Layer Separation | H4 | 3 | 224 | 56 | reference |
| &nbsp;&nbsp;&nbsp;&nbsp;└ Strategy C: Pattern Extraction | H4 | 3 | 216 | 54 | reference |
| &nbsp;&nbsp;&nbsp;&nbsp;└ Strategy D: Decision vs. Implementation Split | H4 | 3 | 213 | 53 | reference |
| &nbsp;&nbsp;&nbsp;&nbsp;└ Strategy E: Interface-First Decomposition | H4 | 3 | 156 | 39 | reference |
| └ Step 4: Write Context Briefs | H3 | 29 | 3,285 | 821 | static |
| &nbsp;&nbsp;&nbsp;&nbsp;└ Small-edit brief mode | H4 | 14 | 1,769 | 442 | **conditional** |
| └ Step 5: Assign Models, Stacks, and Estimate | H3 | 37 | 2,214 | 553 | static |
| └ Step 6: Define Execution Order | H3 | 17 | 848 | 212 | static |
| └ Step 7: Classify Out-of-Scope Items (Backlog) | H3 | 21 | 1,267 | 316 | **conditional** |
| Output Format (template) | H2 | 7 | 147 | 36 | static |
| └ Overview | H2 | 3 | 85 | 21 | static |
| └ Cost Summary | H2 | 17 | 1,327 | 331 | static |
| └ Stack Distribution | H2 | 7 | 198 | 49 | static |
| └ Execution Waves (intro) | H2 | 2 | 19 | 4 | static |
| &nbsp;&nbsp;&nbsp;&nbsp;└ Wave 1 + Task 1.1/1.2 example | H3+H4 | 43 | 1,304 | 324 | static |
| &nbsp;&nbsp;&nbsp;&nbsp;└ Wave 2 + Task 2.1 example | H3+H4 | 6 | 145 | 35 | static |
| └ Integration Verification | H2 | 3 | 116 | 29 | static |
| └ Risk Notes | H2 | 4 | 140 | 35 | static |
| └ Deferred Items | H2 | 11 | 437 | 109 | conditional (paired with Step 7) |
| Decomposition Quality Checks | H2 | 74 | 4,439 | 1,109 | mixed (see below) |
| Common Mistakes to Avoid | H2 | 14 | 1,264 | 316 | reference |
| Handling Uncertainty | H2 | 8 | 589 | 147 | reference |
| Model Selection Quick Reference | H2 | 16 | 1,024 | 256 | **redundant** w/ Model Capability Reference |
| Output Budget | H2 | 17 | 914 | 228 | static |
| Plan Persistence and Output Protocol | H2 | 31 | 1,394 | 348 | static |
| **TOTAL** | | **541** | **32,747** | **8,186** | |

### Decomposition Quality Checks breakdown (within the 1,109-tok block)

| Subsection | ~Tok | Classification |
|---|---|---|
| Brief size gate (table + causes) | ~200 | static |
| Haiku/Sonnet/Opus checklists | ~210 | static |
| Wave-ordering validation (intro + 4 bullets) | ~280 | static |
| Broken-head split detection (option a/b + heuristic) | ~419 | **conditional** |

## Classification rationale

- **Static:** Read on every plan run. The planner needs these in working memory: philosophy, model capabilities, planning steps 1-6, output format template, output budget, plan persistence protocol.
- **Reference:** Looked up rather than internalized. The decomposition strategies (A-E) are patterns the planner consults when choosing how to split work; Common Mistakes is anti-pattern reminders; Handling Uncertainty is for probe-task scenarios.
- **Conditional (conditionally executed, not conditionally loaded):** the planner currently reads these on every run, but the *guidance* only fires under specific spec patterns. They are split candidates because their output behavior is gated, not because they're skipped. Conditions:
  - **Step 7 (Backlog)**: only when consumer repo opted in via `.github/pipeline-backlog.yml` sentinel. Detectable from `pipeline.config` (`BACKLOG_ENABLED`).
  - **Small-edit brief mode**: only when the planner identifies tasks fitting the small-edit profile (<20 lines change, single file). Detectable mid-planning, after Step 3.
  - **Broken-head split detection**: only when a logical change must split across waves AND modifies a public symbol. Detectable mid-planning.

## Token recovery estimate

### Strong split candidates (clearly conditional, cleanly extractable)

| Candidate | Tokens | Notes |
|---|---|---|
| Step 7 + Deferred Items section | 316 + 109 = **425** | Whole subsection plus the matched output template block; only fires when backlog opt-in |
| Small-edit brief mode | **442** | Subsection within Step 4; fires when small-edit detected |
| Broken-head split detection | **419** | Nested within Decomposition Quality Checks; fires when pattern detected |
| **Subtotal** | **~1,286** | |

### Weak/borderline candidates

| Candidate | Tokens | Notes |
|---|---|---|
| Common Mistakes to Avoid | 316 | Less clearly conditional; useful cargo-cult prevention every plan |
| Handling Uncertainty | 147 | Only for probe-task scenarios; could be reference |
| Decomposition strategies A-E | 266 | Reference patterns, but small enough to keep inline |
| **Subtotal** | **~729** | |

### Aggressive split total

Strong + weak = **~2,015 tokens**, above the 1,500 threshold. But this requires moving reference material that the planner would need to consciously re-load — adding cognitive load and risk of "forgot to read."

### Conservative split total (strong only)

**~1,286 tokens**, **below** the 1,500 threshold.

## Decision: NO-GO

The conservative split bundle (~1,286 tok) does not clear the issue's 1,500-token threshold. Reasons against pursuing the aggressive split:

1. **Two of the three strong candidates are nested inside larger sections.** "Small-edit brief mode" lives under Step 4; "broken-head split detection" lives under Decomposition Quality Checks. Cleanly extracting them requires reshaping their parents and risks breaking the surrounding flow.
2. **Conditional loading adds runtime fragility.** A planner agent that forgets to read `reference/small-edit.md` will silently produce verbose briefs for small tasks (the exact failure mode tracked in #59). The current always-loaded design is failure-resistant.
3. **The largest standalone savings is Step 7 + Deferred Items at ~425 tokens** — meaningful but not enough on its own to justify the structural change.
4. **The skill is the planner's primary instruction set.** Unlike `orchestrate/SKILL.md` (a procedural script with discrete steps that map cleanly to lazy-loaded files), `architect-planner/SKILL.md` is a continuous reasoning aid the planner consults throughout decomposition. The lazy-load pattern that worked for orchestrate doesn't transfer cleanly here.

## Opportunistic non-split wins (potential follow-up)

These can be picked up in a separate, smaller PR without the structural complexity of splitting:

| Item | Tokens recovered | Notes |
|---|---|---|
| **Consolidate Model Selection Quick Reference into Model Capability Reference** | ~256 | The two sections overlap on Haiku limits and pricing but serve different formats (capability inventory vs decision table). Consolidate into one canonical lookup at the top of the skill — keep the decision-table format, drop the second header and the duplicated content. |
| **Condense Cost Summary risk uplift heuristic** | ~200 | The 6-line explanation of folds/reviewer-drift uplift is useful but verbose; could be 3 lines. |
| **Total opportunistic recovery** | **~456** | |

These do not require splitting — just trimming redundancy and verbosity. Worth considering as a separate small-PR follow-up if the ~456-token saving is judged valuable.

## Files referenced

- `skills/architect-planner/SKILL.md` (the audited file)
- `agents/implementer-contract.md` (referenced by Step 4 and Decomposition Quality Checks; 14 lines / ~110 tok; out of scope per issue)

## Closing the issue

Per issue #76 acceptance criteria, this audit deliverable is the close condition. Filing this document closes #76. No follow-up implementation issue is opened — the decision is "do not split."

If the opportunistic wins (~456 tok across two non-split changes) are judged worth pursuing, file a new small-PR issue with that scope.
