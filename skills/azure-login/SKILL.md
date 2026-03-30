---
name: azure-login
description: >
  Pre-flight Azure authentication and context validation. Verifies az CLI auth,
  shows active subscription/tenant, validates target resource group access.
  Run before any Azure-dependent skill (deploy-bicep, validate-bicep what-if,
  azure-drift-check, infra-test-runner). Also provides guided login for
  unauthenticated sessions.
---

# Azure Login & Context Validation

Pre-flight check that validates Azure authentication state, subscription context, and
resource group permissions before any Azure-dependent operation. This skill verifies
context — it does not manage credentials.

## When to Use

- **Automatically**: The orchestrator calls this before Azure-dependent pipeline steps when the active capabilities include `azure-auth`.
- **Manually**: Run `/azure-login` to verify your Azure context or switch subscriptions.
- **Before deployment**: `deploy-bicep` and `validate-bicep` (what-if) invoke this as a pre-flight gate.

## Pre-Flight Check Sequence

Run these checks in order. Stop at the first failure and provide guided remediation.

### Step 1: Verify az CLI Installed

```bash
az version --output json
```

If `az` is not found:
```
AZURE AUTH FAILED | az CLI not installed

Install the Azure CLI:
  macOS:   brew install azure-cli
  Linux:   curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
  Windows: winget install Microsoft.AzureCLI
  Docs:    https://learn.microsoft.com/cli/azure/install-azure-cli
```

### Step 2: Verify Authentication

```bash
az account show --output json
```

If not authenticated (exit code != 0):
```
AZURE AUTH FAILED | Not logged in

Choose your login method:

  Interactive (recommended for local dev):
    az login

  Service principal (CI/CD):
    az login --service-principal -u <app-id> -p <secret-or-cert> --tenant <tenant-id>

  Managed identity (Azure-hosted):
    az login --identity

  Environment variables (headless):
    export AZURE_CLIENT_ID=<app-id>
    export AZURE_TENANT_ID=<tenant-id>
    export AZURE_CLIENT_SECRET=<secret>
    az login --service-principal -u $AZURE_CLIENT_ID -p $AZURE_CLIENT_SECRET --tenant $AZURE_TENANT_ID

  GitHub Actions (OIDC):
    uses: azure/login@v2
    with:
      client-id: ${{ secrets.AZURE_CLIENT_ID }}
      tenant-id: ${{ secrets.AZURE_TENANT_ID }}
      subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
```

**Important**: Do NOT run `az login` on behalf of the user. Print the guidance and ask them to authenticate. The user should type `! az login` in the Claude Code prompt to run it in their session.

### Step 3: Display Active Context

If authenticated, parse `az account show` output and display:

```
AZURE CONTEXT
  Subscription:  My Dev Subscription (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
  Tenant:        My Org (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
  User:          dev@myorg.com
  Cloud:         AzureCloud
  Auth method:   Interactive (az login)
```

Detect auth method from the `user.type` field:
- `user` → Interactive (`az login`)
- `servicePrincipal` → Service principal
- `managedIdentity` → Managed identity

### Step 4: Validate Subscription (if target specified)

If a target subscription is known (from parameter files, pipeline.config, or user input):

```bash
az account show --subscription <subscription-id-or-name> --output json
```

If the subscription does not exist or user lacks access:
```
AZURE AUTH FAILED | Cannot access subscription '<name>'

Available subscriptions:
  - My Dev Subscription    (xxxxxxxx-...) [default]
  - My Staging Sub         (xxxxxxxx-...)

To switch subscription:
  az account set --subscription "<name-or-id>"
```

### Step 5: Validate Resource Group (if target specified)

If a target resource group is known:

```bash
az group show --name <resource-group> --output json
```

If the resource group does not exist:
```
AZURE AUTH WARNING | Resource group '<name>' does not exist

The deployment will create it if the template includes a resource group resource
at subscription scope. Otherwise, create it first:
  az group create --name <name> --location <location>
```

### Step 6: Validate Permissions (if deploying)

For deployment operations, verify the user has write access:

```bash
az role assignment list --assignee <user-or-sp-id> --scope /subscriptions/<sub-id>/resourceGroups/<rg> --output json
```

Check that the user has at least one of: `Contributor`, `Owner`, or a custom role with `Microsoft.Resources/deployments/write`.

If insufficient permissions:
```
AZURE AUTH FAILED | Insufficient permissions on resource group '<name>'

Current roles: Reader
Required: Contributor or Owner (for deployments)

To grant access (requires Owner or User Access Administrator):
  az role assignment create --assignee <user> --role Contributor --scope /subscriptions/<sub-id>/resourceGroups/<rg>
```

## Output Contract

**On success:**
```
AZURE AUTH OK | Subscription: <name> (<id>) | User: <upn-or-sp> | Method: <interactive|service-principal|managed-identity>
```

**On failure:**
```
AZURE AUTH FAILED | <reason>
```

Followed by remediation guidance specific to the failure.

**On warning (non-blocking):**
```
AZURE AUTH WARNING | <message>
```

Warnings (missing RG, unknown permissions) are advisory — they do not block the pipeline. Failures (no az CLI, not logged in, wrong subscription) are blocking.

## Context Caching

After a successful pre-flight check, cache the result in-session:
- `AZURE_AUTH_STATUS = OK`
- `AZURE_SUBSCRIPTION_ID = <id>`
- `AZURE_SUBSCRIPTION_NAME = <name>`
- `AZURE_TENANT_ID = <id>`
- `AZURE_USER = <upn-or-sp>`
- `AZURE_AUTH_METHOD = <method>`

Subsequent Azure-dependent skills in the same pipeline run can skip re-validation by checking `AZURE_AUTH_STATUS`. Re-validate if the target subscription or resource group changes.

## Scenarios

### Local Developer (most common)

1. Developer runs `az login` once (opens browser, authenticates)
2. Pipeline calls `/azure-login` → detects interactive session, shows context
3. Developer confirms subscription is correct
4. Pipeline proceeds with deploy/what-if/drift-check

### CI/CD Pipeline

1. CI sets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET` (or OIDC)
2. CI runs `az login --service-principal` before pipeline
3. Pipeline calls `/azure-login` → detects service principal, shows context
4. No user confirmation needed (automated)

### Multiple Subscriptions

1. Developer has access to dev, staging, prod subscriptions
2. Pipeline calls `/azure-login` → shows current subscription
3. If wrong: `az account set --subscription "My Dev Subscription"`
4. Pipeline re-validates and proceeds

### Expired Token

1. Developer's `az login` token has expired (common after overnight)
2. Pipeline calls `/azure-login` → `az account show` fails
3. Skill shows "Not logged in" guidance with `az login` command
4. Developer re-authenticates, pipeline retries
