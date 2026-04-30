# Contributing

How to extend the pipeline: write a new adapter, run the test suite.

## Writing a Custom Adapter

To add support for a new tech stack (e.g., Rust, Go, .NET):

### 1. Create the adapter directory

```bash
mkdir -p adapters/your-stack/scripts
```

### 2. Create the 10 required files

**`manifest.json`** — Machine-readable adapter descriptor:
```json
{
  "name": "your-stack",
  "display_name": "Your Language / Framework",
  "capabilities": [],
  "implies_overlays": [],
  "detection": [
    { "type": "file_exists", "path": "your-project-file" }
  ],
  "stack_paths": {
    "directories": ["src"],
    "fallback_globs": ["**/*.ext"]
  }
}
```
Detection rule types: `file_exists`, `file_contains` (with `pattern`), or glob paths. See existing adapters for examples.

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
- **Build:** `python3 .claude/scripts/<stack-name>/build.py [OPTIONS]`
- **Test:** `python3 .claude/scripts/<stack-name>/test.py [OPTIONS]`

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

**`implementer-overlay-essential.md`** — A compact, rules-only version of the implementer overlay (~500-800 chars, 8-12 bullet points, no examples). Used for Haiku tasks to maximize the signal-to-noise ratio. Include only the rules that, if violated, would fail code review. See existing adapters for reference.

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

Then run the structural validator on the pipeline repo:

```bash
python3 tests/validate_structure.py
```

It auto-discovers adapters from `manifest.json` files and checks all 10 required files, essential overlay size, and cross-references. No test file edits needed.

### 4. Add an adoption guide

For consistency with the other adapters, add `docs/adoption/<stack>.md` following the same structure as the existing guides (Detection → Tools → Bootstrap → Layout → Build/test → First `/orchestrate` run → Pitfalls → Issue filing). Link it from the README's adapter table.

### 5. Submit a PR

Contributions welcome for new adapters.

## Pipeline Self-Tests

The pipeline includes a 4-layer integration test suite that validates structural integrity, output contracts, and end-to-end bootstrap without making API calls.

### Running Tests

```bash
# Layer 1: Static validation — checks all files exist, markers present,
# cross-references resolve, overlays within size limits (~376 checks, instant)
python3 tests/validate_structure.py

# Layer 2: Dry-run mode — planned but not yet implemented.
# Will compose all prompts without launching agents for prompt validation.

# Layer 3: Contract tests — validates output protocol parsers against
# golden fixtures for all agent and script output formats (80 tests, instant)
python3 tests/test_contracts.py

# Layer 4: Smoke test — creates a temporary project, runs init.sh,
# validates bootstrap output, runs build/test scripts (30s, no API calls)
python3 tests/smoke/run_smoke.py

# Layer 4 (full): Same as above + runs full pipeline with a trivial task
# WARNING: Makes real API calls, costs ~$0.50-1.00
python3 tests/smoke/run_smoke.py --full
```

### What Each Layer Catches

| Failure Type | L1 Static | L3 Contract | L4 Smoke |
|---|---|---|---|
| Missing/renamed files | x | | |
| Overlay injection markers broken | x | | |
| Output protocol drift | x | x | |
| Essential overlay size regression | x | | |
| TOKEN_REPORT format changes | x | x | |
| Build/test script output parsing | | x | |
| init.sh bootstrap failures | | | x |
| Symlink resolution errors | | | x |
| Adapter hook merging | | | x |
| Agent quality degradation | | | x (full) |
| Defect report parsing errors | | x | |
| Fix-defects skill structure | x | | |
