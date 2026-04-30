# Adopting the Bicep (Azure IaC) Adapter

This adapter activates for Azure infrastructure-as-code projects using Bicep. The pipeline runs `bicep build` + lint for build and ARM-TTK / PSRule / `what-if` for tests. The Bicep adapter also auto-implies the cross-cutting `azure-sdk` overlay (for projects that mix IaC with SDK code) and adds the `azure-auth` capability that triggers an Azure login pre-flight before deploy/what-if operations.

> **Comprehensive guide:** for the full Azure adoption story (Bicep + Azure SDK overlay + auth + the seven Azure-specific skills), see [docs/azure-guide.md](../azure-guide.md). This document is a quick-start summary that points there for depth.

## Detection

`init.sh` activates this adapter when any of these exist at the project root:

- `*.bicep` files (anywhere)
- `infra/*.bicep`, `infrastructure/*.bicep`, `deploy/*.bicep`, `modules/*.bicep`
- `bicepconfig.json`

When detected, the `azure-auth` capability and `azure-sdk` overlay activate automatically (see `manifest.json`).

## Tools you'll need

| Tool | Why | Notes |
|---|---|---|
| Azure CLI (`az`) | Bicep build + deployment | `az upgrade` if installed; `az bicep install` |
| Bicep CLI | Build + lint | Bundled with `az` (`az bicep version`) |
| PowerShell 7+ (`pwsh`) | PSRule + ARM-TTK | Optional but recommended for full coverage |
| `gh` CLI | PR creation by the pipeline | `gh auth status` must exit 0 |

## Bootstrap

```bash
cd your-bicep-project
git submodule add https://github.com/MILL5/claude-code-pipeline.git .claude/pipeline
bash .claude/pipeline/init.sh .
```

Expected output:

```
Detected stacks: bicep
Active overlays: azure-sdk
Active capabilities: azure-auth
Symlinks created:
  .claude/agents -> .claude/pipeline/agents
  .claude/skills/* -> .claude/pipeline/skills/*
  .claude/scripts/bicep -> .claude/pipeline/adapters/bicep/scripts
Wrote .claude/pipeline.config (stacks=bicep, overlays=azure-sdk)
Merged hooks into .claude/settings.json
Generated .claude/CLAUDE.md and .claude/ORCHESTRATOR.md (edit these next)
Generated .claude/local/ overlay templates
```

After bootstrap, run `/azure-login` once to verify Azure auth, subscription context, and RBAC permissions.

## Project layout assumed

Default `stack_paths`:

- `infra/`, `infrastructure/`, `deploy/`

Plus fallback globs for `**/*.bicep`, `**/*.bicepparam`, and `bicepconfig.json`.

If your modules live elsewhere (e.g., `modules/`), they're picked up by the fallback globs. For non-standard layouts, add patterns to `pipeline.config` explicitly.

## Build & test commands

```bash
python3 .claude/scripts/bicep/build.py
python3 .claude/scripts/bicep/test.py
```

`build.py` runs `bicep build` + `az bicep lint` and emits the pipeline's contract line. `test.py` orchestrates ARM-TTK, PSRule, and (optionally) `what-if` against a target subscription, parsing each tool's output into the unified `Summary: Total: N, Passed: N, Failed: N | Coverage: X.X%` line.

Raw `bicep build`, `az deployment ... create`, and PSRule invocations are blocked by `hooks.json`. Use the Azure-specific skills:

- `/validate-bicep` — lint + build + optional what-if
- `/deploy-bicep` — deploy with mandatory confirmation gate
- `/azure-cost-estimate` — monthly cost projection
- `/security-scan` — PSRule + Checkov
- `/infra-test-runner` — ARM-TTK + Pester
- `/azure-drift-check` — compare deployed state to templates

## First `/orchestrate` run

Inside Claude Code:

```
/azure-login          # one-time, verifies auth
/orchestrate
```

Then describe a small change: *"Add a private endpoint to the Storage account in modules/storage.bicep"*. The pipeline will:

1. Ask 1-2 clarifying questions (subnet to attach to, DNS zone integration)
2. Generate a Haiku-tier plan (likely 1-2 tasks)
3. Open a draft PR
4. Run pre-flight build (`bicep build` + lint)
5. Implement, review (with Bicep reviewer overlay watching for security, cost, reliability)
6. Run ARM-TTK + PSRule
7. Optionally run `what-if` against a target subscription (configured via `/validate-bicep`)
8. Ask you to manually approve before any deploy
9. File a token-analysis report

For a small infra change, expect ~$0.10-0.30 and 5-10 minutes wall-clock.

## Common pitfalls

### Authentication scope

`az login` may default to a different tenant or subscription than the one you're targeting. The `/azure-login` skill validates this explicitly. If `what-if` or deploy fails with permission errors, re-run `/azure-login` and confirm the subscription context.

### `dependsOn` over-specification

Bicep can infer `dependsOn` from references in most cases. The reviewer flags explicit `dependsOn` lists that duplicate inferable dependencies as `[simplify]`. If you see deps removed during fix cycles, that's behavior-preserving cleanup.

### What-if vs. deploy

The pipeline never deploys without explicit user confirmation (`/deploy-bicep` requires a confirmation gate). What-if is a non-mutating preview. For PR validation, prefer what-if to deploy — what-if catches most issues and doesn't risk drift.

### Module reuse

The Bicep reviewer overlay encourages module reuse over inlining. Haiku tends to inline resources for clarity. Reviewer flags 2+ near-duplicate resource definitions as candidates for module extraction (`[should-fix]`).

### Multi-stack: Bicep + an SDK language

If your repo has Bicep templates AND application code in another language (Python with Azure SDK, .NET/Node calling Azure services), bootstrap both stacks. The `azure-sdk` overlay activates automatically and applies to whichever language stack you bootstrap with — the overlay teaches both Python and Bicep the same auth/retry/Key Vault discipline.

## Where to file issues

Pipeline behavior issues: https://github.com/MILL5/claude-code-pipeline/issues

Adoption pain specific to this stack: same repo, label `type: docs` with `bicep` or `azure` in the title.

## See also

- [Azure Deployment Guide](../azure-guide.md) — full Azure adoption walkthrough
- [Testing Guide](../testing-guide.md) — manual testing and defect reporting
