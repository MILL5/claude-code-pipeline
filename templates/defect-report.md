# Defect Report Template

Copy this template into a GitHub PR comment to report a defect found during manual testing.
The `/fix-defects` command parses these comments and runs the pipeline to fix them.

---

**Copy everything below this line into a PR comment:**

---

```markdown
### DEFECT REPORT

**Severity:** CRITICAL | HIGH | MEDIUM | LOW
**Component:** <area of the app affected, e.g., "login flow", "dashboard chart", "API /users endpoint">
**Found in:** <file or screen where the defect was observed>

#### Steps to Reproduce

1. <first step>
2. <second step>
3. <third step>

#### Expected Behavior

<What should happen>

#### Actual Behavior

<What actually happens — be specific about error messages, visual glitches, incorrect data, etc.>

#### Screenshots

<!-- Drag and drop images here, or use GitHub image syntax: -->
<!-- ![description](image-url) -->

#### Environment

- **Browser/Device:** <e.g., Chrome 120, iPhone 15 Pro, macOS Sequoia>
- **OS:** <if relevant>
- **Build:** <commit SHA or branch state when tested>

#### Additional Context

<!-- Optional: stack traces, console errors, related issues, workarounds found -->
```

---

## Schema Rules

The `/fix-defects` command identifies defect reports by the `### DEFECT REPORT` header.
Multiple defects can be filed as separate comments on the same PR.

**Required fields** (parsing fails without these):
- `Severity` — must be one of: CRITICAL, HIGH, MEDIUM, LOW
- `Steps to Reproduce` — at least one numbered step
- `Expected Behavior` — non-empty
- `Actual Behavior` — non-empty

**Optional fields:**
- `Component` — helps the pipeline correlate to plan tasks/files
- `Found in` — narrows the search scope for the fix
- `Screenshots` — GitHub image URLs, passed to the fix agent for visual context
- `Environment` — included in the fix agent's context
- `Additional Context` — included verbatim in the fix agent's context

**Severity definitions:**
| Level | Meaning | Pipeline behavior |
|-------|---------|-------------------|
| CRITICAL | App crashes, data loss, security hole | Fixed first, Sonnet model, architect blast-radius analysis |
| HIGH | Feature broken, major UX regression | Fixed in severity order, Sonnet model |
| MEDIUM | Minor UX issue, cosmetic but noticeable | Fixed after HIGH, Sonnet model |
| LOW | Cosmetic, nice-to-have improvement | Fixed last, may use Haiku for simple fixes |

**Image support:**
- Drag-and-drop images directly into the GitHub comment (recommended)
- Use `![description](url)` markdown syntax
- Multiple images supported — each is passed to the fix agent
- The fix agent receives image URLs as context but cannot view images directly; include a text description of what the image shows in the Actual Behavior field
