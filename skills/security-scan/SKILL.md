---
name: security-scan
description: >
  Run security and compliance scans against Bicep/ARM templates using PSRule for Azure
  or Checkov. Reports misconfigurations, policy violations, and security findings.
  Use before deployment or during code review.
---

# Security Scan

Runs security and compliance scans against Bicep and ARM templates, reporting misconfigurations, policy violations, and security findings using the Azure Well-Architected Framework and CIS benchmarks.

## Tools

- **PSRule for Azure** (preferred) — validates against Azure Well-Architected Framework rules. Requires `ps-rule.yaml` config for Bicep file expansion.
- **Checkov** (fallback) — validates against CIS Azure benchmarks. Runs without config.
- Both can be run together for comprehensive coverage.

The scanner auto-detects which tools are available and uses the best option.

## How to Run

1. Detect available scanners:
   ```bash
   # Check for PSRule
   pwsh -Command "Get-Module -ListAvailable PSRule.Rules.Azure" 2>/dev/null

   # Check for Checkov
   checkov --version 2>/dev/null
   ```

2. Run the available scanner against all `.bicep` files:

   **PSRule:**
   ```bash
   pwsh -Command "Assert-PSRule -Module PSRule.Rules.Azure -InputPath . -Format File"
   ```

   **Checkov:**
   ```bash
   checkov --directory . --framework bicep --output cli
   ```

3. Collect and format findings into the output contract.

## Output Contract

```
SECURITY SCAN | Total: N findings | Critical: N, High: N, Medium: N, Low: N

Rule                          Severity  Resource                  Description                              Recommendation
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
Azure.Storage.MinTLS          HIGH      myStorageAccount          TLS version below 1.2                    Set minimumTlsVersion to 'TLS1_2'
Azure.KeyVault.SoftDelete     MEDIUM    myKeyVault                Soft delete not enabled                  Enable soft delete with 90-day retention
```

- Findings are sorted by severity (Critical > High > Medium > Low).
- Each finding includes a concrete remediation recommendation.
- Exit code 0 = no critical/high findings, 1 = critical or high findings present.

## Integration

- Findings can feed into the code-reviewer agent context for IaC reviews.
- Critical findings should block deployment via the deploy-bicep skill.
- Results can be posted as PR comments for visibility.

## Important Notes

- PSRule requires a `ps-rule.yaml` configuration file for Bicep file expansion. Without it, only pre-compiled ARM JSON is scanned.
- Checkov runs without configuration and supports Bicep natively.
- Some rules may produce false positives for resources that rely on Azure Policy for enforcement. Suppress known false positives via rule configuration, not by ignoring findings.
