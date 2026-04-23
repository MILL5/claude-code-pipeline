# Bicep Essential Rules

Critical rules for Haiku execution. Violations will fail code review.

- Never run `git commit`/`git push` — orchestrator commits after review
- camelCase for parameters/variables/outputs, PascalCase for resource symbolic names
- `@description()` decorator on every parameter — no exceptions
- `@secure()` on all secrets, passwords, connection strings, and keys
- Always specify explicit API version on every resource (latest stable GA)
- Use `existing` keyword for references to resources not created in this template
- Prefer implicit dependencies over explicit `dependsOn`
- Never hardcode resource names, secrets, or environment-specific values
- Use modules for reusable components — one module per logical component
- Expose only IDs, names, and endpoints in outputs — never expose secrets
- Use ternary expressions for conditional deployments, not separate templates
- Tag all resources: environment, owner, costCenter, project
