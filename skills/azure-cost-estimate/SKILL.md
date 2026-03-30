---
name: azure-cost-estimate
description: >
  Estimate monthly Azure costs from Bicep templates. Parses resource types and SKUs
  to produce a cost breakdown. Use before deploying to understand cost impact.
---

# Azure Cost Estimate

Parses Bicep templates to extract resource types, SKUs, and regions, then queries the Azure Retail Pricing API to produce an estimated monthly cost breakdown.

## How It Works

1. Read Bicep files and compile to ARM JSON if needed (`bicep build`).
2. Extract resource types, SKU/tier information, and target regions from the compiled templates.
3. Query the Azure Retail Pricing API for each resource type + SKU + region combination.
4. Aggregate and present the cost breakdown.

## How to Run

1. Read the target Bicep files to identify all resource definitions.
2. Compile to ARM JSON if SKU details are parameterized:
   ```bash
   az bicep build --file <path/to/main.bicep> --stdout
   ```
3. Query pricing for each resource:
   ```
   https://prices.azure.com/api/retail/prices?$filter=serviceName eq '<service>' and skuName eq '<sku>' and armRegionName eq '<region>'
   ```
4. Compile results into the output contract format.

## Output Contract

```
COST ESTIMATE | Total: $X.XX/month

Resource                   Type                                SKU          Region        Est. Monthly
────────────────────────────────────────────────────────────────────────────────────────────────────────
myStorageAccount           Microsoft.Storage/storageAccounts   Standard_LRS eastus        $21.00
myAppService               Microsoft.Web/servingSites          P1v3         eastus        $138.00
myCosmosDb                 Microsoft.DocumentDB/databaseAccts  Standard     eastus        $25.00-$500.00*

* Consumption-based resources show estimate ranges based on typical usage tiers.
```

## Limitations

- **Estimates only** — actual costs depend on usage, data transfer, and transactions.
- Consumption-based resources (Functions, Cosmos DB, Event Hubs) show ranges based on typical usage tiers, not exact costs.
- Marketplace and third-party resource costs are not included.
- Prices are retail (pay-as-you-go); enterprise agreements, reservations, and savings plans may differ significantly.
- The Azure Retail Pricing API is public and does not require authentication.
- Currency defaults to USD. Regional pricing variations are accounted for.
