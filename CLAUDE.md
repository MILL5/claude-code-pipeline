# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A tech-stack-agnostic orchestration system for Claude Code that coordinates planning, implementation, code review, testing, and git workflow through specialized agents. The pipeline itself has no build system or dependencies — it's a collection of agent definitions, skills, adapter overlays, and Python scripts that get symlinked into target projects via `init.sh`.

## Key Commands

**Bootstrap into a project:**
```bash
bash init.sh /path/to/project [--stack=swift-ios|react|python] [--force]
```
Auto-detects stack from project files. Creates symlinks and config in the target project's `.claude/` directory.

**Run the pipeline** (from within a bootstrapped project):
```
/orchestrate
```

**Build/test** (from within a bootstrapped project):
```bash
python3 .claude/scripts/build.py [OPTIONS]
python3 .claude/scripts/test.py [OPTIONS]
```

**Pipeline self-tests** (from the pipeline repo root):
```bash
python3 tests/validate_structure.py          # Layer 1: structural integrity (147 checks)
python3 tests/test_contracts.py              # Layer 3: output protocol contract tests (24 tests)
python3 tests/smoke/run_smoke.py             # Layer 4: bootstrap smoke test (init.sh + scripts)
python3 tests/smoke/run_smoke.py --full      # Layer 4: full pipeline smoke test (costs ~$0.50-1.00)
```
Layer 2 (dry-run mode for prompt composition validation) is planned but not yet implemented.

## Architecture

### Pipeline Flow

User request → **1a: Analyze & Clarify** (Sonnet) → **1b: Plan** (Opus) → **1.5: Open Draft PR** → **2: Implement** (Haiku per task) → **2.1: Review** (Sonnet) → **2.2: Fix** (Sonnet) → **3: Commit & Push** → **3.5: Manual Test Loop** → **4: Finalize PR** → **5: Token Analysis** (mandatory)

### Three Layers

1. **Agents** (`agents/`) — Four generic, stack-agnostic agent definitions: `architect-agent`, `implementer-agent`, `code-reviewer-agent`, `test-architect-agent`. Each contains an `<!-- ADAPTER:TECH_STACK_CONTEXT -->` marker where adapter overlays get injected at launch. `implementer-contract.md` is the canonical Haiku readiness checklist referenced by both the planner and implementer.

2. **Skills** (`skills/`) — Eight pipeline steps. `orchestrate` is the master coordinator that invokes all others: `architect-analyzer`, `architect-planner`, `build-runner`, `test-runner`, `open-pr`, `summarize-implementation`, `token-analysis`.

3. **Adapters** (`adapters/`) — Pluggable tech-stack modules (swift-ios, react, python). Each provides: `adapter.md` (metadata), four `*-overlay.md` files (injected into agents), `hooks.json` (blocks raw build/test commands), and `scripts/build.py` + `scripts/test.py` (runner scripts with strict output contracts). Each adapter also provides `implementer-overlay-essential.md` — a compact (~500-800 chars) rules-only variant used for Haiku tasks to improve signal-to-noise ratio.

### How Adapter Injection Works

The orchestrator reads `.claude/pipeline.config` → loads `adapters/<stack>/adapter.md` → for each agent launch, reads the generic agent + the relevant overlay → inserts overlay at the `<!-- ADAPTER:TECH_STACK_CONTEXT -->` marker → passes composed prompt to the Agent tool. For Haiku implementer tasks, the essential overlay variant is used instead of the full overlay.

### Model Assignment Strategy

- **Haiku** (~70%): Single-file, fully-specified mechanical tasks via implementer-agent and test-architect-agent
- **Sonnet** (~20%): Judgment tasks — code review, design decisions, fixes, analysis (step 1a)
- **Opus** (~10%): Architecture and planning (step 1b)

The planner's job is to decompose work so Haiku can execute it. Irreducibly complex tasks (algorithms, security, concurrency) escalate to Sonnet/Opus.

### Token Optimization

The orchestrator uses several strategies to reduce token consumption:
- **Scoped ORCHESTRATOR.md extracts**: Each agent receives only the sections it needs (1a gets fragile areas + architecture, 1b gets conventions + data flow, 3.5 gets fragile areas only), not the full file.
- **Essential overlay variants**: Haiku implementers receive a compact rules-only overlay (~500-800 chars) instead of the full overlay (~3,500 chars). The reviewer has the full overlay and catches violations.
- **Reviewer reuse**: Within a wave, one code-reviewer agent handles all reviews via SendMessage, avoiding re-ingestion of the agent definition and overlay per review (cap: 8 reviews per agent).
- **TOKEN_REPORT**: All agents append a `---TOKEN_REPORT---` block to their output reporting files read from disk, tool calls, and self-assessed token consumption. This captures the ~43% of token usage invisible to the orchestrator's prompt-level tracking.

### Output Protocols

Agents communicate via structured output: implementer outputs `SUCCESS`/`FAILURE` + conventional-commit message + `TOKEN_REPORT`; code reviewer outputs `PASS`/`FAIL` + structured issues + `TOKEN_REPORT`; build/test scripts output summary lines with counts and coverage percentages.

### Recovery Artifacts

`.claude/tmp/1a-spec.md` and `.claude/tmp/1b-plan.md` are written during planning. If the pipeline is interrupted, it detects these and offers to resume.

## Writing a New Adapter

Create `adapters/<stack-name>/` with these 9 files: `adapter.md`, `architect-overlay.md`, `implementer-overlay.md`, `implementer-overlay-essential.md`, `reviewer-overlay.md`, `test-overlay.md`, `hooks.json`, `scripts/build.py`, `scripts/test.py`. The essential overlay is the compact Haiku variant (~500-800 chars, rules only, no examples). Follow existing adapters as reference. Build script must output `BUILD SUCCEEDED | N warning(s)` or `BUILD FAILED | ...`; test script must output `Summary: Total: N, Passed: N, Failed: N | Coverage: X.X%`.

## Project Files Generated by init.sh

In the target project's `.claude/`: symlinks to `agents/`, `skills/`, `scripts/`; `pipeline.config` (stack + pipeline path); merged `settings.json` (PreToolUse hooks from adapter); `CLAUDE.md` and `ORCHESTRATOR.md` from templates; `tmp/` for recovery artifacts.
