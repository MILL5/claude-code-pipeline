# Azure SDK Essential Rules

Critical rules for Haiku execution. Violations will fail code review.

- Always use `DefaultAzureCredential` — never hardcode keys or connection strings
- Reuse SDK clients (singleton/scoped) — never create per-request
- Configure retry policies with exponential backoff on all clients
- Retrieve secrets from Key Vault only — never from config files in production
- Use managed identity over connection strings wherever supported
- Dispose/close SDK clients properly (context managers, using blocks, finally)
- Tag all resources: environment, owner, costCenter, project
- Use RBAC role assignments over access keys or shared access signatures
- Propagate correlation IDs on all cross-service operations
- Never log secrets, connection strings, or request bodies with PII
