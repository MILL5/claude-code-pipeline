---
step: "3"
requires: []
produces: []
sendmessage: n/a
---

# Step 3: COMMIT + PUSH

This file is read by the orchestrator just-in-time before executing Step 3.
The orchestrator's residual `SKILL.md` (Step Dispatch table) routes here. Shared
protocols (SendMessage notes, Step 0.6 token tracking, Backlog Integration) live
in `SKILL.md` and remain accessible.

For each agent that completed successfully (after passing review):

1. Stage the agent's modified files: `git add <files>`
2. Commit using the agent's SUCCESS message verbatim (everything after the `SUCCESS\n\n` header)
3. Do NOT modify the commit message — use it exactly as returned
4. Push to the PR branch: `git push`

If multiple agents completed in the same wave, commit them in task order (1.1 before 1.2, etc.).

```bash
git add <files from agent>
git commit -m "<SUCCESS message from agent>"
git push
```

Pushing after each commit keeps the draft PR up to date so progress is visible.

**Record test baseline:** After committing all waves, run the full test suite and record
the total passing test count. This is the regression baseline for Step 3.5.
