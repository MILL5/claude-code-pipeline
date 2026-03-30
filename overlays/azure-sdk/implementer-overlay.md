# Azure SDK Implementer Rules

## Code Quality Rules (Rule 4)

Within the boundaries of what the brief asks for, write clean Azure SDK integration code:

### Authentication
- Always use `DefaultAzureCredential` as the credential chain — it handles managed identity, Azure CLI, environment variables, and more
- Never hardcode API keys, connection strings, or shared access signatures
- Never pass credentials as constructor arguments when `DefaultAzureCredential` is available
- Use `ManagedIdentityCredential` directly only when you need to specify a user-assigned identity client ID
- Cache credential instances — do not create a new credential per request

### Client Management
- Reuse SDK clients: create once at startup (singleton or scoped lifetime), not per-request
- Configure retry policies with exponential backoff on all clients:
  - Python: `retry_total=3, retry_backoff_factor=0.8, retry_backoff_max=60`
  - JS/TS: `retryOptions: { maxRetries: 3, retryDelayInMs: 800, maxRetryDelayInMs: 60000 }`
  - .NET: `new RetryOptions(maxRetries: 3, delay: TimeSpan.FromSeconds(0.8))`
- Set reasonable timeouts on all network operations — never use unbounded timeouts
- Use connection pooling where the SDK supports it (HTTP pipeline is shared across clients of the same type)

### Key Vault Integration
- Use `SecretClient` for secret retrieval — never use the REST API directly
- Cache secrets with a TTL (5-15 minutes depending on rotation frequency)
- Never log secret values, connection strings, or access keys — not even at DEBUG level
- Use Key Vault references in App Configuration instead of duplicating secrets
- Handle `ResourceNotFoundException` gracefully when a secret does not exist or has been soft-deleted

### Connection Strings
- Always retrieve connection strings from Key Vault or App Configuration — never from config files or environment variables in production
- In local development, use `DefaultAzureCredential` to authenticate to Key Vault for secrets
- Never commit connection strings to source control — use `.env.example` with placeholder values
- Prefer managed identity (passwordless connections) over connection strings wherever the service supports it

### Resource Lifecycle
- Properly dispose of SDK clients when they are no longer needed:
  - Python: Use `async with` or `with` context managers for async/sync clients; call `.close()` in `finally` if not using context managers
  - JS/TS: Call `.close()` in `finally` blocks or use try-finally patterns
  - .NET: Use `using` blocks or `await using` for async disposal; implement `IDisposable`/`IAsyncDisposable` on wrapper classes
- Close `ServiceBusReceiver`, `ServiceBusSender`, and `ServiceBusClient` in the correct order (receiver first, then sender, then client)
- Return Cosmos DB client connections to the pool — do not hold references beyond the operation scope

### Error Handling
- Handle Azure SDK specific exceptions by type, not by catching generic `Exception`:
  - Python: `ResourceNotFoundError`, `ClientAuthenticationError`, `ServiceRequestError`, `HttpResponseError`
  - JS/TS: `RestError` with `statusCode` checks, `@azure/abort-controller` for cancellation
  - .NET: `RequestFailedException` with `Status` property, `Azure.Identity.AuthenticationFailedException`
- Retry transient errors (HTTP 429, 500, 503) — the SDK retry policy handles most, but verify configuration
- Do not retry authentication failures (401/403) — these indicate misconfiguration, not transient issues
- Log the `x-ms-request-id` header on failures for Azure support correlation

### Logging & Observability
- Use Azure Monitor / Application Insights SDK for telemetry — do not roll custom logging infrastructure
- Add correlation IDs to all cross-service operations — propagate via `traceparent` header or SDK built-in distributed tracing
- Use structured logging with consistent field names: `operationName`, `resourceName`, `durationMs`, `statusCode`
- Enable SDK-level logging for debugging (Python: `logging.getLogger('azure')`, .NET: `AzureEventSourceListener`)
- Never log request/response bodies that may contain PII or secrets

### Language-Specific SDK Patterns

#### Python (`azure-*` packages)
- Use `azure-identity` for `DefaultAzureCredential`
- Prefer async clients (`aio` submodule) for async applications: `from azure.servicebus.aio import ServiceBusClient`
- Use `azure-core` pipeline policies for cross-cutting concerns (logging, retry, custom headers)
- Pin Azure SDK package versions in `requirements.txt` or `pyproject.toml`

#### JavaScript/TypeScript (`@azure/*` packages)
- Use `@azure/identity` for `DefaultAzureCredential`
- All SDK methods return `Promise` — always `await` or handle the promise
- Use `@azure/abort-controller` for operation cancellation and timeouts
- Configure the SDK client with `{ retryOptions, userAgentOptions }` in the constructor

#### .NET (`Azure.*` packages)
- Use `Azure.Identity` for `DefaultAzureCredential`
- Register SDK clients via `Microsoft.Extensions.Azure` for dependency injection: `builder.Services.AddAzureClients()`
- Use `Azure.Core` pipeline policies for cross-cutting concerns
- Configure retry with `AzureClientOptions.Retry` property

### Resource Tagging
- Tag all Azure resources created programmatically with: `environment`, `owner`, `costCenter`, `project`
- Propagate tags from the deployment context — do not hardcode tag values
- Use consistent tag key casing (lowercase with hyphens or camelCase — match the project convention)

## Project Conventions

Key conventions for Azure SDK integration (the context brief overrides these if different):
- One service client wrapper per Azure service (e.g., `BlobStorageService`, `ServiceBusPublisher`)
- Configuration classes for each service client (connection details, retry policies, timeouts)
- Secrets and connection strings loaded from Key Vault at startup, cached in memory
- All Azure operations wrapped with correlation ID propagation
- Error handling follows the SDK exception hierarchy — no generic catches
- Managed identity preferred over connection strings in all environments except local development
