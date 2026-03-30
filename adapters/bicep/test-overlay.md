# Bicep Test Patterns

## ARM-TTK (Template Test Toolkit) Patterns

Validate ARM template correctness and best practices:

### Test Structure
- ARM-TTK tests run against compiled ARM JSON (Bicep compiles to ARM before validation)
- Tests organized by category: deployment template tests, parameter file tests, createUIDefinition tests
- Run via PowerShell: `Test-AzTemplate -TemplatePath ./main.bicep`
- Each test returns Pass/Fail with descriptive messages

### Built-in Test Categories
- **Template validation**: Valid JSON structure, required properties, correct API versions
- **Parameter validation**: Every parameter used, no hardcoded values, secure handling
- **Resource validation**: Correct resource types, valid locations, proper dependencies
- **Output validation**: No secrets in outputs, valid output expressions

### Custom ARM-TTK Tests
- Place custom test scripts in `arm-ttk/testcases/deploymentTemplate/` directory
- Test functions follow naming convention: `<TestName>.test.ps1`
- Use `Test-AzTemplate -Test <TestName>` to run specific tests

## PSRule for Azure Patterns

Cloud-native validation using Azure Well-Architected Framework rules:

### Configuration
- Configure in `ps-rule.yaml` at project root:
  ```yaml
  binding:
    targetType:
      - type
      - resourceType
  rule:
    include:
      - Azure.*
  configuration:
    AZURE_BICEP_FILE_EXPANSION: true
    AZURE_PARAMETER_FILE_EXPANSION: true
  ```

### Rule Categories
- **Security baseline**: Encryption, network isolation, identity, access control
- **Cost optimization**: SKU selection, scaling configuration, resource sharing
- **Reliability**: Availability zones, redundancy, backup, health checks
- **Operational excellence**: Diagnostics, monitoring, tagging, naming

### Custom Rules
- Define in `.ps-rule/` directory with `.Rule.yaml` or `.Rule.ps1` extension
- Reference Azure resource types for targeting
- Use `Assert` for validation conditions with descriptive failure messages

### Baselines
- Use `Azure.Default` baseline for standard checks
- Create custom baselines to include/exclude specific rules
- Override rule configuration per environment via parameter files

## What-If Dry Run Patterns

Validate deployment impact without making changes:

### Running What-If
- Resource group scope: `az deployment group what-if --resource-group <rg> --template-file main.bicep --parameters @dev.bicepparam`
- Subscription scope: `az deployment sub what-if --location <loc> --template-file main.bicep`
- Interpret change types:
  - **Create**: New resource will be provisioned
  - **Delete**: Existing resource will be removed (danger — verify intent)
  - **Modify**: Existing resource properties will change (review property diff)
  - **NoChange**: Resource exists and matches template (ideal state)
  - **Ignore**: Resource exists but is not managed by this template
  - **Deploy**: Resource will be deployed (what-if cannot determine if it changes)

### Validation Tests from What-If
- Assert expected create/modify counts match planned changes
- Flag any unexpected Delete operations
- Verify no NoChange resources are being unnecessarily redeployed
- Check that sensitive properties are not changing unexpectedly

## Deployment Validation Tests (Post-Deploy)

Verify deployed resources match expected state:

### Pester Integration Tests
- Test file naming: `*.Tests.ps1` in a `tests/` directory
- Test structure:
  ```powershell
  Describe "Storage Account" {
      It "should exist" {
          $sa = Get-AzStorageAccount -ResourceGroupName $rg -Name $name
          $sa | Should -Not -BeNullOrEmpty
      }
      It "should enforce HTTPS" {
          $sa.EnableHttpsTrafficOnly | Should -Be $true
      }
  }
  ```
- Group tests by resource type or functional area
- Use `BeforeAll` blocks for resource lookup, share across tests in a `Describe` block

### az CLI Validation
- Use `az resource show` to verify resource existence and properties
- Use `az monitor diagnostic-settings list` to verify monitoring
- Use `az network nsg rule list` to verify network security
- Parse JSON output with `--query` (JMESPath) for specific assertions

## Anti-Patterns to Avoid
- Don't skip what-if validation before deploying to any environment
- Don't rely solely on ARM-TTK — it checks syntax, not architecture (use PSRule for that)
- Don't write post-deployment tests that duplicate what-if validation (test actual behavior instead)
- Don't hardcode resource group names or subscription IDs in test scripts — parameterize them
- Don't test individual resource properties already covered by PSRule baselines — focus on custom business rules
- Don't run what-if against production without verifying parameter files match the target environment
