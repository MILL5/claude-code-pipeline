# Bicep Adapter

## Stack Metadata

- **Stack name:** `bicep`
- **Display name:** Azure Bicep (IaC)
- **Languages:** Bicep, JSON (ARM templates)
- **Build system:** bicep CLI (`bicep build`) + az CLI (`az bicep lint`). Linting via standalone `bicep` uses `bicepconfig.json` rules during build.
- **Test framework:** ARM-TTK / PSRule for Azure / `az deployment group what-if`
- **Coverage tool:** Resource validation coverage (% of resources with validation rules)

## Build & Test Commands

- **Build (lint/compile):** `python3 .claude/scripts/build.py [--project-dir .] [--scheme <lint|build|all>]`
- **Test:** `python3 .claude/scripts/test.py [--project-dir .] [--scheme <arm-ttk|psrule|what-if|all>] [--resource-group <name>] [--no-coverage]`

## Blocked Commands

These commands are blocked by hooks and must use the pipeline skills instead:
- `bicep build` / `bicep lint` / `bicep decompile` -> use `build-runner` skill
- `az deployment` (any subcommand) -> use `deploy-bicep` or `test-runner` skill
- `Invoke-PSRule` / `Test-AzTemplate` -> use `test-runner` skill

## Overlay Files

| Overlay | Agent | Purpose |
|---------|-------|---------|
| `architect-overlay.md` | architect-agent | Bicep module decomposition, scope hierarchies, dependency chains |
| `implementer-overlay.md` | implementer-agent | Bicep code quality rules, naming, decorators, security |
| `reviewer-overlay.md` | code-reviewer-agent | Bicep-specific review checklist (security, cost, reliability) |
| `test-overlay.md` | test-architect-agent | ARM-TTK, PSRule, what-if patterns and conventions |

## Project Detection

This adapter activates when the project root contains any of:
- `*.bicep` files (in root or `modules/` directory)
- `bicepconfig.json`
- `main.bicep`

## Azure Authentication

Several pipeline skills require an authenticated Azure session. The `azure-login` skill validates auth state before any Azure-dependent operation. The pipeline **does not manage credentials** — it verifies context and provides guided remediation.

### Which Skills Need Auth

| Skill | Auth Required | Why |
|-------|--------------|-----|
| `build-runner` | No | `bicep build/lint` are local operations |
| `test-runner` (PSRule/ARM-TTK) | No | Template validation is local |
| `test-runner` (what-if) | **Yes** | Queries Azure Resource Manager |
| `validate-bicep` (what-if) | **Yes** | Queries Azure Resource Manager |
| `deploy-bicep` | **Yes** | Creates/modifies Azure resources |
| `azure-drift-check` | **Yes** | Reads deployed resource state |
| `infra-test-runner` (post-deploy) | **Yes** | Reads deployed resource state |
| `azure-cost-estimate` | No | Uses public Azure Retail Pricing API |
| `security-scan` | No | PSRule/Checkov are local operations |

### Auth Methods (by scenario)

**Local developer (most common):**
```bash
az login                                          # Interactive browser login
az account set --subscription "My Dev Sub"        # Set target subscription
```

**Service principal (CI/CD):**
```bash
az login --service-principal -u <app-id> -p <secret> --tenant <tenant-id>
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
| `what-if` / drift-check | **Reader** | Target resource group |
| `deploy` (incremental) | **Contributor** | Target resource group |
| `deploy` (complete mode) | **Contributor** | Target resource group |
| Role assignments in template | **Owner** or **User Access Administrator** | Target resource group |

### Subscription Safety

The pipeline validates subscription context before deployment. Developers with access to multiple subscriptions (dev, staging, prod) must confirm the active subscription matches their intent. The `azure-login` skill displays the current subscription and prompts for confirmation if it appears to be a production subscription.

## Common Conventions

- **Parameter naming:** camelCase for parameters and variables
- **Resource naming:** PascalCase for resource symbolic names
- **Module pattern:** One module per logical resource group or reusable component
- **Parameter files:** `<environment>.bicepparam` or `<environment>.parameters.json`
- **Scoping:** `targetScope` declared at top of file; subscription-level for resource groups, resource-group-level for resources
- **API versions:** Always explicit, prefer latest stable GA version
- **Secrets:** Always use `@secure()` decorator; reference Key Vault where possible
- **Environment separation:** Parameterize all environment-specific values (location, SKU, naming prefix)
- **Tagging:** All resources must include a standard tag set (environment, owner, cost-center)
