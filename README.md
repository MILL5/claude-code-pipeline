# Claude Code Pipeline

A general-purpose, tech-stack-agnostic orchestration pipeline for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Coordinates planning, implementation, code review, testing, and git workflow through specialized agents — across any language or framework.

## Why This Exists

Claude Code is powerful, but complex multi-file features benefit from structured coordination. Without it, you get:
- Implementations that drift from requirements
- Code that ships without review
- Regressions that slip through because tests weren't run
- Commits with inconsistent messages and no traceability

This pipeline enforces a disciplined workflow: **clarify -> plan -> implement -> review -> test -> commit -> manual verify -> finalize**. Every step is handled by a specialized agent with the right model (Haiku for mechanical tasks, Sonnet for judgment, Opus for architecture) — optimizing both quality and cost.

The pipeline is **tech-stack-agnostic**. The core workflow is identical whether you're building a Swift/iOS app, a React frontend, or a Python API. Stack-specific knowledge (build commands, code review rules, testing patterns) lives in **adapters** that get injected at runtime.

## Pipeline Flow

```
User: "Add feature X" or /orchestrate
    |
    v
Step 1a: ANALYZE & CLARIFY ──────────────── architect-agent (Sonnet)
    |  Seam analysis across layers/platforms
    |  Fragile area scan against ORCHESTRATOR.md
    |  Iterative clarifying questions (max 3 rounds)
    |  Output: .claude/tmp/1a-spec.md (enriched spec)
    v
Step 1b: PLAN ────────────────────────────── architect-agent (Opus, fresh context)
    |  Reads enriched spec + ORCHESTRATOR.md (~15K tokens clean)
    |  Cost-optimized decomposition: >=70% Haiku tasks
    |  Self-contained context briefs per task
    |  Parallel waves with dependency ordering
    |  Output: .claude/tmp/1b-plan.md (recovery artifact)
    |  User confirms plan before proceeding
    v
Step 1.5: OPEN PR ────────────────────────── orchestrator
    |  Create feature branch from main
    |  Open draft PR with plan summary + task checklist
    v
Step 2: IMPLEMENT ────────────────────────── implementer-agent (Haiku/Sonnet/Opus)
    |  One agent per task, parallel within waves
    |  Each: implement -> self-review -> build -> test (>=90% coverage)
    |  Output: SUCCESS + commit message  OR  FAILURE + details
    v
Step 2.1: REVIEW ─────────────────────────── code-reviewer-agent (Sonnet)
    |  Aggressive review: memory leaks, race conditions, security, architecture
    |  Output: PASS  OR  FAIL + structured issues list
    v
Step 2.2: FIX (if FAIL) ─────────────────── implementer-agent (Sonnet, escalated)
    |  Fix reviewer findings, re-build, re-test
    |  Max 2 review-fix cycles, then escalate to user
    v
Step 3: COMMIT + PUSH ───────────────────── orchestrator
    |  Commit per task with implementer's message verbatim
    |  Push after each commit (progress visible on draft PR)
    |  Record test baseline (total passing count)
    v
Step 3.5: MANUAL TEST ───────────────────── user + orchestrator
    |  User tests the PR branch, reports bugs
    |  Each bug: assess blast radius -> fix -> review -> commit
    |  Regression guard: test count must never decrease
    |  Max 3 fix cycles per round, then escalate
    v
Step 4: FINALIZE ─────────────────────────── orchestrator
    |  Update ORCHESTRATOR.md if architecture changed
    |  Update PR body with coverage numbers
    |  Mark PR ready for review
    |  Report: PR URL, tasks completed, coverage summary
    v
User merges when ready (pipeline never auto-merges)
```

## Quick Start

### 1. Clone the pipeline into your project

```bash
cd your-project
git clone https://github.com/swtarmey/claude-code-pipeline.git .claude/pipeline
```

Or add as a git submodule for version-pinned updates:

```bash
git submodule add https://github.com/swtarmey/claude-code-pipeline.git .claude/pipeline
```

### 2. Bootstrap

```bash
# Auto-detect your tech stack
bash .claude/pipeline/init.sh .

# Or specify explicitly
bash .claude/pipeline/init.sh . --stack=swift-ios
bash .claude/pipeline/init.sh . --stack=react
bash .claude/pipeline/init.sh . --stack=python
```

The init script:
1. Detects your tech stack from project files (Package.swift, package.json, pyproject.toml, etc.)
2. Creates symlinks: `.claude/agents/` -> pipeline agents, `.claude/skills/` -> pipeline skills, `.claude/scripts/` -> adapter scripts
3. Writes `.claude/pipeline.config` with your stack and pipeline path
4. Merges adapter hooks into `.claude/settings.json`
5. Generates `.claude/CLAUDE.md` and `.claude/ORCHESTRATOR.md` from templates (if they don't exist)

### 3. Configure your project

Edit the generated files:

- **`.claude/CLAUDE.md`** — Set your developer persona, project description, and any project-specific workflow rules
- **`.claude/ORCHESTRATOR.md`** — Document your architecture, services, directory structure, conventions, fragile areas, and current build/test status

These are your project's living documentation. The pipeline reads them before every operation.

### 4. Run the pipeline

Start Claude Code in your project directory:

```bash
claude
```

Then use any of these to trigger the pipeline:

- `/orchestrate` — Full pipeline run
- "implement X" / "add feature X" / "fix bug Y" — Auto-triggers orchestration
- "build" / "implement" / "add feature" — Also triggers

## Available Adapters

| Adapter | Auto-Detects | Build Tool | Test Framework | Coverage |
|---------|-------------|------------|----------------|----------|
| `swift-ios` | `*.xcodeproj`, `*.xcworkspace`, `Package.swift` | Xcode / Swift PM | XCTest | xccov |
| `react` | `package.json` with `react` dependency | npm/yarn/pnpm/bun + tsc | Jest / Vitest | istanbul / v8 |
| `python` | `pyproject.toml`, `setup.py`, `requirements.txt` | mypy + ruff | pytest | pytest-cov |

### What Each Adapter Provides

Every adapter includes 8 files:

| File | Purpose |
|------|---------|
| `adapter.md` | Stack metadata: name, languages, build/test commands, blocked commands, conventions |
| `architect-overlay.md` | Framework-specific complexity patterns for task decomposition and model assignment |
| `implementer-overlay.md` | Language-specific code quality rules injected into the implementer agent |
| `reviewer-overlay.md` | Stack-specific code review checklist (8 categories per adapter) |
| `test-overlay.md` | Testing framework patterns, assertion conventions, mocking strategies |
| `hooks.json` | PreToolUse hooks that block raw build/test commands (forces pipeline skill usage) |
| `scripts/build.py` | Build runner matching the pipeline's output contract |
| `scripts/test.py` | Test runner matching the pipeline's output contract |

## Architecture

### Agents

The pipeline uses 4 specialized agents, each with a focused role:

| Agent | Default Model | Role |
|-------|--------------|------|
| `architect-agent` | Opus | Requirements analysis (1a) and cost-optimized plan generation (1b) |
| `implementer-agent` | Haiku | Executes individual tasks from context briefs. Escalates to Sonnet for fixes. |
| `code-reviewer-agent` | Sonnet | Aggressive code review with PASS/FAIL protocol |
| `test-architect-agent` | Haiku | Generates comprehensive test suites for coverage gaps |

Agents are **generic** — they contain no tech-stack-specific knowledge. Stack context is injected by the orchestrator at launch time via overlay markers (`<!-- ADAPTER:TECH_STACK_CONTEXT -->`).

### Skills

| Skill | Trigger | Purpose |
|-------|---------|---------|
| `orchestrate` | `/orchestrate`, "implement", "add feature", "fix bug" | Master pipeline coordinator |
| `architect-analyzer` | Step 1a (via orchestrator) | Requirements clarification and enriched spec generation |
| `architect-planner` | Step 1b (via orchestrator) | Cost-optimized task decomposition into waves |
| `build-runner` | "build", "compile", "does it build" | Delegates to adapter's `build.py` script |
| `test-runner` | "run tests", "check tests", "validate" | Delegates to adapter's `test.py` script |
| `open-pr` | Step 1.5 (via orchestrator) or "open a PR" | Creates feature branch + draft PR |
| `summarize-implementation` | After implementation tasks | Generates conventional-commit messages |

### Adapter Injection Flow

```
Orchestrator reads .claude/pipeline.config
    |
    v
Loads adapters/<stack>/adapter.md (metadata)
    |
    v
For each agent launch:
    1. Read generic agent definition (agents/<name>.md)
    2. Read relevant overlay (adapters/<stack>/<name>-overlay.md)
    3. Insert overlay at <!-- ADAPTER:TECH_STACK_CONTEXT --> marker
    4. Pass composed prompt to Agent tool
```

This means:
- **Updating the pipeline** (git pull) immediately updates all projects using it
- **Switching stacks** only requires re-running `init.sh --stack=new-stack`
- **Custom overlays** can be added without modifying core pipeline files

### Cost Optimization

The pipeline is designed to minimize Claude API costs:

- **Haiku for mechanical tasks**: Single-file implementations with fully specified briefs (~$0.005-0.02 per task)
- **Sonnet for judgment**: Code review, design decisions, multi-file consistency (~$0.03-0.15 per task)
- **Opus for architecture**: Plan generation, novel algorithm design (~$0.10-0.50 per task)
- **Clean context windows**: Fresh agents for each pipeline step prevent context accumulation
- **File-based handoff**: Enriched spec written to disk between 1a and 1b (avoids carrying Q&A history into planning)

A typical feature plan targets **>=70% Haiku tasks**, making the mixed strategy significantly cheaper than running everything on Sonnet or Opus.

## Project Structure

```
claude-code-pipeline/
|-- init.sh                              # Bootstrap script
|-- README.md
|
|-- agents/                              # Generic agent definitions
|   |-- architect-agent.md               # Plans features, routes to analyzer/planner skills
|   |-- implementer-agent.md             # Executes tasks from context briefs
|   |-- code-reviewer-agent.md           # Aggressive code review (PASS/FAIL)
|   +-- test-architect-agent.md          # Generates test suites
|
|-- skills/                              # Generic skill definitions
|   |-- orchestrate/SKILL.md             # Master pipeline (446 lines)
|   |-- architect-analyzer/SKILL.md      # Step 1a: requirements clarification
|   |-- architect-planner/SKILL.md       # Step 1b: cost-optimized decomposition
|   |-- build-runner/SKILL.md            # Delegates to adapter build script
|   |-- test-runner/SKILL.md             # Delegates to adapter test script
|   |-- open-pr/SKILL.md                 # Branch + draft PR creation
|   +-- summarize-implementation/SKILL.md # Conventional commit messages
|
|-- adapters/
|   |-- swift-ios/                       # Apple ecosystem adapter
|   |   |-- adapter.md                   # Xcode, XCTest, xccov
|   |   |-- architect-overlay.md         # Apple framework complexity patterns
|   |   |-- implementer-overlay.md       # Swift code quality, @MainActor, MVVM
|   |   |-- reviewer-overlay.md          # Memory leaks, retain cycles, battery
|   |   |-- test-overlay.md              # XCTest patterns, actor isolation
|   |   |-- hooks.json                   # Block xcodebuild, swift build
|   |   +-- scripts/
|   |       |-- build.py                 # Xcode build runner (209 lines)
|   |       +-- test.py                  # XCTest runner + simulator mgmt (830 lines)
|   |
|   |-- react/                           # React/TypeScript adapter
|   |   |-- adapter.md                   # npm/yarn/pnpm, Jest/Vitest
|   |   |-- architect-overlay.md         # Component hierarchy, state management
|   |   |-- implementer-overlay.md       # TypeScript strict, hooks rules, JSX
|   |   |-- reviewer-overlay.md          # Re-renders, XSS, bundle size, a11y
|   |   |-- test-overlay.md              # RTL patterns, mocking, snapshots
|   |   |-- hooks.json                   # Block npm test, npx jest
|   |   +-- scripts/
|   |       |-- build.py                 # tsc + build script runner
|   |       +-- test.py                  # Jest/Vitest runner with coverage
|   |
|   +-- python/                          # Python adapter
|       |-- adapter.md                   # pip/poetry/uv, pytest, mypy/ruff
|       |-- architect-overlay.md         # Module decomposition, async, Django/FastAPI
|       |-- implementer-overlay.md       # Type hints, dataclasses, PEP conventions
|       |-- reviewer-overlay.md          # GIL, security, resource management
|       |-- test-overlay.md              # pytest fixtures, parametrize, async
|       |-- hooks.json                   # Block pytest, mypy directly
|       +-- scripts/
|           |-- build.py                 # mypy + ruff runner
|           +-- test.py                  # pytest runner with coverage
|
+-- templates/                           # Project file templates
    |-- CLAUDE.md.template               # Starting point for project CLAUDE.md
    |-- ORCHESTRATOR.md.template         # Starting point for project ORCHESTRATOR.md
    +-- pipeline.config.template         # Config file format reference
```

## How-To Guide

### Running the Full Pipeline

1. Start Claude Code: `claude`
2. Describe your feature: "Add user authentication with JWT tokens"
3. The pipeline automatically:
   - Analyzes your request and asks clarifying questions (1a)
   - Generates a cost-optimized plan with parallel waves (1b)
   - Presents the plan for your approval
   - Opens a draft PR
   - Implements each task with build + test verification
   - Reviews every implementation
   - Commits with conventional-commit messages
   - Asks you to manually test
   - Fixes any bugs you report
   - Finalizes the PR

### Running Individual Skills

You don't have to use the full pipeline. Individual skills work standalone:

```
/build-runner                    # Build the project
/test-runner                     # Run tests with coverage
/open-pr                         # Create a branch + draft PR
/summarize-implementation        # Generate a commit message from current diff
```

### Updating the Pipeline

If cloned directly:
```bash
cd your-project/.claude/pipeline
git pull origin main
```

If using a submodule:
```bash
git submodule update --remote .claude/pipeline
```

Updates take effect immediately — no re-init needed (symlinks point to the pipeline repo).

Re-run `init.sh --force` only if:
- You want to switch adapters (`--stack=different-stack`)
- The pipeline added new directories that need symlinking
- Hook structure changed and needs re-merging

### Resuming After Interruption

The pipeline creates recovery artifacts:
- `.claude/tmp/1a-spec.md` — Enriched spec from analysis (skips re-analysis)
- `.claude/tmp/1b-plan.md` — Full plan from Opus (skips expensive re-planning)

If interrupted, just say `/orchestrate` again. The pipeline detects existing artifacts and offers to resume.

### Manual Testing Feedback Loop

After implementation, the pipeline enters a manual testing phase:

1. You test the PR branch
2. Report bugs: "The timer doesn't start when I tap the button"
3. The orchestrator:
   - Assesses blast radius (simple vs complex fix)
   - Launches architect for complex bugs touching fragile areas
   - Fixes via implementer agent (Sonnet for fixes)
   - Reviews the fix
   - Runs full test suite with regression guard (test count must not drop)
   - Commits and pushes
4. You re-test
5. Say "tests pass" when satisfied

**Regression guards** prevent fixes from breaking other things:
- Test count baseline is recorded after initial implementation
- Every fix must maintain or increase the test count
- If a fix drops the count, it's rejected automatically
- After 3 fix cycles, the pipeline escalates to you for manual triage

## Writing a Custom Adapter

To add support for a new tech stack (e.g., Rust, Go, Java):

### 1. Create the adapter directory

```bash
mkdir -p adapters/your-stack/scripts
```

### 2. Create the 8 required files

**`adapter.md`** — Stack metadata following this structure:
```markdown
# Your Stack Adapter

## Stack Metadata
- **Stack name:** `your-stack`
- **Display name:** Your Language / Framework
- **Languages:** Your Language
- **Build system:** Your build tool
- **Test framework:** Your test framework
- **Coverage tool:** Your coverage tool

## Build & Test Commands
- **Build:** `python3 .claude/scripts/build.py [OPTIONS]`
- **Test:** `python3 .claude/scripts/test.py [OPTIONS]`

## Blocked Commands
- `your-build-cmd` -> use `build-runner` skill
- `your-test-cmd` -> use `test-runner` skill

## Project Detection
This adapter activates when the project root contains:
- `your-project-file` (e.g., Cargo.toml, go.mod, pom.xml)

## Common Conventions
- Your language/framework conventions here
```

**Overlay files** — Provide stack-specific content for each agent. Look at existing adapters for the pattern. Each overlay is injected at `<!-- ADAPTER:TECH_STACK_CONTEXT -->` markers in the generic agents.

**`hooks.json`** — Block raw build/test commands:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "your hook logic here",
            "timeout": 5,
            "statusMessage": "Checking for forbidden commands..."
          }
        ]
      }
    ]
  }
}
```

**`scripts/build.py`** — Must conform to this output contract:
```
BUILD SUCCEEDED  |  N warning(s)
```
or:
```
BUILD FAILED  |  N error(s)  |  N warning(s)

File                          Ln  Error
-----------------------------------------------------------
path/to/file.ext              42  description of error
```
Exit code: 0 = success, 1 = failure.

**`scripts/test.py`** — Must conform to this output contract:
```
Summary: Total: N, Passed: N, Failed: N | Coverage: X.X%

Coverage:  Target1: X.X%  |  Target2: X.X%

All tests passed.
```
Exit code: 0 = all pass, 1 = failures.

### 3. Test it

```bash
bash init.sh /path/to/your-project --stack=your-stack
```

### 4. Submit a PR

Contributions welcome for new adapters.

## Configuration Reference

### `.claude/pipeline.config`

```ini
# Active tech-stack adapter
stack=react

# Absolute path to the pipeline repo
pipeline_root=/path/to/claude-code-pipeline

# Date this config was generated
initialized=2026-03-29T00:00:00Z
```

### `.claude/settings.json`

Generated by `init.sh` from the adapter's `hooks.json`. Contains PreToolUse hooks that:
- Block raw build/test commands (forces use of pipeline skills)
- Block `grep`/`cat`/`find`/`sed` via Bash (forces use of Grep/Read/Glob/Edit tools)

You can add project-specific hooks alongside the pipeline hooks.

### `.claude/CLAUDE.md`

Your project's instructions for Claude Code. The template provides a starting structure. Key sections to customize:
- **Role**: Your developer persona ("senior React developer", "Python backend engineer")
- **Context**: What your project does
- **Workflow Rules**: Project-specific rules (the template includes sensible defaults)
- **Build & Test**: Already configured by init.sh to use pipeline skills

### `.claude/ORCHESTRATOR.md`

Your project's living architecture document. The template provides the full structure. Key sections:
- **Targets**: Your build targets/entry points
- **Architecture**: How your code is organized (MVVM, hexagonal, etc.)
- **Key Services**: What does what
- **Conventions**: Naming, patterns, error handling
- **Known Fragile Areas**: Parts of the codebase that need extra care
- **Current State**: Build/test status, updated after each pipeline run

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI (latest version)
- [GitHub CLI](https://cli.github.com/) (`gh`) — for PR management
- Python 3.8+ — for build/test runner scripts
- `jq` — for hook merging during init (optional but recommended)
- Stack-specific tools:
  - **swift-ios**: Xcode 15+, `xcrun`, iOS/watchOS simulators
  - **react**: Node.js 18+, npm/yarn/pnpm/bun
  - **python**: Python 3.9+, pip/poetry/uv

## FAQ

**Q: Can I use individual agents without the full pipeline?**
Yes. The agents work standalone. For example, launch `code-reviewer-agent` directly on your recent changes, or use `test-architect-agent` to generate tests for a specific file.

**Q: What if my project uses multiple stacks?**
The pipeline supports one adapter at a time. For monorepos with multiple stacks, you could either use the dominant stack's adapter or create a custom adapter that combines overlays. Multi-adapter support is a potential future enhancement.

**Q: Does the pipeline support CI/CD integration?**
The pipeline runs locally via Claude Code. It creates PRs that your CI/CD system can pick up normally. The pipeline itself doesn't run in CI.

**Q: How do I update ORCHESTRATOR.md?**
The pipeline updates it automatically in Step 4 when architecture changes. You should also update it manually when making significant changes outside the pipeline, so the architect has accurate context.

**Q: What's the cost per feature?**
Varies by complexity. A typical 8-task feature (6 Haiku + 2 Sonnet) costs roughly $0.15-0.40 in API usage, compared to $0.90-2.00 if everything ran on Opus. The architect's plan includes a cost estimate before you approve.

## License

MIT
