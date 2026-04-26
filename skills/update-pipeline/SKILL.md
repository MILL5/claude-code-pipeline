---
name: update-pipeline
description: >
  Updates the Claude Code Pipeline submodule to the latest version. Shows a changelog,
  validates structural integrity, and commits the submodule bump.
  Use when: "update pipeline", "upgrade pipeline", "/update-pipeline",
  "pull latest pipeline", "bump pipeline".
---

# Update Pipeline Skill

Updates the pipeline submodule to the latest version with validation and automatic rollback on failure.

## Step 1: Locate Pipeline and Detect Install Mode

The skill works for all three install types. Detect which is in use so Step 7 can commit
correctly (or skip the commit) at the end.

1. Read `pipeline_root` from `.claude/pipeline.config`. If `pipeline_root` does not start
   with `/`, resolve it against the project root (the directory containing `.claude/`).
   Record as `PIPELINE_PATH`.
2. If `PIPELINE_PATH/.git` does not exist, abort: "Pipeline not installed at `<PIPELINE_PATH>`.
   Re-run the bootstrap from the pipeline repo."
3. Classify `INSTALL_MODE`:
   - **`submodule`** — `.gitmodules` exists at the project root AND contains a submodule
     entry whose `path` matches `PIPELINE_PATH` (relative to project root). Record that
     relative path as `SUBMODULE_PATH` for Step 7.
   - **`submodule-orphaned`** — `PIPELINE_PATH/.git` is a **file** (a gitlink pointing at
     the parent repo's `modules/...` directory) AND `.gitmodules` is missing or has no
     matching entry. The parent repo has a stale submodule reference but the registration
     was lost. Warn the user: "Submodule registration at `<PIPELINE_PATH>` is inconsistent —
     `.git` is a gitlink but `.gitmodules` has no entry. Update will proceed in clone-semantics
     mode (no submodule bump will be committed). To repair, run:
     `git submodule add <pipeline_remote_url> <PIPELINE_PATH>` after the update completes."
     Treat this mode as `clone` for Step 7 purposes.
   - **`clone`** — `PIPELINE_PATH/.git` is a **directory** (a full clone). No submodule
     tracking, no parent-repo commit needed at the end.

Steps 2–6 below run identically for all three modes, operating on `PIPELINE_PATH`. Only
Step 7 branches on `INSTALL_MODE`.

## Step 2: Pre-Flight Checks

1. `cd <PIPELINE_PATH>`
2. Check for uncommitted changes: `git status --porcelain`
   - If dirty, abort: "Pipeline has uncommitted changes. Commit or discard them first."
3. Record current state:
   ```
   OLD_SHA=$(git rev-parse HEAD)
   OLD_VERSION=$(cat VERSION 2>/dev/null || echo "unknown")
   OLD_INIT_SHA=$(git log -1 --format=%H -- init.sh)
   ```

## Step 3: Pull Latest

1. Fetch from remote: `git fetch origin`
2. Determine the tracked branch:
   ```
   BRANCH=$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null | sed 's|origin/||' || echo "main")
   ```
3. Attempt fast-forward merge: `git merge origin/$BRANCH --ff-only`
4. If merge fails (non-fast-forward):
   - Warn the user: "Pipeline has diverged from the remote branch. This usually means local
     changes were made to the pipeline checkout. Resolve manually with:
     `cd <PIPELINE_PATH> && git log --oneline origin/$BRANCH..HEAD` to see local commits."
   - Abort — do NOT force-reset.

## Step 4: Show Changelog

1. Record new state:
   ```
   NEW_SHA=$(git rev-parse HEAD)
   NEW_VERSION=$(cat VERSION 2>/dev/null || echo "unknown")
   ```
2. If `OLD_SHA == NEW_SHA`:
   - Report: "Pipeline is already up to date (version $OLD_VERSION)."
   - Stop here.
3. Show the changelog:
   ```
   git log --oneline $OLD_SHA..$NEW_SHA
   ```
4. Report version change: "Pipeline: $OLD_VERSION → $NEW_VERSION"
5. Show file-level summary: `git diff --stat $OLD_SHA..$NEW_SHA`

## Step 5: Re-Bootstrap if Needed

1. Check if init.sh changed:
   ```
   NEW_INIT_SHA=$(git log -1 --format=%H -- init.sh)
   ```
2. If `OLD_INIT_SHA != NEW_INIT_SHA`:
   - Inform user: "init.sh has changed — re-running bootstrap to update config and symlinks."
   - Run: `bash <PIPELINE_PATH>/init.sh <project_root> --force`
   - Report the init.sh output.
3. Regardless of init.sh changes, check for new local templates:
   - For each file in `<PIPELINE_PATH>/templates/local/*.template`:
     - Extract the base name (e.g., `project-overlay.md` from `project-overlay.md.template`)
     - If `.claude/local/<base_name>` does not exist, copy the template
     - Report any new files created

## Step 6: Validate

1. Run structural validation: `python3 <PIPELINE_PATH>/tests/validate_structure.py`
2. If validation **passes**: proceed to Step 7.
3. If validation **fails**:
   - Show the failure output to the user.
   - Warn: "Structural validation failed after update. The new pipeline version may require
     migration steps not covered by this update."
   - Ask the user: "Would you like to roll back to the previous version ($OLD_VERSION, $OLD_SHA)?"
   - If user says **yes**:
     ```
     cd <PIPELINE_PATH>
     git checkout $OLD_SHA
     ```
     Report: "Rolled back to $OLD_VERSION."
   - If user says **no**: proceed without committing. Report: "Keeping new version but NOT
     committing. Fix the validation issues, then (for submodule installs) run
     `git add <SUBMODULE_PATH> && git commit`."

## Step 7: Commit (submodule mode only)

Behavior branches on the `INSTALL_MODE` captured in Step 1.

### `INSTALL_MODE=submodule`

1. Return to project root: `cd <project_root>`
2. Stage the submodule: `git add <SUBMODULE_PATH>`
3. If init.sh was re-run (Step 5), also stage any changed config files:
   ```
   git add .claude/pipeline.config .claude/settings.json
   ```
   And any new local template files that were copied.
4. Commit:
   ```
   git commit -m "chore(pipeline): update claude-code-pipeline to v$NEW_VERSION"
   ```
5. Report:
   - "Pipeline updated: $OLD_VERSION → $NEW_VERSION"
   - "Commit created but NOT pushed. Review the changes, then push when ready."
   - If init.sh was re-run: "Config and symlinks were also updated."

### `INSTALL_MODE=clone` or `INSTALL_MODE=submodule-orphaned`

No parent-repo submodule bump to commit — the pipeline checkout at `<PIPELINE_PATH>` is not
registered as a submodule in this project.

1. If init.sh was re-run (Step 5), the config and symlinks in `.claude/` may have changed.
   Remind the user: "init.sh re-ran — review `git status` and commit any changes under
   `.claude/` yourself if they should be tracked."
2. Report:
   - "Pipeline updated at `<PIPELINE_PATH>`: $OLD_VERSION → $NEW_VERSION"
   - "No submodule bump committed — pipeline is a `<INSTALL_MODE>` install."
   - For `submodule-orphaned`: repeat the repair hint from Step 1 so the user can fix the
     inconsistency at their leisure.

## Error Handling

- **Network failure during fetch**: Report the error and suggest the user check connectivity.
- **Merge conflict**: Never force-resolve. Report and suggest manual resolution.
- **Validation failure**: Always offer rollback. Never auto-commit a broken state.
- **Missing VERSION file**: Treat version as "unknown" — the skill still works, just without
  version numbers in messages.
- **Pipeline at unexpected path**: The skill reads `pipeline_root` from
  `.claude/pipeline.config` and resolves it against the project root, so it works regardless
  of where the pipeline lives (e.g., `pipeline/`, `.claude/pipeline/`, `tools/pipeline/`,
  or an absolute path for legacy clone installs).
