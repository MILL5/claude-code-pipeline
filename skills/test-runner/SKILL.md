---
name: test-runner
description: "MANDATORY SKILL: Run project tests. Use EXCLUSIVELY instead of running test commands directly. This is not optional — violation breaks the build pipeline. Triggers on: run tests, run unit tests, check tests, did tests pass, execute tests, validate implementation, or any implicit need to verify correctness after code changes. If you use Bash to run test commands directly, you have violated a critical constraint."
---

# Test Runner

Runs project tests via the adapter's test script and outputs a minimal results table to minimize context consumption for agents reading the output.

## When to Use

Use this skill **instead of** running test commands directly. Always invoke this after:
- Completing an implementation
- Fixing a bug
- Refactoring code
- Any scenario where test validation is appropriate

## How to Run

```bash
python3 .claude/scripts/<stack>/test.py [OPTIONS]
```

Replace `<stack>` with the tech stack being tested (e.g., `react`, `python`, `bicep`, `swift-ios`).
For single-stack projects, there is only one subdirectory. For multi-stack projects, run the
test script matching the stack of the files you modified.

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--project-dir` | `.` (cwd) | Path to project root |
| `--scheme` | auto | Test target/scheme name (if applicable) |
| `--no-coverage` | off | Disable code coverage collection (faster, no coverage report) |
| `--exclude-from-coverage` | none | Glob patterns for files to exclude from coverage |

**Examples:**
```bash
# Single-stack project
python3 .claude/scripts/react/test.py

# Multi-stack: test specific stack
python3 .claude/scripts/python/test.py

# Specific test target
python3 .claude/scripts/swift-ios/test.py --scheme MyAppTests

# Skip coverage for a faster run
python3 .claude/scripts/react/test.py --no-coverage

# Exclude files from coverage calculation
python3 .claude/scripts/react/test.py --exclude-from-coverage '*View.*' '*/views/*'
```

## Output Contract

All adapter test scripts MUST conform to this output format:

**All-passing run with coverage:**
```
Summary: Total: 682, Passed: 682, Failed: 0 | Coverage: 74.3%

Coverage:  Target1: 74.3%  |  Target2: 68.1%

All tests passed.
```

**Run with failures:**
```
Summary: Total: 14, Passed: 12, Failed: 2 | Coverage: 71.2%

Coverage:  Target1: 71.2%

Class              Test                    Time
-----------------------------------------------
AuthTests          testTokenRefresh       0.034s
   L assertion message or failure reason
NetworkTests       testRetryLogic         0.101s
   L assertion message or failure reason
```

- `Summary:` line always appears first — include it verbatim when reporting results
- Coverage is collected by default and parsed from the test framework's output
- Coverage excludes test files — only application code is counted
- Failure rows show the assertion message (truncated to 160 chars)
- Exit code 0 = all passed, 1 = failures or build error

## Build Errors

If the build fails before tests can run, the last 30 lines of output are shown so
the agent can diagnose compile errors without the full noise of build output.
