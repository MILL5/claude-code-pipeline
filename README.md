# Claude Code Pipeline

A general-purpose, tech-stack-agnostic orchestration pipeline for Claude Code. Coordinates planning, implementation, code review, testing, and git workflow through specialized agents.

## Overview

This pipeline provides a structured, multi-stage workflow for software development:

```
User Request
    |
    v
Step 1a: ANALYZE & CLARIFY (architect agent, Sonnet)
    |  Seam analysis, clarifying questions, enriched spec
    v
Step 1b: PLAN (architect agent, Opus)
    |  Cost-optimized task decomposition into Haiku-executable tasks
    v
Step 1.5: OPEN PR (draft PR on GitHub)
    v
Step 2: IMPLEMENT (implementer agents, parallel waves)
    |  Each: implement -> self-review -> build -> test (>=90% coverage)
    v
Step 2.1: REVIEW (code-reviewer agent)
    v
Step 3: COMMIT + PUSH
    v
Step 3.5: MANUAL TEST (user feedback loop with regression guards)
    v
Step 4: FINALIZE (update docs, mark PR ready)
```

## Quick Start

```bash
# Clone into your project
cd your-project
git clone <repo-url> .claude/pipeline

# Bootstrap (auto-detects tech stack)
bash .claude/pipeline/init.sh .

# Or specify the stack explicitly
bash .claude/pipeline/init.sh . --stack=swift-ios
bash .claude/pipeline/init.sh . --stack=react
bash .claude/pipeline/init.sh . --stack=python
```

After init, start Claude Code in your project and use `/orchestrate` to run the full pipeline.

## Available Adapters

| Adapter | Detects | Build Tool | Test Tool |
|---------|---------|------------|-----------|
| `swift-ios` | `*.xcodeproj`, `*.xcworkspace`, `Package.swift` | Xcode / Swift PM | XCTest |
| `react` | `package.json` with React dependency | npm/yarn/pnpm + TypeScript | Jest / Vitest |
| `python` | `pyproject.toml`, `setup.py`, `requirements.txt` | mypy + ruff | pytest |

## Project Structure

```
claude-code-pipeline/
├── init.sh                     # Bootstrap script
├── agents/                     # Generic agent definitions
│   ├── architect-agent.md
│   ├── implementer-agent.md
│   ├── code-reviewer-agent.md
│   └── test-architect-agent.md
├── skills/                     # Generic skill definitions
│   ├── orchestrate/SKILL.md
│   ├── architect-analyzer/SKILL.md
│   ├── architect-planner/SKILL.md
│   ├── open-pr/SKILL.md
│   ├── summarize-implementation/SKILL.md
│   ├── build-runner/SKILL.md
│   └── test-runner/SKILL.md
├── adapters/                   # Tech-stack adapters
│   ├── swift-ios/
│   ├── react/
│   └── python/
└── templates/                  # Project file templates
```

## How Adapters Work

Adapters provide tech-stack-specific knowledge that gets injected into generic agents at runtime. Each adapter contains:

- **`adapter.md`** — Stack metadata, build/test commands, conventions
- **`*-overlay.md`** — Stack-specific content injected into each agent type
- **`hooks.json`** — PreToolUse hooks that enforce using pipeline skills over raw commands
- **`scripts/`** — Build and test runner scripts matching the pipeline's output contract

The orchestrator reads `.claude/pipeline.config` to determine the active adapter, then composes agent prompts by merging the generic agent definition with the adapter's overlay content.

## Writing a Custom Adapter

Create a new directory under `adapters/` with these files:

1. `adapter.md` — Follow the format in any existing adapter
2. `implementer-overlay.md` — Code quality rules for your language/framework
3. `reviewer-overlay.md` — Code review checklist for your stack
4. `test-overlay.md` — Testing framework patterns and conventions
5. `architect-overlay.md` — Architecture patterns and framework complexity guidance
6. `hooks.json` — Commands to block (force using pipeline skills)
7. `scripts/build.py` — Must accept `--project-dir`, exit 0/1, print `BUILD SUCCEEDED`/`BUILD FAILED`
8. `scripts/test.py` — Must accept `--project-dir`, `--no-coverage`, exit 0/1, print `Summary:` line

Run `bash init.sh /path/to/project --stack=your-adapter` to activate.

## Requirements

- [Claude Code](https://claude.ai/claude-code) CLI
- [GitHub CLI](https://cli.github.com/) (`gh`) for PR management
- Python 3.8+ (for build/test scripts)
- Stack-specific tools (Xcode, Node.js, Python, etc.)
