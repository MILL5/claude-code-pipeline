---
step: "4"
requires: []
produces: []
sendmessage: n/a
---

# Step 4: FINALIZE

This file is read by the orchestrator just-in-time before executing Step 4.
The orchestrator's residual `SKILL.md` (Step Dispatch table) routes here. Shared
protocols (SendMessage notes, Step 0.6 token tracking, Backlog Integration) live
in `SKILL.md` and remain accessible.

After all tasks are committed and pushed:

1. If the changes affected architecture (new services, new targets, new patterns):
   - Update `ORCHESTRATOR.md` with the changes
   - Commit and push the update
2. Update the PR body's Coverage section with final numbers from the last test run
3. Check off completed tasks in the PR body's task list
3.5. If `BACKLOG_ENABLED=true` and `.claude/tmp/run-log.yml` has any entries with
   `action: folded`, render the "Folded in this run" checklist into the PR body
   (see the Backlog Integration section for the format). Skip this if no folds
   occurred.
4. Mark the PR as ready for review:
   ```bash
   gh pr ready <PR_NUMBER>
   ```
5. Report final status to user:
   - PR URL
   - Number of tasks completed
   - Number of commits made
   - Coverage summary from the last test run
   - Any review findings that were fixed

The orchestrator does NOT merge — the user decides when to merge.
