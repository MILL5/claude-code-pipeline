# Azure SDK Architect Context

## Project Context

This project integrates with Azure services via the Azure SDK. When planning, account for:
- Azure service dependencies and their availability/latency characteristics
- Authentication chain design — managed identity is the default, fallback strategies must be explicit
- Network topology constraints — private endpoints, VNet integration, DNS resolution
- The 4-file rule: tasks touching more than 3 files must be split into smaller tasks

## Azure Service Integration Patterns

When planning tasks that involve Azure services, account for their specific integration complexity:

### Service Bus
- **Single queue/topic sender or receiver** (Haiku): Sending or receiving messages from a known queue/topic with a configured client
- **Session-based messaging** (Sonnet): Ordered message processing, session state management, session lock renewal
- **Dead-letter queue processing and poison message handling** (Sonnet): DLQ monitoring, retry policies, alerting on DLQ depth
- **Cross-service message choreography** (Opus): Saga patterns, compensation logic, multi-topic event flows

### Event Grid
- **Single event subscription handler** (Haiku): Webhook endpoint receiving a known event type
- **Custom event schema design** (Sonnet): Event type taxonomy, schema versioning, filtering rules
- **Multi-source event routing** (Sonnet/Opus): System topics + custom topics, dead-letter destinations, event delivery guarantees

### Cosmos DB
- **Single container CRUD operations** (Haiku): Point reads, upserts, simple queries against a known container
- **Partition key strategy and data modeling** (Sonnet): Access patterns, partition key selection, denormalization decisions
- **Cross-partition queries and change feed processing** (Sonnet): Fan-out queries, change feed processors, materialized views
- **Multi-region write conflict resolution** (Opus): Conflict resolution policies, consistency level selection, failover handling

### Blob Storage
- **Single blob upload/download** (Haiku): Uploading or downloading a known blob with a configured client
- **Lifecycle management and tiering** (Sonnet): Hot/cool/archive policies, access patterns, cost optimization
- **Event-driven blob processing pipelines** (Sonnet): Blob triggers, Event Grid integration, large file chunked uploads

### App Configuration
- **Reading feature flags or configuration values** (Haiku): Single key-value retrieval with a configured client
- **Feature flag design and configuration schema** (Sonnet): Feature flag taxonomy, label strategy, configuration refresh patterns
- **Dynamic configuration with Sentinel keys** (Sonnet): Configuration refresh triggers, cache invalidation, multi-environment label strategy

## Managed Identity Design

- **System-assigned identity** (Haiku): Enable on a single resource, assign a role — use when the resource has a 1:1 relationship with its identity
- **User-assigned identity** (Sonnet): Create a shared identity, assign to multiple resources — use when multiple resources need the same permissions or when identity must survive resource recreation
- **Role assignment patterns** (Sonnet): Principle of least privilege, scope role assignments to specific resources (not resource groups), use built-in roles over custom where possible
- **Cross-subscription identity** (Opus): Federated identity, cross-tenant access, workload identity federation for CI/CD

## Key Vault Integration

- **Secret retrieval** (Haiku): Using `SecretClient` to read a known secret with caching
- **Key/certificate management** (Sonnet): Key rotation strategy, certificate auto-renewal, versioning
- **Reference patterns** (Sonnet): App Configuration Key Vault references, App Service Key Vault references, resolving at startup vs on-demand
- **Access policies vs RBAC** (Sonnet): Prefer RBAC model over access policies, scope permissions per secret/key/certificate

## Network Architecture

- **Private endpoint for a single service** (Haiku): Creating a private endpoint connection and DNS record for one Azure service
- **VNet integration design** (Sonnet): Subnet planning, service endpoints vs private endpoints, NSG rules for Azure service traffic
- **DNS resolution for private endpoints** (Sonnet): Private DNS zones, DNS forwarding, hybrid DNS with on-premises
- **Multi-region networking** (Opus): VNet peering, hub-spoke topology, Traffic Manager/Front Door routing, cross-region private endpoint access

## Multi-Region Patterns

- **Active-passive failover** (Sonnet): Primary region with standby, data replication, manual or automated failover
- **Active-active** (Opus): Traffic Manager/Front Door routing, data consistency across regions, conflict resolution
- **Geo-replication** (Sonnet): Cosmos DB multi-region writes, Storage GRS/GZRS, SQL geo-replication
- **Traffic Manager vs Front Door** (Sonnet): DNS-based vs proxy-based routing, Layer 4 vs Layer 7, caching and WAF considerations

## Azure SDK Decomposition Notes

- Single-service integrations are natural Haiku boundaries — define the client configuration (Sonnet if non-trivial), then implement each operation as a separate Haiku task
- Authentication design is always Sonnet (choosing the credential chain, role assignments, Key Vault access); using `DefaultAzureCredential` in a client is Haiku
- Cross-service orchestration (e.g., Service Bus trigger that writes to Cosmos DB and publishes to Event Grid) is Sonnet — each individual service call is Haiku but the coordination logic requires judgment
- Multi-region architecture is always Opus; single-region deployment of an already-designed pattern is Sonnet
- Retry and resilience policy design is Sonnet; applying a configured retry policy to a client is Haiku
