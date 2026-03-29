# Manual Testing & Defect Reporting Guide

This guide covers the end-to-end workflow for manual testing of pipeline PRs: how testers report defects and how developers process them through the automated fix pipeline.

## Overview

The pipeline supports a structured feedback loop between manual testers and the automated fix pipeline:

```
Tester files defect on PR  ──>  Developer runs /fix-defects  ──>  Pipeline fixes each defect
        │                              │                                    │
        │  (structured comment         │  (reads PR comments,              │  (assess → fix →
        │   on GitHub PR)              │   parses, triages)                │   review → commit)
        v                              v                                    v
   PR comment with                Pipeline processes              Reply on PR comment
   defect report                  defects by severity             with fix commit SHA
```

Testers don't need Claude Code or any pipeline tooling — they just comment on the PR using a structured template. The developer processes all accumulated defects in a single `/fix-defects` run.

## For Testers: Filing Defect Reports

### Prerequisites

- Access to the GitHub PR you're testing
- The PR branch checked out locally (or access to a deployed preview)

### Step 1: Test the PR branch

Check out the PR branch and test the changes. When you find a defect, file it as a comment on the PR.

### Step 2: Copy the template

Copy the template below into a **new comment** on the PR. File one defect per comment — this allows the pipeline to track, fix, and reply to each independently.

```markdown
### DEFECT REPORT

**Severity:** CRITICAL
**Component:** login flow
**Found in:** src/auth/login.ts

#### Steps to Reproduce

1. Navigate to the login page
2. Enter valid credentials and click "Sign In"
3. Observe the result

#### Expected Behavior

User should be redirected to the dashboard after successful login.

#### Actual Behavior

The app crashes with a white screen. Console shows TypeError at login.ts:42.

#### Screenshots

<!-- Drag and drop images directly into this comment, or: -->
![description of what the image shows](image-url)

#### Environment

- **Browser/Device:** Chrome 120, macOS Sequoia 15.2
- **OS:** macOS 15.2
- **Build:** abc1234

#### Additional Context

This was working before the auth refactor commits.
```

### Step 3: Fill in the fields

#### Required fields

These four fields must be present and non-empty. If any are missing, the pipeline skips the defect and leaves an error reply on your comment.

| Field | What to write |
|-------|--------------|
| **Severity** | One of: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` (see severity guide below) |
| **Steps to Reproduce** | Numbered list. Be specific — "click the button" is better than "interact with the UI" |
| **Expected Behavior** | What should happen when following the steps |
| **Actual Behavior** | What actually happens. Include error messages, visual descriptions, data inconsistencies |

#### Optional fields

| Field | When to include |
|-------|----------------|
| **Component** | Always recommended. Helps the pipeline narrow its search (e.g., "login flow", "dashboard chart", "API /users endpoint") |
| **Found in** | Include if you know the file or screen (e.g., `src/auth/login.ts`, "Settings > Profile page") |
| **Screenshots** | Highly recommended for visual defects. Drag-and-drop images into the comment — GitHub handles hosting |
| **Environment** | Include browser, device, and OS when relevant. Always include the commit SHA or branch state |
| **Additional Context** | Stack traces, console errors, workarounds, links to related issues |

### Choosing a severity level

| Severity | Use when | Examples |
|----------|----------|---------|
| **CRITICAL** | App crashes, data loss, security vulnerability, complete feature breakage | White screen of death, data corruption, auth bypass, unrecoverable error |
| **HIGH** | Feature doesn't work as intended, major UX regression | Button does nothing, chart shows wrong data, form validation broken |
| **MEDIUM** | Feature works but has noticeable UX issues | Missing toast notification, misaligned layout, slow response with no loading state |
| **LOW** | Cosmetic issues, minor polish items | Off-by-one pixel alignment, slightly wrong color shade, typo in non-critical text |

When in doubt, go one level higher — the pipeline adjusts its approach based on severity.

### Adding screenshots

Screenshots dramatically improve fix accuracy. Three methods:

1. **Drag and drop** (recommended): Drag an image file directly into the GitHub comment box. GitHub uploads it and inserts the markdown automatically.

2. **Paste from clipboard**: Take a screenshot (Cmd+Shift+4 on Mac, Win+Shift+S on Windows), then paste (Cmd+V / Ctrl+V) into the comment box.

3. **Manual markdown**: If you have an image URL:
   ```markdown
   ![description of what the screenshot shows](https://your-image-url.png)
   ```

Since the fix agent receives image URLs but may not be able to view them directly, always describe what the image shows in the **Actual Behavior** field. For example: "The chart renders as an empty white box (see screenshot)."

### Tips for effective defect reports

- **One defect per comment.** This allows the pipeline to fix, commit, and reply to each independently.
- **Be specific in Steps to Reproduce.** Include exact input values, click targets, and navigation paths.
- **Include error messages verbatim.** Copy-paste console errors, stack traces, or error dialogs.
- **Describe the visual state.** "The button is gray and disabled" is more useful than "the button doesn't work."
- **Note if it's a regression.** If it was working before, say so — this helps the pipeline assess blast radius.
- **Include the commit SHA.** This pins the defect to a specific build and prevents confusion if the branch is updated.

### What happens after you file

1. The developer runs `/fix-defects` (you don't need to do anything)
2. For each valid defect, the pipeline:
   - Assesses blast radius and correlates to codebase files
   - Fixes the defect via an implementer agent
   - Reviews the fix via a code-reviewer agent
   - Commits and pushes
3. The pipeline replies to your comment with:
   - The fix commit SHA
   - A summary of what was changed
   - The files that were modified
4. Re-test the fixed items and file new defects if needed

If your defect report is missing required fields, the pipeline replies with a warning and skips it. Fix the comment and the next `/fix-defects` run will pick it up.

## For Developers: Running the Fix Pipeline

### Prerequisites

- The project must be bootstrapped with the pipeline (`init.sh` has been run)
- GitHub CLI (`gh`) installed and authenticated
- You're on the PR branch (or can provide the PR number)

### Step 1: Check the PR for defect reports

You can preview what's been filed before running the pipeline:

```bash
# List all comments on a PR
gh pr view 42 --comments

# Or check via the GitHub web UI
```

### Step 2: Run the fix pipeline

Start Claude Code in your project directory and run:

```
/fix-defects
```

Or with a specific PR:

```
/fix-defects 42
```

Or with a PR URL:

```
/fix-defects https://github.com/org/repo/pull/42
```

The pipeline will:

1. **Identify the PR** — from your current branch, the argument, or by asking you
2. **Fetch all comments** — reads both PR review comments and conversation comments
3. **Parse defect reports** — identifies comments with the `### DEFECT REPORT` header
4. **Skip already-processed defects** — checks for existing "Fixed in commit" replies
5. **Show you a summary table** — severity, component, and a short description for each
6. **Process in severity order** — CRITICAL first, then HIGH, MEDIUM, LOW

### Step 3: Monitor progress

For each defect, the pipeline runs:

```
5.1 ASSESS    →  Correlate to files, check fragile areas, classify simple vs complex
5.2 FIX       →  Launch implementer agent (Sonnet for CRITICAL/HIGH/MEDIUM, Haiku for simple LOW)
5.3 REVIEW    →  Launch code-reviewer agent (Sonnet)
5.4 COMMIT    →  git commit + push
5.5 REPLY     →  Comment on PR with fix summary + add reaction to original comment
```

CRITICAL defects always get a blast-radius analysis via the architect agent before fixing. Other severities get blast-radius analysis only if they touch fragile areas or cross multiple components.

If a fix fails code review, the pipeline retries with the reviewer's feedback (up to 2 cycles). After that, it escalates to you and moves on to the next defect.

### Step 4: Review the summary

After processing all defects, the pipeline shows a summary:

```
Defect Fix Summary for PR #42

| # | Severity | Component    | Status             | Commit  |
|---|----------|--------------|--------------------|---------|
| 1 | CRITICAL | login flow   | Fixed              | abc1234 |
| 2 | HIGH     | dashboard    | Fixed              | def5678 |
| 3 | MEDIUM   | settings     | Escalated to user  | —       |

2 of 3 defects fixed. Remaining issues require manual intervention.
```

### Step 5: Ask testers to re-test

The pipeline tells testers to re-test via its PR comment replies. If new defects are found, testers file new comments and you run `/fix-defects` again — it skips already-fixed defects.

### Running within an orchestrate session

The `/fix-defects` skill also works within an active `/orchestrate` session. If you're at the manual test step (Step 3.5) and testers have been filing defects on the PR, you can run `/fix-defects` instead of manually describing each bug.

The TOKEN_LEDGER entries use the `defect:` prefix to distinguish from the orchestrate run's entries.

### Cost expectations

| Defect complexity | Model | Approximate cost |
|-------------------|-------|-----------------|
| Simple LOW defect | Haiku fix + Sonnet review | ~$0.01-0.03 |
| Typical HIGH defect | Sonnet fix + Sonnet review | ~$0.05-0.15 |
| Complex CRITICAL defect | Sonnet assess + Sonnet fix + Sonnet review | ~$0.10-0.30 |

A batch of 5 defects (1 CRITICAL, 2 HIGH, 2 MEDIUM) typically costs $0.20-0.60.

### Troubleshooting

| Problem | Solution |
|---------|----------|
| "No defect reports found" | Ensure comments use `### DEFECT REPORT` as the header (case-insensitive) |
| Defect skipped with field error | Check the pipeline's error reply — it says which fields are missing |
| `gh` not installed | `brew install gh` (macOS) or see https://cli.github.com/ |
| Not authenticated | Run `gh auth login` |
| Fix keeps failing review | After 2 cycles the pipeline escalates to you — fix manually or provide more context |
| Wrong PR detected | Pass the PR number explicitly: `/fix-defects 42` |

## Workflow Example

Here's a complete walkthrough of a typical testing cycle:

**1. Developer creates a PR via the pipeline:**
```
> /orchestrate
> Add user authentication with JWT tokens
```
Pipeline runs, opens draft PR #42.

**2. Testers test the PR branch and file defects:**

Tester A comments on PR #42:
```markdown
### DEFECT REPORT

**Severity:** CRITICAL
**Component:** login flow
**Found in:** src/auth/login.ts

#### Steps to Reproduce
1. Navigate to /login
2. Enter valid credentials
3. Click "Sign In"

#### Expected Behavior
Redirect to dashboard.

#### Actual Behavior
White screen crash. Console: TypeError at login.ts:42.

#### Screenshots
![crash](https://user-images.github.../crash.png)

#### Environment
- **Browser/Device:** Chrome 120
- **Build:** abc1234
```

Tester B files another comment with a MEDIUM severity defect.

**3. Developer processes all defects:**
```
> /fix-defects
```

Pipeline output:
```
Found 2 defect report(s) on PR #42:

| # | Severity | Component   | Summary                    |
|---|----------|-------------|----------------------------|
| 1 | CRITICAL | login flow  | White screen crash on login |
| 2 | MEDIUM   | settings    | Missing save confirmation   |

Proceeding to fix in severity order.
```

**4. Pipeline fixes each defect, replies to PR comments:**

Reply on Tester A's comment:
> Fixed in commit `def5678`. Please re-test.
>
> **Fix summary:** Added null check for auth token response before accessing `.token` property.
> **Files modified:** src/auth/login.ts

**5. Testers re-test, file new defects or confirm fixes.**

**6. Developer runs `/fix-defects` again if new defects were filed.** Already-fixed defects are skipped.

**7. When all tests pass, developer finalizes the PR** (via `/orchestrate` Step 4 or manually).
