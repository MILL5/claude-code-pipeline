# Azure Deployment Guide

How to use the Claude Code Pipeline for projects that deploy to Azure. Covers the Bicep adapter for Infrastructure as Code, the Azure SDK overlay for application code, Azure authentication, and the 7 Azure-specific skills.

## Who This Is For

Developers building applications or infrastructure that deploy to Azure. Your repo might contain:

- **Bicep templates** (`main.bicep`, `modules/*.bicep`) for infrastructure provisioning
- **Application code** (Python, TypeScript, .NET) that uses Azure SDK to talk to Azure services
- **Both** — a full-stack project with app code + IaC in the same repo

The pipeline handles each scenario differently:

| Scenario | Adapter | Overlay | What You Get |
|----------|---------|---------|-------------|
| Bicep IaC only | `bicep` | `azure-sdk` (auto) | Bicep build/lint/test + all 7 Azure skills |
| Python app + Azure SDK | `python` | `azure-sdk` (auto) | Python pipeline + Azure SDK review rules + Azure skills |
| React app + Azure SDK | `react` | `azure-sdk` (auto) | React pipeline + Azure SDK review rules + Azure skills |
| Bicep + Python app in same repo | `bicep` or `python` | `azure-sdk` (auto) | Choose primary stack; Azure overlay adds cross-cutting rules |

## Quick Start

### 1. Bootstrap

```bash
# Clone the pipeline
git clone https://github.com/swtarmey/claude-code-pipeline.git .claude/pipeline

# Bootstrap — auto-detects Bicep from .bicep files or bicepconfig.json
bash .claude/pipeline/init.sh .
```

If your project has both Bicep and Python files, the auto-detector picks Bicep (it checks before Python). To override:

```bash
bash .claude/pipeline/init.sh . --stack=python   # Use Python adapter, Azure SDK overlay auto-detected
bash .claude/pipeline/init.sh . --stack=bicep     # Use Bicep adapter explicitly
```

### 2. Verify Azure detection

Check `.claude/pipeline.config`:

```ini
stack=bicep
pipeline_root=/path/to/claude-code-pipeline
overlays=azure-sdk
initialized=2026-03-29T12:00:00Z
```

The `overlays=azure-sdk` line means the Azure SDK overlay was detected. If it's missing and you're deploying to Azure, add it manually.

### 3. Authenticate

```bash
az login
az account set --subscription "My Dev Subscription"
```

Then verify from within Claude Code:

```
/azure-login
```

This validates your auth state, shows the active subscription, and caches the result for the session.

### 4. Run the pipeline

```
/orchestrate
```

The pipeline flows exactly as documented in the main README. For Bicep projects, the implementer writes `.bicep` files, the reviewer checks for Azure security/cost/reliability patterns, and build/test runs `bicep build` + PSRule/ARM-TTK.

## Azure Authentication

### How Auth Works in the Pipeline

The pipeline **does not manage your Azure credentials**. It validates that you're authenticated and targeting the right subscription before running any Azure-dependent operation.

The `azure-login` skill runs a 6-step pre-flight check:

1. **az CLI installed?** — If not, shows install instructions for your platform
2. **Authenticated?** — If not, shows login options (interactive, service principal, managed identity, GitHub Actions OIDC)
3. **Display context** — Shows subscription, tenant, user, auth method
4. **Correct subscription?** — Validates the active subscription if a target is known
5. **Resource group exists?** — Checks the target RG (advisory, non-blocking)
6. **Sufficient permissions?** — Verifies RBAC roles for the operation type

### When Auth Is Checked

Auth is checked **lazily** — only before the first Azure-dependent step, not at pipeline start. This means:

- `bicep build` / `bicep lint` — **No auth needed** (local operations)
- PSRule / ARM-TTK template validation — **No auth needed** (local operations)
- Security scan (PSRule/Checkov) — **No auth needed** (local operations)
- Cost estimate — **No auth needed** (public pricing API)
- `az deployment group what-if` — **Auth required** (queries Azure Resource Manager)
- `deploy-bicep` — **Auth required** (creates/modifies resources)
- `azure-drift-check` — **Auth required** (reads deployed state)
- Post-deploy infrastructure tests — **Auth required** (reads deployed state)

If you're only doing local build/lint/review cycles, you'll never be asked to authenticate.

### Auth Methods

**Local development (most common):**
```bash
az login                                    # Opens browser for interactive login
az account set --subscription "My Dev Sub"  # Set target subscription
```

**Service principal (CI/CD):**
```bash
az login --service-principal \
  -u $AZURE_CLIENT_ID \
  -p $AZURE_CLIENT_SECRET \
  --tenant $AZURE_TENANT_ID
```

**Managed identity (Azure-hosted runners):**
```bash
az login --identity
```

**GitHub Actions (OIDC — recommended for CI):**
```yaml
- uses: azure/login@v2
  with:
    client-id: ${{ secrets.AZURE_CLIENT_ID }}
    tenant-id: ${{ secrets.AZURE_TENANT_ID }}
    subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
```

### Required RBAC Roles

| Operation | Minimum Role | Scope |
|-----------|-------------|-------|
| What-if / drift check | Reader | Target resource group |
| Deploy (incremental) | Contributor | Target resource group |
| Deploy (complete mode) | Contributor | Target resource group |
| Role assignments in template | Owner or User Access Administrator | Target resource group |

### Multiple Subscriptions

If you have access to dev, staging, and prod subscriptions, the pipeline shows which one is active and asks for confirmation before any deployment. To switch:

```bash
az account set --subscription "My Staging Subscription"
```

Or run `/azure-login` to see all available subscriptions.

## The Bicep Adapter

### What It Does

The Bicep adapter teaches the pipeline's 4 generic agents about Infrastructure as Code:

| Agent | What the Bicep overlay adds |
|-------|---------------------------|
| **Architect** | Module decomposition patterns, scope hierarchy (subscription/RG/management group), resource dependency chains, hub-spoke networking, environment parameterization |
| **Implementer** | Naming conventions (camelCase params, PascalCase resources), `@description`/`@secure` decorators, API version policy, module patterns, conditional deployments, Key Vault references |
| **Reviewer** | 8-category checklist: security (RBAC, private endpoints, encryption), cost (SKU, auto-scale, tagging), reliability (availability zones, backups, locks), module boundaries, parameter validation, output contracts, dependency chains, naming |
| **Test architect** | ARM-TTK patterns, PSRule baselines, what-if interpretation, post-deploy Pester tests |

### Build Script

`python3 .claude/scripts/bicep/build.py` runs:

1. **`bicep lint`** (via `az bicep lint` or `bicep build` with `bicepconfig.json` rules)
2. **`bicep build`** (compiles each `.bicep` to ARM JSON)

Output follows the standard pipeline contract:
```
BUILD SUCCEEDED  |  2 warning(s)
```
or:
```
BUILD FAILED  |  1 error(s)  |  2 warning(s)

File                      Ln  Error
-------------------------------------------------------
main.bicep                18  [BCP035] missing required property "location"
```

### Test Script

`python3 .claude/scripts/bicep/test.py` auto-detects and runs available frameworks:

| Framework | Detection | What it tests |
|-----------|----------|--------------|
| **PSRule for Azure** | `ps-rule.yaml` or PowerShell module | Azure Well-Architected Framework rules (security, cost, reliability) |
| **ARM-TTK** | PowerShell module | Template syntax, parameters, resource types |
| **What-if** | `az` CLI + `--resource-group` flag | Deployment impact (requires Azure auth) |

Output follows the standard test contract:
```
Summary: Total: 18, Passed: 18, Failed: 0 | Coverage: 83.3%
```

### Project Structure

The adapter expects a typical Bicep project layout:

```
your-project/
|-- main.bicep                    # Entry point
|-- bicepconfig.json              # Linter configuration
|-- modules/
|   |-- storage.bicep             # Reusable module
|   |-- networking.bicep
|   +-- keyvault.bicep
|-- dev.bicepparam                # Dev environment parameters
|-- staging.bicepparam            # Staging parameters
|-- prod.bicepparam               # Production parameters
+-- tests/
    +-- infra.Tests.ps1           # Pester integration tests (optional)
```

## The Azure SDK Overlay

### What It Does

The Azure SDK overlay is a **cross-cutting concern** that layers onto any adapter. When the pipeline detects Azure SDK packages in your project dependencies, it automatically activates.

This means a Python + Azure project gets both:
- Python adapter overlays (type hints, pytest patterns, Django/FastAPI conventions)
- Azure SDK overlays (DefaultAzureCredential, retry policies, Key Vault, managed identity)

### How It's Detected

`init.sh` checks for Azure SDK packages in:

| Stack | Detection |
|-------|----------|
| Python | `azure-*` in `requirements.txt` or `pyproject.toml` |
| Node/JS | `@azure/*` in `package.json` |
| .NET | `Azure.*` NuGet packages in `*.csproj` |
| Bicep | Always activated (implicit) |

### What It Adds

**For the architect:** Azure service integration patterns (Service Bus, Cosmos DB, Blob Storage), managed identity design, Key Vault integration, multi-region patterns.

**For the implementer:** `DefaultAzureCredential` as the standard auth chain, client reuse/singleton patterns, retry policy configuration, Key Vault secret retrieval, connection strings from Key Vault only, proper client disposal.

**For the reviewer:** 5 additional review categories layered on top of the adapter's existing categories:
1. Authentication — managed identity over keys, DefaultAzureCredential, no hardcoded secrets
2. Retry & Resilience — retry policies, circuit breakers, timeouts
3. Resource Lifecycle — client disposal, connection pooling, no leaked connections
4. Security — Key Vault for secrets, RBAC over access keys, no secrets in logs
5. Cost & Performance — client reuse, batch operations, tagging

### Manual Activation

If auto-detection missed your Azure SDK usage, add it to `pipeline.config`:

```ini
overlays=azure-sdk
```

Or re-run init with a project that has Azure packages in its dependencies.

## Azure Skills Reference

### `/azure-login` — Authentication Pre-Flight

Validates Azure auth state, subscription context, and permissions. Run before any Azure-dependent operation, or let the orchestrator call it automatically.

```
> /azure-login

AZURE CONTEXT
  Subscription:  My Dev Subscription (xxxxxxxx-...)
  Tenant:        Contoso (xxxxxxxx-...)
  User:          dev@contoso.com
  Auth method:   Interactive (az login)

AZURE AUTH OK | Subscription: My Dev Subscription (xxxxxxxx-...) | User: dev@contoso.com | Method: interactive
```

### `/validate-bicep` — Lint, Build, and What-If

Validates Bicep templates without deploying. The what-if step is optional and requires Azure auth.

```
> /validate-bicep

BUILD SUCCEEDED  |  0 warning(s)

WHAT-IF SUMMARY | Create: 2, Modify: 1, Delete: 0, NoChange: 3
```

### `/deploy-bicep` — Deploy with Confirmation Gate

Deploys Bicep templates to Azure. **Always** shows a what-if preview and requires explicit confirmation.

```
> /deploy-bicep

What-if results for rg-staging:
  Create: myStorageAccount (Microsoft.Storage/storageAccounts)
  Modify: myKeyVault (Microsoft.KeyVault/vaults)
  NoChange: 3 resources

Proceed with deployment to rg-staging? (yes/no)
> yes

DEPLOY SUCCEEDED | 1 resources created | 1 modified
```

The confirmation gate is mandatory and cannot be bypassed. The pipeline will never deploy without an explicit "yes" in the same conversation turn.

### `/azure-cost-estimate` — Monthly Cost Estimation

Parses Bicep templates, extracts resource types and SKUs, and queries the Azure Retail Pricing API. No Azure auth required.

```
> /azure-cost-estimate

COST ESTIMATE | Total: $284.50/month

Resource                   Type                                SKU          Est. Monthly
──────────────────────────────────────────────────────────────────────────────────────────
myStorageAccount           Microsoft.Storage/storageAccounts   Standard_LRS $21.00
myAppServicePlan           Microsoft.Web/serverfarms           P1v3         $138.00
myCosmosDb                 Microsoft.DocumentDB/databaseAccts  Standard     $25.00-$500.00*

* Consumption-based resources show estimate ranges.
```

### `/security-scan` — Security and Compliance Scanning

Runs PSRule for Azure or Checkov against Bicep templates. No Azure auth required.

```
> /security-scan

SECURITY SCAN | Total: 4 findings | Critical: 1, High: 1, Medium: 2, Low: 0

Rule                          Severity  Resource            Description
───────────────────────────────────────────────────────────────────────────
Azure.SQL.FirewallIPRange     CRITICAL  mySqlServer         Firewall allows 0.0.0.0-255.255.255.255
Azure.Storage.MinTLS          HIGH      myStorageAccount    TLS version below 1.2
```

### `/infra-test-runner` — Infrastructure Tests

Runs ARM-TTK template validation, Pester integration tests, or post-deploy resource checks. Template validation is local; post-deploy tests require Azure auth.

```
> /infra-test-runner

Summary: Total: 18, Passed: 15, Failed: 3 | Coverage: 83.3%

Test                              Result   Time
───────────────────────────────────────────────────
Storage.MinTLS                    PASSED   0.8s
KeyVault.SoftDelete               PASSED   0.6s
Network.NSGRules                  FAILED   1.2s
   Expected: DenyAllInbound rule present, Actual: no deny-all rule found
```

### `/azure-drift-check` — Configuration Drift Detection

Compares deployed Azure resource state against Bicep templates. Requires Azure auth.

```
> /azure-drift-check

DRIFT CHECK | Total: 5 resources | Drifted: 2, Compliant: 2, Missing: 1

Resource              Property               Expected    Actual      Status
──────────────────────────────────────────────────────────────────────────────
myStorageAccount      minimumTlsVersion      TLS1_2      TLS1_0      DRIFTED
myKeyVault            enableSoftDelete       true        false       DRIFTED
myAppServicePlan      —                      Standard_S1 —           MISSING
```

## Workflows

### Workflow 1: Building a New Bicep Module

You're adding a new storage module to your IaC project.

```
> Add a storage account module with blob containers, private endpoint, and diagnostic settings

Pipeline runs:
  1a. Architect analyzes: module boundaries, dependency on networking + Key Vault modules
  1b. Plan: 4 Haiku tasks (module, params, outputs, param file) + 1 Sonnet (networking integration)
  1.5. Opens draft PR
  2.  Implements each task with bicep build + PSRule validation
  2.1. Reviews: checks @secure on connection strings, private endpoint config, tagging
  3.  Commits each task
  3.5. You test: /validate-bicep, /security-scan, /azure-cost-estimate
  4.  Finalizes PR
```

### Workflow 2: Adding Azure SDK Integration to a Python App

You're adding Cosmos DB integration to an existing Python API.

```
> Add Cosmos DB client for user profile storage using DefaultAzureCredential

Pipeline runs with Python adapter + Azure SDK overlay:
  1a. Architect considers: DefaultAzureCredential chain, retry policies, connection pooling
  1b. Plan: CosmosDB client wrapper (Sonnet), CRUD operations (Haiku x3), tests (Haiku x2)
  2.  Implements with Python + Azure SDK rules enforced
  2.1. Reviews: checks client reuse, retry config, no hardcoded keys, proper disposal
```

### Workflow 3: Pre-Deployment Validation

Before deploying to staging, run the validation skills standalone:

```
/security-scan              # Check for misconfigurations
/azure-cost-estimate        # Verify cost is within budget
/validate-bicep             # Lint + build + what-if preview
/azure-drift-check          # Check if staging has drifted from templates
/deploy-bicep               # Deploy (with confirmation gate)
/infra-test-runner           # Post-deploy validation
```

### Workflow 4: Investigating Production Drift

Something changed in production outside of your templates:

```
> /azure-login                 # Verify you're on the prod subscription
> /azure-drift-check           # Compare deployed state vs templates

DRIFT CHECK | Total: 12 resources | Drifted: 3, Compliant: 8, Missing: 1

# Fix the drift by updating templates to match desired state, then:
> /orchestrate                 # Pipeline plans + implements the template updates
> /validate-bicep              # Verify the fix
> /deploy-bicep                # Deploy the corrected templates
```

## Tips

### Keeping Bicep and App Code in Sync

If your repo has both Bicep templates and application code:

1. Bootstrap with the adapter matching your **primary development activity**
2. The Azure SDK overlay activates automatically for both stacks
3. Use `/orchestrate` for your primary stack's changes
4. Use the Azure skills (`/validate-bicep`, `/deploy-bicep`, etc.) directly for IaC changes

### Environment-Specific Deployments

Use parameter files to target different environments:

```bash
# Dev (default — safe to experiment)
/deploy-bicep   # Uses dev.bicepparam by default

# Staging (requires confirmation)
# Tell the pipeline: "deploy to staging using staging.bicepparam"

# Production (requires explicit subscription switch + double confirmation)
az account set --subscription "Production"
/azure-login    # Re-validates auth on new subscription
/deploy-bicep   # Shows what-if, requires confirmation
```

### Cost Control

Run `/azure-cost-estimate` before deploying to catch:
- Over-provisioned SKUs (Premium when Standard suffices)
- Resources that should use reserved pricing
- Missing cost allocation tags
- Accidental duplicate resources

### Security Hardening

Run `/security-scan` as part of your review process to catch:
- Public endpoints without private endpoints
- Missing encryption at rest or in transit
- Overly permissive firewall rules
- Missing diagnostic settings
- Hardcoded secrets or connection strings

## Requirements

In addition to the [base pipeline requirements](../README.md#requirements):

- **Azure CLI** (`az`) — for deployments, what-if, drift checks
- **Bicep CLI** (`bicep`) — standalone or via `az bicep` (included with az CLI)
- **PowerShell 7+** (`pwsh`) — for ARM-TTK and PSRule (optional, for testing)
- **PSRule for Azure** — `Install-Module PSRule.Rules.Azure` (optional, for security scanning)
- **ARM-TTK** — `Install-Module arm-ttk` (optional, for template validation)

None of the optional tools are required for basic `bicep build`/`bicep lint` — they extend the testing and scanning capabilities.
