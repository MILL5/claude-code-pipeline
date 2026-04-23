---
name: bootstrap-backlog
description: Provisions GitHub labels, Issue Forms, and a sentinel config so /orchestrate can file deferred work as backlog issues. Idempotent — safe to re-run on every pipeline upgrade.
---

# Bootstrap Backlog Skill

Provisions the opt-in artifacts that enable `/orchestrate` to file deferred work as
GitHub issues with the canonical namespaced label taxonomy. Run once per consumer
repo; re-running is a no-op if nothing changed upstream.

## Prerequisites

- `gh` CLI installed and authenticated (`gh auth status` exit 0).
- Current directory is inside a git repo with a GitHub remote.
- User has write access to labels on the remote's owner.

Fail loudly with a clear message if any prerequisite is missing. Do not attempt to
install `gh` or run `gh auth login` for the user.

## Step 1: Preflight

```bash
gh auth status
```

If exit code is nonzero, print:
```
bootstrap-backlog: gh CLI is not authenticated. Run `gh auth login` and retry.
```
…and stop.

Verify the current directory is a git repo with a remote:

```bash
git rev-parse --is-inside-work-tree
git remote get-url origin
```

If either fails, print a specific error and stop.

Locate the pipeline repo root (for reading `templates/backlog/`). In consumer
projects, `.claude/pipeline/` points at the pipeline submodule or clone. In the
pipeline repo itself, the repo root IS the pipeline root.

## Step 2: Provision Labels

Read `templates/backlog/labels.yml` from the pipeline root. For each label,
invoke:

```bash
gh label create "<name>" --color "<color>" --description "<description>" --force
```

`--force` updates existing labels (idempotent). The 12 labels are:

| Name | Color | Purpose |
|---|---|---|
| `type: bug` | d73a4a | Something isn't working |
| `type: feature` | a2eeef | New capability |
| `type: chore` | fef2c0 | Tech debt, refactor, cleanup |
| `type: docs` | 0075ca | Documentation only |
| `priority: p0` | b60205 | Drop everything |
| `priority: p1` | d93f0b | Next sprint |
| `priority: p2` | fbca04 | Backlog |
| `status: needs-triage` | ededed | Default on new issues |
| `status: blocked` | e4e669 | Blocked by external dependency |
| `status: ready` | 0e8a16 | Triaged, ready to pick up |
| `source: ai-deferred` | 5319e7 | Filed by /orchestrate run |
| `good first issue` | 7057ff | Good for newcomers |
| `help wanted` | 008672 | Extra attention is needed |

**DO NOT delete existing labels** — bootstrap is additive. If a consumer repo
has a label with the same name and different color/description, `--force` will
update it (document this behavior in the summary).

If `gh label create --force` fails for any label, surface the error and stop —
partial provisioning is worse than none.

## Step 3: Install Issue Forms

Create `.github/ISSUE_TEMPLATE/` if missing. Copy all four YAML files from
`templates/backlog/ISSUE_TEMPLATE/` in the pipeline root:

```bash
mkdir -p .github/ISSUE_TEMPLATE
cp <pipeline_root>/templates/backlog/ISSUE_TEMPLATE/bug_report.yml      .github/ISSUE_TEMPLATE/
cp <pipeline_root>/templates/backlog/ISSUE_TEMPLATE/feature_request.yml .github/ISSUE_TEMPLATE/
cp <pipeline_root>/templates/backlog/ISSUE_TEMPLATE/chore.yml           .github/ISSUE_TEMPLATE/
cp <pipeline_root>/templates/backlog/ISSUE_TEMPLATE/config.yml          .github/ISSUE_TEMPLATE/
```

Copies (not symlinks) because `.github/` must be directly committable in the
consumer repo. Overwriting existing Issue Forms is intentional — the pipeline
is the source of truth for these templates. Pre-existing unrelated templates in
`.github/ISSUE_TEMPLATE/` are left untouched.

## Step 4: Write Sentinel Config

```bash
test -f .github/pipeline-backlog.yml || \
  cp <pipeline_root>/templates/backlog/pipeline-backlog.yml.template \
     .github/pipeline-backlog.yml
```

**Do NOT overwrite an existing sentinel** — the user may have customized
`fold_cap` or set `project_number`. The template's defaults (version 1,
enabled true, fold_cap 3, project_number null) are sensible first-run values.

## Step 5: Summary

Print a structured provisioning summary:

```
bootstrap-backlog: complete
  Labels provisioned:   12 (via gh label create --force)
  Issue Forms:          .github/ISSUE_TEMPLATE/{bug_report,feature_request,chore,config}.yml
  Sentinel config:      .github/pipeline-backlog.yml (<created | existing, unchanged>)

Next steps:
  1. Review .github/ISSUE_TEMPLATE/ and .github/pipeline-backlog.yml
  2. Commit and push — backlog integration activates on the next /orchestrate run
  3. To disable later: delete .github/pipeline-backlog.yml (labels and templates remain)
```

## Error Handling

- `gh` not installed → "bootstrap-backlog: install GitHub CLI — brew install gh"
- `gh auth status` nonzero → "bootstrap-backlog: run `gh auth login` and retry"
- Not in a git repo → "bootstrap-backlog: this must run inside a git repository"
- No GitHub remote → "bootstrap-backlog: this repo has no GitHub remote configured"
- `gh label create` fails → surface `gh`'s stderr verbatim and stop (do not continue with partial labels)
- `cp` fails → surface the OS error and stop

## Re-running

Re-running is safe and produces zero diff after the first successful run:
- `gh label create --force` is idempotent (updates or creates)
- Template files are overwritten with identical content
- Sentinel is NOT overwritten if present

This is the expected behavior on every pipeline upgrade — re-run after
`/update-pipeline` to pick up any label or template changes.

## Token Report

After completing, output:

```
---TOKEN_REPORT---
files_read: <N>
tool_calls: <N>
self_assessed_input: <tokens>
self_assessed_output: <tokens>
```
