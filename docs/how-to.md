# How-To Guide

Common workflows after the pipeline is bootstrapped in your project.

For per-stack setup details (Detection, Tools, Bootstrap output, Pitfalls), see the [adoption guides](adoption/) instead. For pipeline architecture, see [architecture.md](architecture.md). For backlog integration setup, see [backlog-integration.md](backlog-integration.md).

## Running the Full Pipeline

1. Start Claude Code: `claude`
2. Describe your feature: "Add user authentication with JWT tokens"
3. The pipeline automatically:
   - Analyzes your request and asks clarifying questions (1a)
   - Generates a cost-optimized plan with parallel waves (1b)
   - Presents the plan for your approval
   - Opens a draft PR
   - Implements each task with build + test verification
   - Reviews every implementation
   - Commits with conventional-commit messages
   - Asks you to manually test
   - Fixes any bugs you report
   - Finalizes the PR
   - Analyzes token usage and files a GitHub issue on the pipeline repo if it finds optimization opportunities

## Running Individual Skills

You don't have to use the full pipeline. Individual skills work standalone:

```
/build-runner                    # Build the project
/test-runner                     # Run tests with coverage
/open-pr                         # Create a branch + draft PR
/summarize-implementation        # Generate a commit message from current diff
/fix-defects                     # Fix defects reported on a PR
/chrome-ui-test                  # Browser UI smoke test (React UIs)
/bootstrap-backlog               # One-time: enable GitHub backlog integration
/update-pipeline                 # Update pipeline submodule to latest

# Azure skills (see docs/azure-guide.md for details)
/azure-login                     # Verify Azure auth and subscription context
/validate-bicep                  # Lint + build + what-if dry run
/deploy-bicep                    # Deploy with confirmation gate
/azure-cost-estimate             # Estimate monthly Azure costs
/security-scan                   # PSRule/Checkov security scan
/infra-test-runner               # ARM-TTK/Pester infrastructure tests
/azure-drift-check               # Detect config drift vs deployed state
```

## Updating the Pipeline

**Recommended:** Use the `/update-pipeline` skill from within Claude Code:

```
/update-pipeline
```

This automatically:
1. Pulls the latest pipeline version from the tracked branch
2. Shows a changelog of what changed
3. Re-runs `init.sh` if the bootstrap script changed
4. Copies any new local overlay templates
5. Runs structural validation against the new version
6. Commits the submodule bump (if validation passes)
7. Offers rollback if validation fails

**Manual update** (if not using the skill):

If cloned directly:
```bash
cd your-project/.claude/pipeline
git pull origin main
```

If using a submodule:
```bash
git submodule update --remote .claude/pipeline
git add .claude/pipeline
git commit -m "chore(pipeline): bump pipeline"
```

Updates take effect immediately — no re-init needed (symlinks point to the pipeline repo).

Re-run `init.sh --force` only if:
- You want to switch adapters (`--stack=different-stack`)
- The pipeline added new directories that need symlinking
- Hook structure changed and needs re-merging

## Resuming After Interruption

The pipeline creates recovery artifacts:
- `.claude/tmp/1a-spec.md` — Enriched spec from analysis (skips re-analysis)
- `.claude/tmp/1b-plan.md` — Full plan from Opus (skips expensive re-planning)

If interrupted, just say `/orchestrate` again. The pipeline detects existing artifacts and offers to resume.

## Manual Testing Feedback Loop

After implementation, the pipeline enters a manual testing phase:

1. You test the PR branch
2. Report bugs: "The timer doesn't start when I tap the button"
3. The orchestrator:
   - Assesses blast radius (simple vs complex fix)
   - Launches architect for complex bugs touching fragile areas
   - Fixes via implementer agent (Sonnet for fixes)
   - Reviews the fix
   - Runs full test suite with regression guard (test count must not drop)
   - Commits and pushes
4. You re-test
5. Say "tests pass" when satisfied

**Regression guards** prevent fixes from breaking other things:
- Test count baseline is recorded after initial implementation
- Every fix must maintain or increase the test count
- If a fix drops the count, it's rejected automatically
- After 3 fix cycles, the pipeline escalates to you for manual triage

## Structured Defect Reporting on PRs

For teams with dedicated testers or async review workflows, the pipeline supports structured defect reports as GitHub PR comments:

1. **Testers** copy the template from `templates/defect-report.md` into PR comments
2. Each defect has: severity (CRITICAL/HIGH/MEDIUM/LOW), steps to reproduce, expected/actual behavior, screenshots (drag-and-drop), environment info
3. **Developer** runs `/fix-defects` in Claude Code
4. The pipeline:
   - Reads all defect report comments from the PR via GitHub API
   - Validates required fields (replies to invalid reports with an error)
   - Triages by severity (CRITICAL first)
   - Runs blast-radius analysis for complex/critical defects
   - Fixes each defect (Sonnet for CRITICAL/HIGH/MEDIUM, Haiku for simple LOW)
   - Reviews each fix
   - Commits, pushes, and replies to the original comment with the fix commit
5. Summary report shows which defects were fixed and which need manual attention

This decouples testing from the pipeline session — testers report defects asynchronously on the PR, and the developer processes them all at once.

For the full guide (tester instructions, developer commands, severity definitions, screenshot tips, cost estimates, and a complete walkthrough), see **[testing-guide.md](testing-guide.md)**.
