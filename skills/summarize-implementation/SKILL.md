---
name: summarize-implementation
description: Generates a concise, conventional-commit-formatted summary of implementation work. Output is ready to use as a git commit message with no further editing. Invoke after completing an implementation task.
allowed-tools: Read, Grep, Glob, Bash
disable-model-invocation: false
---

# Summarize Implementation

Generate a git commit message for the work just completed.

## Process

1. Run `git diff --cached --stat` and `git diff --stat` to see what files changed
2. Run `git diff --cached` and `git diff` to see the actual changes
3. If a plan file path was provided in $ARGUMENTS, read it for task context
4. Produce the commit message

## Output Rules

- Output ONLY the commit message. No preamble, no explanation, no markdown fencing, no quotes.
- The first line is the subject: `<type>(<scope>): <imperative summary>` — max 72 characters
- Types: feat, fix, refactor, test, docs, chore, perf, style, ci, build
- Scope: the module, component, or area affected (1-2 words)
- Subject uses imperative mood ("add", "fix", "remove" — not "added", "fixes", "removed")
- If the change is non-trivial, add a blank line then a body
- Body is 2-5 bullet points, each starting with `-`
- Each bullet is one line, max 80 characters
- Bullets state WHAT changed and WHY, never HOW (the diff shows how)
- No bullet for trivial changes like imports or formatting that support the main change
- If there are breaking changes, add a final line: `BREAKING CHANGE: <description>`
- Total message must not exceed 15 lines

## Examples

Simple change:
```
feat(auth): add JWT refresh token rotation
```

Multi-file change:
```
feat(auth): add JWT refresh token rotation

- Add refresh endpoint that issues new token pair on valid refresh
- Store token family ID to detect reuse and revoke compromised chains
- Expire refresh tokens after 7 days of inactivity
```

Bug fix:
```
fix(payments): prevent duplicate charge on retry timeout

- Check idempotency key before submitting to Stripe
- Return cached response for duplicate requests within 5min window
```

## Anti-patterns (never do these)

- "This commit adds..." — no meta-commentary
- "Updated files: auth.ts, token.ts, ..." — the diffstat shows this
- "As part of the authentication feature..." — no narrative context
- Bullet points that describe every single line changed
- Wrapping the output in ```backticks``` or quotes
