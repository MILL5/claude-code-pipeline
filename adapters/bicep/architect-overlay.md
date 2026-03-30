# Bicep Architect Context

## Project Context

This is an Azure Bicep (Infrastructure as Code) project. When planning, account for:
- Module structure and dependency chains — circular module references are a deployment failure mode
- Scope hierarchy: management group → subscription → resource group → resource
- Azure resource provider API versions and feature availability by region
- The 4-file rule: tasks touching more than 3 files must be split into smaller tasks

## Module Decomposition Patterns

When planning tasks that involve Bicep modules, account for their specific complexity:

- **Single resource definitions** (Haiku): Adding a resource to an existing template, updating parameters, adding outputs, modifying a single module
- **Module interface design** (Sonnet): Defining parameter/output contracts between modules, designing reusable module libraries, establishing naming conventions across templates
- **Cross-module dependency chains** (Sonnet): Resource references across modules, deployment ordering, `existing` keyword patterns, output-to-parameter wiring
- **Multi-subscription landing zone patterns** (Opus): Hub-spoke networking, management group hierarchies, policy assignments, cross-subscription resource references

## Scope Hierarchy Patterns

- **Resource-group scoped** (Haiku): Standard resource deployments with `targetScope = 'resourceGroup'` (default)
- **Subscription scoped** (Sonnet): Resource group creation, policy assignments, role assignments at subscription level with `targetScope = 'subscription'`
- **Management-group scoped** (Sonnet/Opus): Policy definitions, blueprint assignments, cross-subscription governance with `targetScope = 'managementGroup'`
- **Tenant scoped** (Opus): Management group hierarchy, tenant-wide policy, cross-tenant patterns with `targetScope = 'tenant'`

## Resource Dependency Patterns

- **Implicit dependencies** (Haiku): Resource property references automatically create dependencies — prefer these over explicit `dependsOn`
- **Explicit `dependsOn`** (Haiku): Only when no property reference exists between resources but ordering is still required
- **`existing` keyword** (Haiku): Referencing pre-existing resources that are not created in this deployment
- **Cross-scope references** (Sonnet): Using `resourceGroup()`, `subscription()`, or `tenant()` scope functions for cross-scope deployments
- **Deployment scripts** (Sonnet): `Microsoft.Resources/deploymentScripts` for custom provisioning logic that Bicep cannot express declaratively

## Common Architecture Patterns

- **Hub-spoke networking** (Sonnet/Opus): Central hub VNet with shared services, spoke VNets peered to hub, NSG/UDR management
- **Shared services module** (Sonnet): Key Vault, Log Analytics, Application Insights as a reusable module consumed by other deployments
- **Environment parameterization** (Haiku/Sonnet): Single template set with `.bicepparam` files per environment (dev, staging, prod)
- **Module registry** (Sonnet): Publishing reusable modules to an Azure Container Registry for cross-project consumption
- **Conditional deployments** (Haiku): Using ternary expressions for optional resources based on parameters

## Bicep-Specific Decomposition Notes

- Module boundaries are natural Haiku boundaries — define the module interface (Sonnet if non-trivial), then implement each module as a separate Haiku task
- Parameter file design is Sonnet (establishing the contract); adding individual parameter values is Haiku
- User-defined types define contracts — designing the type is Sonnet, using it in resources is Haiku
- Networking topology is always Sonnet or Opus; individual NSG rules or route tables are Haiku
- Policy definitions are Sonnet; policy assignments to scopes are Haiku
