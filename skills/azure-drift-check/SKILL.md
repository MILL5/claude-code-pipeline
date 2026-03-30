---
name: azure-drift-check
description: >
  Compare deployed Azure resource state against Bicep template definitions.
  Detects configuration drift from manual portal changes or external modifications.
  Use for compliance checks or before deployments to understand current state.
---

# Azure Drift Check

Compares deployed Azure resource state against Bicep template definitions to detect configuration drift caused by manual portal changes, external scripts, or other out-of-band modifications.

## Pre-Flight: Azure Authentication

This skill requires an authenticated Azure session with at least **Reader** access to the target resource group.

1. If `AZURE_AUTH_STATUS` is cached and `OK`, proceed.
2. Otherwise, run the `azure-login` skill. If auth fails, **stop** and show remediation guidance.

## How It Works

1. Run `az deployment group what-if` against the live environment to compare template definitions with actual deployed state.
2. Optionally use Azure Resource Graph queries to inspect specific resource properties for more granular comparison.
3. Report drifted, compliant, and missing resources.

## How to Run

**What-if comparison (primary method):**
```bash
az deployment group what-if \
  --resource-group <resource-group> \
  --template-file <path/to/main.bicep> \
  --parameters <path/to/parameters.json> \
  --result-format ResourceIdOnly
```

**Resource Graph queries (granular inspection):**
```bash
az graph query -q "
  Resources
  | where resourceGroup == '<resource-group>'
  | project name, type, properties
"
```

## Output Contract

```
DRIFT CHECK | Total: N resources | Drifted: N, Compliant: N, Missing: N

Resource                   Property                    Expected              Actual                 Status
────────────────────────────────────────────────────────────────────────────────────────────────────────────
myStorageAccount           minimumTlsVersion           TLS1_2                TLS1_0                 DRIFTED
myStorageAccount           enableHttpsTrafficOnly      true                  true                   COMPLIANT
myKeyVault                 enableSoftDelete            true                  false                  DRIFTED
myAppServicePlan           —                           Standard_S1           —                      MISSING
```

- **DRIFTED** — deployed property differs from template definition.
- **COMPLIANT** — deployed property matches template definition.
- **MISSING** — resource defined in template but not found in the environment.
- Exit code 0 = no drift detected, 1 = drift or missing resources found.

## When to Use

- Periodic compliance checks to ensure environments match their template definitions.
- Before deployments to understand what the current state looks like.
- After incident investigation to detect unauthorized changes.
- Governance audits to verify infrastructure policy adherence.

## Important Notes

- What-if may show false positives for computed or read-only properties (e.g., `provisioningState`, `createdTime`). Filter these from drift reports.
- Resource Graph queries provide point-in-time snapshots and may have a slight propagation delay (typically under 60 seconds).
- Requires an active `az login` session with read access to the target resource group.
- For large environments, scope the check to specific resource types to reduce noise.
