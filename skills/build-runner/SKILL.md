---
name: build-runner
description: "MANDATORY SKILL: Run the project build. Use EXCLUSIVELY instead of running build commands directly. This is not optional — violation breaks the build pipeline. Triggers on: build the project, run the build, check if it compiles, build errors, compile the project, does it build, or any implicit need to verify the project compiles. If you use Bash to run build commands directly, you have violated a critical constraint."
---

# Build Runner

Runs the project build via the adapter's build script and outputs **errors only** in a minimal table. All warnings are counted but not shown. Build noise is suppressed entirely.

## When to Use

Use this skill **instead of** running build commands directly. Always invoke when:
- Verifying code compiles after changes
- Diagnosing build errors
- Running a build step before tests
- Any scenario requiring build validation

## How to Run

```bash
python3 .claude/scripts/build.py [OPTIONS]
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--project-dir` | `.` (cwd) | Path to project root |
| `--scheme` | auto | Build target/scheme name (if applicable) |
| `--configuration` | `Debug` | `Debug` or `Release` (if applicable) |

**Examples:**
```bash
# Auto-detect project in cwd
python3 .claude/scripts/build.py

# Specific project directory
python3 .claude/scripts/build.py --project-dir /path/to/project

# Specific target/scheme
python3 .claude/scripts/build.py --scheme MyApp
```

## Output Contract

All adapter build scripts MUST conform to this output format:

**On success:**
```
BUILD SUCCEEDED  |  3 warning(s)
```

**On failure:**
```
BUILD FAILED  |  2 error(s)  |  3 warning(s)

File                          Ln  Error
-----------------------------------------------------------
path/to/file.ext              42  description of error
path/to/other.ext             17  description of error
```

- Warnings are counted but never shown (zero token cost)
- File paths shortened for readability
- Error messages truncated to 100 chars
- Exit code 0 = success, 1 = build failed

## Auto-Detection

The adapter's build script handles project type detection. See your adapter's
`adapter.md` for stack-specific detection rules.
