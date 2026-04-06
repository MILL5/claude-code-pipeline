# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A tech-stack-agnostic orchestration system for Claude Code that coordinates planning, implementation, code review, testing, and git workflow through specialized agents. The pipeline itself has no build system or dependencies — it's a collection of agent definitions, skills, adapter overlays, and Python scripts that get symlinked into target projects via `init.sh`.

## Key Commands

**Bootstrap into a project (as submodule — recommended):**
```bash
cd your-project
git submodule add https://github.com/MILL5/claude-code-pipeline.git .claude/pipeline
bash .claude/pipeline/init.sh .
```
Auto-detects pipeline mode (submodule vs external clone) and creates relative symlinks. Auto-detects all applicable stacks from project files. Supports multiple `--stack` flags for multi-stack repos (e.g., `--stack=react --stack=python --stack=bicep`). Also auto-detects Azure SDK usage and activates the `azure-sdk` overlay when Azure packages are found in dependencies. Creates symlinks and config in the target project's `.claude/` directory.

**Bootstrap (external clone — legacy):**
```bash
bash /path/to/claude-code-pipeline/init.sh /path/to/project [--stack=<name>]... [--force]
```

**Run the pipeline** (from within a bootstrapped project):
```
/orchestrate
```

**Fix defects from PR comments** (from within a bootstrapped project):
```
/fix-defects
```
Reads structured defect reports from GitHub PR comments (see `templates/defect-report.md` for the schema) and runs the fix pipeline for each one.

**Update the pipeline** (from within a bootstrapped project):
```
/update-pipeline
```
Pulls latest pipeline submodule, shows changelog, validates structural integrity, re-runs `init.sh` if needed, and commits the submodule bump.

**Azure/Bicep skills** (from within a bootstrapped project):
```
/azure-login            # Verify Azure auth, subscription context, permissions
/validate-bicep        # Lint + build + optional what-if dry run
/deploy-bicep          # Deploy with mandatory confirmation gate
/azure-cost-estimate   # Estimate monthly Azure costs from Bicep
/security-scan         # PSRule/Checkov security scan
/infra-test-runner     # ARM-TTK/Pester infrastructure tests
/azure-drift-check     # Compare deployed state vs templates
```

**Build/test** (from within a bootstrapped project):
```bash
python3 .claude/scripts/<stack>/build.py [OPTIONS]
python3 .claude/scripts/<stack>/test.py [OPTIONS]
```

**Pipeline self-tests** (from the pipeline repo root):
```bash
python3 tests/validate_structure.py          # Layer 1: structural integrity (200 checks)
python3 tests/test_contracts.py              # Layer 3: output protocol contract tests (43 tests)
python3 tests/smoke/run_smoke.py             # Layer 4: bootstrap smoke test (init.sh + scripts)
python3 tests/smoke/run_smoke.py --full      # Layer 4: full pipeline smoke test (costs ~$0.50-1.00)
```
Layer 2 (dry-run mode for prompt composition validation) is planned but not yet implemented.

## Architecture

### Pipeline Flow

User request → **1a: Feature Clarification** (Sonnet, feature-only Q&A) → **1b: Implementation Clarification & Plan** (Sonnet default, Opus for novel architecture — implementation-specific Q&A then decomposition) → **1.5: Open Draft PR** → **2: Implement** (Haiku per task) → **2.1: Review** (Sonnet) → **2.2: Fix** (Sonnet) → **3: Commit & Push** → **3.5: Manual Test Loop** → **4: Finalize PR** → **5: Token Analysis** (mandatory)

### Three Layers

1. **Agents** (`agents/`) — Four generic, stack-agnostic agent definitions: `architect-agent`, `implementer-agent`, `code-reviewer-agent`, `test-architect-agent`. Each contains an `<!-- ADAPTER:TECH_STACK_CONTEXT -->` marker where adapter overlays get injected at launch. `implementer-contract.md` is the canonical Haiku readiness checklist referenced by both the planner and implementer.

2. **Skills** (`skills/`) — Seventeen pipeline steps. `orchestrate` is the master coordinator that invokes the core nine: `architect-analyzer`, `architect-planner`, `build-runner`, `test-runner`, `open-pr`, `summarize-implementation`, `token-analysis`. The standalone `fix-defects` skill reads structured defect reports from PR comments and runs the fix pipeline independently. `update-pipeline` manages submodule updates with validation and rollback. Seven Azure/Bicep skills provide IaC-specific capabilities: `azure-login` (auth pre-flight), `validate-bicep`, `deploy-bicep`, `azure-cost-estimate`, `security-scan`, `infra-test-runner`, `azure-drift-check`.

3. **Adapters** (`adapters/`) — Pluggable tech-stack modules (swift-ios, react, python, bicep). Multiple adapters can be active simultaneously for multi-stack repos. Each provides: `adapter.md` (metadata), four `*-overlay.md` files (injected into agents), `hooks.json` (blocks raw build/test commands), and `scripts/build.py` + `scripts/test.py` (runner scripts with strict output contracts). Each adapter also provides `implementer-overlay-essential.md` — a compact (~500-800 chars) rules-only variant used for Haiku tasks to improve signal-to-noise ratio.

### Cross-Cutting Overlays

In addition to adapters, the pipeline supports **cross-cutting overlays** (`overlays/`) that layer on top of any adapter. The `azure-sdk` overlay adds Azure SDK best practices (authentication, retry, Key Vault, managed identity) to any language adapter when the project uses Azure services. Overlays are auto-detected by `init.sh` (Azure packages in deps) and stored in `pipeline.config` as `overlays=azure-sdk`.

### How Adapter Injection Works

The orchestrator reads `.claude/pipeline.config` → loads all adapters from the `stacks` list into a **STACK_REGISTRY** → resolves each task's stack from its file paths via `stack_paths.*` patterns → injects the appropriate overlay(s) at the `<!-- ADAPTER:TECH_STACK_CONTEXT -->` marker.

**Injection strategy by agent role:**
- **Architect agents** (1a, 1b, blast-radius): receive ALL stacks' overlays so they can design cross-stack interactions
- **Implementer agents** (2, 2.2, 3.5): receive ONLY the task's stack overlay (resolved from file paths)
- **Reviewer agents** (2.1, 3.5): receive the union of stacks present in the current wave's tasks

If cross-cutting overlays are configured, their content is appended after the stack adapter overlay(s) at the same marker. For Haiku implementer tasks, the essential overlay variant is used instead of the full overlay.

### Local Overlays

Consumer repos can add project-specific overlays in `.claude/local/` that compose into agents after adapter and cross-cutting overlays. Four files: `project-overlay.md` (all agents), `coding-standards.md` (implementer + reviewer), `architecture-rules.md` (architect), `review-criteria.md` (reviewer). Created by `init.sh` from templates in `templates/local/`, committed to the consumer repo. The orchestrate skill loads them in Step 0.2. Empty or comment-only files are skipped during injection.

Conditional pipeline behavior (e.g., Azure authentication pre-flight) is driven by **capabilities** aggregated from adapter and overlay `manifest.json` files, not by checking stack names. This means adding a new adapter that declares `"capabilities": ["azure-auth"]` automatically triggers Azure auth without editing any skills.

### Model Assignment Strategy

- **Haiku** (~70%): Single-file, fully-specified mechanical tasks via implementer-agent and test-architect-agent
- **Sonnet** (~25%): Judgment tasks — code review, design decisions, fixes, analysis (step 1a), and planning for routine features (step 1b default)
- **Opus** (~5%): Planning for novel architecture, cross-cutting changes, or security-critical design (step 1b escalation only)

The planner's job is to decompose work so Haiku can execute it. Irreducibly complex tasks (algorithms, security, concurrency) escalate to Sonnet/Opus. Step 1b defaults to Sonnet — Opus is reserved for cases where the 1a-spec indicates novel architecture or cross-cutting complexity.

### Token Optimization

The orchestrator uses several strategies to reduce token consumption:
- **Sonnet-default planning**: Step 1b defaults to Sonnet instead of Opus, reducing planning cost by ~5x for routine features. Opus is reserved for novel architecture or cross-cutting complexity.
- **Brief-size gate**: The planner enforces token limits on context briefs (Haiku: 3K, Sonnet: 6K, Opus: 8K). Oversized briefs must be trimmed or split before implementation.
- **Wave batch cap**: Waves are capped at 4 tasks. The orchestrator splits larger waves into batches of ≤4, reducing blast radius and keeping agent calls under ~50K tokens.
- **Plan output budget**: Context briefs are capped at 400 tokens each; total plan output targets ≤4,000 tokens for ≤15-task features.
- **Scoped ORCHESTRATOR.md extracts**: Each agent receives only the sections it needs (1a gets fragile areas + architecture, 1b gets only sections NOT already in 1a-spec, 3.5 gets fragile areas only), not the full file. The 1b Extract excludes Architecture and Key Services/Modules since those are already embedded in the 1a-spec.
- **Essential overlay variants**: Haiku implementers receive a compact rules-only overlay (~500-800 chars) instead of the full overlay (~3,500 chars). The reviewer has the full overlay and catches violations.
- **Reviewer reuse**: Within a wave, one code-reviewer agent handles all reviews via SendMessage, avoiding re-ingestion of the agent definition and overlay per review (cap: 8 reviews per agent). Bug-fix reviews in Step 3.5 use the same reuse pattern.
- **Streaming reviews**: Reviews start as soon as each implementer completes, not after the full wave finishes. This overlaps review work with still-running implementer tasks.
- **Parallel bug fixes**: Independent bugs (non-overlapping file sets) found during manual testing can be fixed in parallel using worktree isolation.
- **Local overlay comment stripping**: HTML comment blocks are stripped from `.claude/local/` files before injection, so template placeholders don't waste tokens.
- **Background token analysis**: Step 5 (token analysis) runs in the background concurrently with Step 4 (PR finalization), reducing wall-clock time.
- **Cost-weighted distribution tracking**: Token analysis reports model distribution by dollar cost, not call count, preventing misleading metrics (e.g., "69% Haiku calls" masking 12% cost share).
- **TOKEN_REPORT**: All agents append a `---TOKEN_REPORT---` block to their output reporting files read from disk, tool calls, and self-assessed token consumption. This captures the ~43% of token usage invisible to the orchestrator's prompt-level tracking.

### Output Protocols

Agents communicate via structured output: implementer outputs `SUCCESS`/`FAILURE` + conventional-commit message + `TOKEN_REPORT`; code reviewer outputs `PASS`/`FAIL` + structured issues + `TOKEN_REPORT`; build/test scripts output summary lines with counts and coverage percentages.

### Recovery Artifacts

`.claude/tmp/1a-spec.md` and `.claude/tmp/1b-plan.md` are written during planning. If the pipeline is interrupted, it detects these and offers to resume.

## Writing a New Adapter

Create `adapters/<stack-name>/` with these 10 files: `manifest.json`, `adapter.md`, `architect-overlay.md`, `implementer-overlay.md`, `implementer-overlay-essential.md`, `reviewer-overlay.md`, `test-overlay.md`, `hooks.json`, `scripts/build.py`, `scripts/test.py`.

The `manifest.json` is the machine-readable adapter descriptor — it declares detection rules (how `init.sh` auto-detects this stack from project files), `stack_paths` (default glob patterns for file-to-stack mapping), `capabilities` (e.g., `["azure-auth"]` for stacks that require Azure CLI), and `implies_overlays` (e.g., `["azure-sdk"]`). See existing adapters for the schema. **No edits to `init.sh`, skills, or tests are needed when adding a new adapter** — the system discovers adapters from their `manifest.json` files.

The essential overlay is the compact Haiku variant (~500-800 chars, rules only, no examples). Follow existing adapters as reference. Build script must output `BUILD SUCCEEDED | N warning(s)` or `BUILD FAILED | ...`; test script must output `Summary: Total: N, Passed: N, Failed: N | Coverage: X.X%`.

## Project Files Generated by init.sh

In the target project's `.claude/`: symlink to `agents/`; `skills/` directory with per-skill symlinks to pipeline skills (local skills can be added as real directories here); `scripts/<stack>/` symlinks (one per active stack); optionally `overlays/` symlink (when Azure SDK detected); `pipeline.config` (stacks + stack_paths + capabilities + pipeline_version + pipeline_root + pipeline_mode + overlays); merged `settings.json` (PreToolUse hooks from all active adapters); `CLAUDE.md` and `ORCHESTRATOR.md` from templates; `local/` directory with project-specific overlay templates (`project-overlay.md`, `coding-standards.md`, `architecture-rules.md`, `review-criteria.md`); `tmp/` for recovery artifacts; `.gitignore` excluding pipeline-managed symlinks. All symlinks are relative for portability across machines.

## Local Skills

Projects can add their own skills alongside pipeline skills. Create a directory in `.claude/skills/<name>/` with a `SKILL.md` file following the standard skill format. Pipeline skill symlinks are auto-excluded via `.claude/skills/.gitignore`; local skill directories are committed to the project repo and available via `/skill-name` in Claude Code.
