---
name: deploy-bicep
description: >
  Deploy Bicep templates to Azure with MANDATORY user confirmation.
  Shows what-if preview first, waits for explicit approval, then deploys.
  Use when you need to deploy infrastructure changes to an Azure environment.
---

# Deploy Bicep

Deploys Bicep templates to Azure. **Always** shows a what-if preview and requires explicit user confirmation before any deployment executes.

## **MANDATORY CONFIRMATION GATE**

**Before ANY deployment, you MUST:**
1. Run `az deployment group what-if` and show the full output to the user.
2. Ask the user: **"Proceed with deployment to `<resource-group>`? (yes/no)"**
3. Wait for an explicit **"yes"** before proceeding.

**NEVER deploy without explicit "yes" from the user. NEVER assume consent. NEVER skip the what-if preview.**

## Pre-Flight: Azure Authentication

Before running any deployment commands, verify Azure auth:

1. If `AZURE_AUTH_STATUS` is cached and `OK` from a prior `azure-login` check in this session, proceed.
2. Otherwise, run the `azure-login` skill to validate auth, subscription context, and resource group permissions.
3. If auth fails, **stop** — do not proceed with deployment. Show the remediation guidance from `azure-login`.
4. Verify the active subscription matches the intended deployment target. Display the subscription name and ask the user to confirm if it was not previously validated in this session.

## How to Deploy

### Step 1: What-If Preview

```bash
az deployment group what-if \
  --resource-group <resource-group> \
  --template-file <path/to/main.bicep> \
  --parameters <path/to/parameters.json>
```

Show the results to the user with a clear summary of what will be created, modified, or deleted.

### Step 2: Ask for Confirmation

Present the what-if summary and ask: **"Proceed with deployment to `<resource-group>`? (yes/no)"**

### Step 3: Deploy (Only After "yes")

```bash
az deployment group create \
  --resource-group <resource-group> \
  --template-file <path/to/main.bicep> \
  --parameters <path/to/parameters.json> \
  --name <deployment-name>
```

## Required Parameters

| Parameter | Description |
|-----------|-------------|
| `--resource-group` | Target Azure resource group |
| `--template-file` | Path to the main `.bicep` file |
| `--parameters` | Parameters file or inline key=value pairs |

## Output Contract

**On success:**
```
DEPLOY SUCCEEDED | N resources created | N modified

Resource                          Type                                    Operation
──────────────────────────────────────────────────────────────────────────────────────
myStorageAccount                  Microsoft.Storage/storageAccounts       Create
myKeyVault                        Microsoft.KeyVault/vaults               NoChange
```

**On failure:**
```
DEPLOY FAILED | <error summary>
```

## Post-Deploy

After a successful deployment, capture deployment outputs (resource IDs, endpoints, connection strings) for use by dependent skills or subsequent pipeline steps:

```bash
az deployment group show \
  --resource-group <resource-group> \
  --name <deployment-name> \
  --query properties.outputs
```

## Safety

- **Never** deploy to production without explicit user confirmation in the **same** conversation turn.
- Always prefer `--mode Incremental` (the default) over `--mode Complete` unless the user explicitly requests complete mode.
- Complete mode deletes resources not in the template — require double confirmation for complete mode.
- **Hooks:** The adapter's hooks block raw `az deployment` commands via Bash. This skill is the approved way to perform deployments. The `az` commands shown above are reference — execute them via subprocess or through the skill's workflow, not as raw Bash tool calls.
