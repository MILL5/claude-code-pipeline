---
name: infra-test-runner
description: >
  Run infrastructure validation tests — ARM-TTK template tests, Pester integration tests,
  or deployed resource state validation. Outputs in standard test contract format.
  Use after deployment to verify resources match expected state.
---

# Infrastructure Test Runner

Runs infrastructure validation tests against Bicep/ARM templates and deployed Azure resources. Outputs results in the standard test contract format for compatibility with the pipeline.

## When to Use

- After deployment to verify resources match expected state
- During CI for template validation before deployment
- For compliance checks against organizational policies
- To validate resource configuration after manual changes

## Pre-Flight: Azure Authentication

Post-deployment tests (resource validation, configuration validation against live resources) require an authenticated Azure session with at least **Reader** access.

1. If `AZURE_AUTH_STATUS` is cached and `OK`, proceed.
2. Otherwise, run the `azure-login` skill. If auth fails, run only local template validation tests (ARM-TTK, PSRule against templates) and skip post-deployment checks.

Pre-deployment template tests (ARM-TTK, PSRule against `.bicep` files) do **not** require Azure auth.

## Test Types

| Type | Tool | Phase | Description |
|------|------|-------|-------------|
| Template validation | ARM-TTK | Pre-deploy | Validates ARM/Bicep templates against best practices |
| Resource validation | Pester + az CLI | Post-deploy | Verifies deployed resource properties match expectations |
| Configuration validation | PSRule | Pre/Post | Validates against Azure Well-Architected Framework |

## How to Run

Auto-detect available test frameworks and run the appropriate tests:

**ARM-TTK (template tests):**
```bash
pwsh -Command "Import-Module arm-ttk; Test-AzTemplate -TemplatePath <path>"
```

**Pester (integration tests):**
```bash
pwsh -Command "Invoke-Pester -Path ./tests/infra/ -OutputFormat NUnitXml -OutputFile results.xml"
```

**az CLI (resource state validation):**
```bash
az resource show --ids <resource-id> --query "properties"
```

## Output Contract

Follows the standard test output format:

```
Summary: Total: N, Passed: N, Failed: N | Coverage: X.X%

Coverage:  TemplateTests: 85.0%  |  ResourceTests: 72.0%

Test                              Result   Time
───────────────────────────────────────────────────
Storage.MinTLS                    PASSED   0.8s
KeyVault.SoftDelete               PASSED   0.6s
Network.NSGRules                  FAILED   1.2s
   L Expected: DenyAllInbound rule present, Actual: no deny-all rule found
```

- `Summary:` line always appears first — include it verbatim when reporting results.
- Failure rows show the assertion message (truncated to 160 chars).
- Exit code 0 = all passed, 1 = failures.

## Coverage

For infrastructure-as-code, coverage is calculated as the percentage of deployed resource types that have at least one validation test. This differs from code coverage — it measures breadth of infrastructure validation, not line coverage.

Example: if a template deploys 10 resource types and 7 have tests, coverage = 70.0%.
