---
name: validate-bicep
description: >
  Validate Bicep templates via lint, build, and optional what-if dry run.
  Use when you need to check Bicep templates for errors, lint violations,
  or preview deployment changes. Standalone skill — can be run independently.
---

# Validate Bicep

Validates Bicep templates through linting, compilation, and an optional what-if dry run against a target Azure environment. Reports errors, warnings, and projected resource changes.

## When to Use

- Before deploying infrastructure changes
- After modifying any `.bicep` template
- As a CI validation gate
- To preview what a deployment would change without applying it

## How to Run

### Step 1: Lint + Build

```bash
python3 .claude/scripts/build.py --scheme all
```

This runs the Bicep linter and compiles all templates to ARM JSON. Any syntax errors, lint violations, or compilation failures are reported.

### Step 1.5: Azure Auth (only if running what-if)

If proceeding to the what-if step, validate Azure authentication first:

1. If `AZURE_AUTH_STATUS` is cached and `OK`, proceed.
2. Otherwise, run the `azure-login` skill. If auth fails, skip what-if and report results from lint+build only.

### Step 2: What-If Dry Run (Optional)

```bash
az deployment group what-if \
  --resource-group <resource-group> \
  --template-file <path/to/main.bicep> \
  --parameters <path/to/parameters.json>
```

This previews the resource changes that would occur if the template were deployed.

## Output Contract

**Lint + Build phase** follows the standard BUILD output contract:

On success:
```
BUILD SUCCEEDED  |  3 warning(s)
```

On failure:
```
BUILD FAILED  |  2 error(s)  |  3 warning(s)

File                          Ln  Error
-----------------------------------------------------------
modules/storage.bicep         12  BCP035: expected type 'string'
main.bicep                    45  no-unused-params: unused parameter 'env'
```

**What-if phase** outputs a resource change summary:
```
WHAT-IF SUMMARY | Create: N, Modify: N, Delete: N, NoChange: N
```

## Important Notes

- The what-if step requires an active `az login` session and a target resource group.
- What-if does not make any changes — it is a read-only preview.
- Lint + build can run without Azure credentials; what-if cannot.
- Exit code 0 = all checks passed, 1 = errors found.
- **Hooks:** The adapter's hooks block raw `az deployment` commands via Bash. The what-if commands shown above are for reference — when used from within the pipeline, they should be run via `python3 .claude/scripts/test.py --scheme what-if` or through this skill, not as raw Bash commands.
