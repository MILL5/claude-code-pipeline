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

## Step 1: Locate Pipeline

1. Check if `.gitmodules` exists in the project root.
2. If it exists, find the submodule entry whose `path` matches the pipeline (look for a path
   that contains `pipeline` or matches the `pipeline_root` from `.claude/pipeline.config`).
3. Extract the submodule `path` (e.g., `pipeline` or `.claude/pipeline`).
4. If `.gitmodules` does not exist or no pipeline submodule is found:
   - Read `pipeline_root` from `.claude/pipeline.config`
   - **Resolve:** if `pipeline_root` does not start with `/`, resolve it against the project root (the directory containing `.claude/`).
   - Check if that path is a git repository (`git -C <path> rev-parse --is-inside-work-tree`)
   - If it is a plain clone (not a submodule), inform the user:
     "Pipeline is not installed as a submodule. To update manually:
     `cd <pipeline_root> && git pull origin main`
     Then re-run `bash <pipeline_root>/init.sh . --force` if init.sh changed."
   - Stop here.

## Step 2: Pre-Flight Checks

1. `cd <submodule_path>`
2. Check for uncommitted changes: `git status --porcelain`
   - If dirty, abort: "Pipeline submodule has uncommitted changes. Commit or discard them first."
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
     changes were made to the submodule. Resolve manually with:
     `cd <submodule_path> && git log --oneline origin/$BRANCH..HEAD` to see local commits."
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
   - Run: `bash <submodule_path>/init.sh <project_root> --force`
   - Report the init.sh output.
3. Regardless of init.sh changes, check for new local templates:
   - For each file in `<submodule_path>/templates/local/*.template`:
     - Extract the base name (e.g., `project-overlay.md` from `project-overlay.md.template`)
     - If `.claude/local/<base_name>` does not exist, copy the template
     - Report any new files created

## Step 6: Validate

1. Run structural validation: `python3 <submodule_path>/tests/validate_structure.py`
2. If validation **passes**: proceed to Step 7.
3. If validation **fails**:
   - Show the failure output to the user.
   - Warn: "Structural validation failed after update. The new pipeline version may require
     migration steps not covered by this update."
   - Ask the user: "Would you like to roll back to the previous version ($OLD_VERSION, $OLD_SHA)?"
   - If user says **yes**:
     ```
     cd <submodule_path>
     git checkout $OLD_SHA
     ```
     Report: "Rolled back to $OLD_VERSION."
   - If user says **no**: proceed without committing. Report: "Keeping new version but NOT
     committing. Fix the validation issues, then run `git add <submodule_path> && git commit`."

## Step 7: Commit Submodule Bump

1. Return to project root: `cd <project_root>`
2. Stage the submodule: `git add <submodule_path>`
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

## Error Handling

- **Network failure during fetch**: Report the error and suggest the user check connectivity.
- **Merge conflict**: Never force-resolve. Report and suggest manual resolution.
- **Validation failure**: Always offer rollback. Never auto-commit a broken state.
- **Missing VERSION file**: Treat version as "unknown" — the skill still works, just without
  version numbers in messages.
- **Submodule at unexpected path**: The skill discovers the path from `.gitmodules`, so it
  works regardless of where the submodule is located (e.g., `pipeline/`, `.claude/pipeline/`,
  `tools/pipeline/`).
