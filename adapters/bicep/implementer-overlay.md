# Bicep Implementer Rules

## Code Quality Rules (Rule 4)

Within the boundaries of what the brief asks for, write clean Bicep:

### Naming Conventions
- camelCase for parameters, variables, outputs, and module symbolic names
- PascalCase for resource symbolic names (e.g., `resource StorageAccount`)
- Descriptive names that indicate purpose: `storageAccountName` not `saName`
- Resource names assembled from parameterized prefix + purpose + environment suffix
- Never hardcode resource names — always derive from parameters

### Parameter Decorators
- `@description('...')` on every parameter — no exceptions
- `@secure()` on all secrets, passwords, connection strings, and keys
- `@minLength()` / `@maxLength()` for string parameters with known bounds
- `@minValue()` / `@maxValue()` for numeric parameters with known bounds
- `@allowed([...])` for parameters with a fixed set of valid values (e.g., SKU names, environments)
- Use `@metadata({...})` for additional documentation when `@description` is not enough

### User-Defined Types
- Define types for complex parameter shapes instead of using multiple loose parameters
- Use union types for constrained string values: `type environment = 'dev' | 'staging' | 'prod'`
- Use typed objects for structured configuration: `type networkConfig = { vnetName: string, addressPrefix: string }`
- Export types from modules when they define a public interface

### Resource Definitions
- Always specify an explicit API version on every resource (e.g., `'Microsoft.Storage/storageAccounts@2023-05-01'`)
- Use the latest stable GA API version unless a preview feature is specifically required
- Use `existing` keyword for references to resources not created in this template
- Prefer implicit dependencies (property references) over explicit `dependsOn`
- Only use `dependsOn` when no property reference creates the needed ordering

### Conditional Deployments
- Use ternary expressions for optional resources: `resource ... = if (deployFirewall) { ... }`
- Use ternary for conditional property values: `sku: isProd ? 'Standard' : 'Basic'`
- Never create separate template files for conditional resources — use conditionals within a single template

### Output Patterns
- Expose only IDs, names, and endpoints that downstream consumers need
- Use `output ... = resource.id` or `output ... = resource.properties.endpoint`
- Document outputs with `@description()` decorator
- Never expose secrets in outputs — use Key Vault references instead

### Module References
- Local modules: `module ... './modules/storage.bicep' = { ... }`
- Registry modules: `module ... 'br:myregistry.azurecr.io/bicep/storage:v1' = { ... }`
- Template specs: `module ... 'ts:subscriptionId/resourceGroup/templateSpecName:version' = { ... }`
- Always pass required parameters explicitly — never rely on defaults for environment-specific values

### Secure Parameter Handling
- Never hardcode secrets, connection strings, API keys, or passwords in templates
- Use `@secure()` decorator on sensitive parameters
- Reference Key Vault secrets: `getSecret('<vaultName>', '<secretName>')`
- Use managed identity over connection strings wherever possible
- Never output `@secure()` parameter values or sensitive resource properties

### Scope Management
- Declare `targetScope` at the top of every file that is not resource-group scoped
- Use `scope:` property on modules for cross-scope deployments
- Use `resourceGroup()` function for deploying to a different resource group within the same subscription

## Project Conventions

Key conventions for Bicep projects (the context brief overrides these if different):
- One module per logical component or reusable resource pattern
- Parameter files per environment: `dev.bicepparam`, `staging.bicepparam`, `prod.bicepparam`
- Modules organized in a `modules/` directory; main entry point is `main.bicep`
- All resources tagged with: `environment`, `owner`, `costCenter`, `project`
- Use `var` for computed values derived from parameters — keep parameter count manageable
- Prefer composition (modules calling modules) over monolithic templates
- Keep templates under 200 lines; extract to modules if larger
