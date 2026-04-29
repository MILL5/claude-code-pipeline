#!/usr/bin/env python3
"""Layer 1: Static validation of pipeline structural integrity.

Validates that all pipeline files exist, cross-references resolve, output
protocols are documented, adapter files are complete, and overlay injection
markers are present. Runs with no dependencies beyond Python 3.9+ stdlib.

Usage:
    python3 tests/validate_structure.py [--verbose]

Exit codes:
    0 — all checks passed
    1 — one or more checks failed
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parent.parent


def discover_adapters() -> list[str]:
    """Auto-discover adapters from directory structure."""
    adapters_dir = PIPELINE_ROOT / "adapters"
    return sorted(
        d.name for d in adapters_dir.iterdir()
        if d.is_dir() and (d / "manifest.json").exists()
    )


def discover_overlays() -> list[str]:
    """Auto-discover overlays from directory structure."""
    overlays_dir = PIPELINE_ROOT / "overlays"
    if not overlays_dir.exists():
        return []
    return sorted(
        d.name for d in overlays_dir.iterdir()
        if d.is_dir() and (d / "manifest.json").exists()
    )


ADAPTERS = discover_adapters()

REQUIRED_ADAPTER_FILES = [
    "manifest.json",
    "adapter.md",
    "architect-overlay.md",
    "implementer-overlay.md",
    "implementer-overlay-essential.md",
    "reviewer-overlay.md",
    "test-overlay.md",
    "hooks.json",
    "scripts/build.py",
    "scripts/test.py",
]

REQUIRED_AGENTS = [
    "architect-agent.md",
    "implementer-agent.md",
    "code-reviewer-agent.md",
    "test-architect-agent.md",
    "implementer-contract.md",
]

REQUIRED_SKILLS = [
    "orchestrate/SKILL.md",
    "architect-analyzer/SKILL.md",
    "architect-planner/SKILL.md",
    "build-runner/SKILL.md",
    "test-runner/SKILL.md",
    "open-pr/SKILL.md",
    "summarize-implementation/SKILL.md",
    "token-analysis/SKILL.md",
    "fix-defects/SKILL.md",
    "validate-bicep/SKILL.md",
    "deploy-bicep/SKILL.md",
    "azure-cost-estimate/SKILL.md",
    "security-scan/SKILL.md",
    "infra-test-runner/SKILL.md",
    "azure-drift-check/SKILL.md",
    "azure-login/SKILL.md",
    "update-pipeline/SKILL.md",
    "bootstrap-backlog/SKILL.md",
    "chrome-ui-test/SKILL.md",
]

REQUIRED_BACKLOG_TEMPLATES = [
    "templates/backlog/ISSUE_TEMPLATE/bug_report.yml",
    "templates/backlog/ISSUE_TEMPLATE/feature_request.yml",
    "templates/backlog/ISSUE_TEMPLATE/chore.yml",
    "templates/backlog/ISSUE_TEMPLATE/config.yml",
    "templates/backlog/labels.yml",
    "templates/backlog/pipeline-backlog.yml.template",
]

REQUIRED_SCRIPTS = [
    "scripts/backlog_file.py",
]

ESSENTIAL_OVERLAY_MAX_CHARS = 1000

OVERLAYS = discover_overlays()

# Overlays intentionally omit test-overlay.md: testing patterns for Azure SDK
# are language-specific and covered by each adapter's own test overlay.
REQUIRED_OVERLAY_FILES = [
    "manifest.json",
    "architect-overlay.md",
    "implementer-overlay.md",
    "implementer-overlay-essential.md",
    "reviewer-overlay.md",
]

# Markers that must exist in agent files for overlay injection
AGENT_MARKERS = {
    "implementer-agent.md": ["<!-- ADAPTER:TECH_STACK_CONTEXT -->", "<!-- ADAPTER:CODE_QUALITY_RULES -->"],
    "architect-agent.md": ["<!-- ADAPTER:TECH_STACK_CONTEXT -->"],
    "code-reviewer-agent.md": ["<!-- ADAPTER:TECH_STACK_CONTEXT -->"],
    "test-architect-agent.md": ["<!-- ADAPTER:TECH_STACK_CONTEXT -->"],
}

# Output protocol keywords each agent must document
AGENT_PROTOCOLS = {
    "implementer-agent.md": ["SUCCESS", "FAILURE", "TOKEN_REPORT"],
    "code-reviewer-agent.md": ["PASS", "FAIL", "TOKEN_REPORT"],
    "architect-agent.md": ["TOKEN_REPORT"],
}

# Sections required in the ORCHESTRATOR.md template
ORCHESTRATOR_TEMPLATE_SECTIONS = [
    "## Project Overview",
    "## Targets / Entry Points",
    "## Directory Structure",
    "## Architecture",
    "## Key Services / Modules",
    "## Data Flow",
    "## Conventions",
    "## Testing",
    "## Known Fragile Areas",
    "## Anti-Patterns",
    "## Current State",
]

# Scoped extract profiles defined in orchestrate skill — must reference these headers
EXTRACT_PROFILES = {
    "1a": [
        "Project Overview",
        "Targets / Entry Points",
        "Directory Structure",
        "Architecture",
        "Key Services / Modules",
        "Known Fragile Areas",
        "Current State",
    ],
    "1b": [
        "Data Flow",
        "Conventions",
        "Testing",
        "Anti-Patterns",
    ],
    "3.5": [
        "Directory Structure",
        "Key Services / Modules",
        "Known Fragile Areas",
    ],
}


class ValidationResult:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []

    def ok(self, msg: str) -> None:
        self.passed.append(msg)

    def fail(self, msg: str) -> None:
        self.failed.append(msg)

    @property
    def success(self) -> bool:
        return len(self.failed) == 0


def check_required_files(result: ValidationResult) -> None:
    """Check all required agent, skill, and template files exist."""
    for agent in REQUIRED_AGENTS:
        path = PIPELINE_ROOT / "agents" / agent
        if path.exists():
            result.ok(f"Agent exists: {agent}")
        else:
            result.fail(f"Missing agent: {agent}")

    for skill in REQUIRED_SKILLS:
        path = PIPELINE_ROOT / "skills" / skill
        if path.exists():
            result.ok(f"Skill exists: {skill}")
        else:
            result.fail(f"Missing skill: {skill}")

    for template in ["CLAUDE.md.template", "ORCHESTRATOR.md.template",
                      "pipeline.config.template", "defect-report.md",
                      "local/project-overlay.md.template",
                      "local/coding-standards.md.template",
                      "local/architecture-rules.md.template",
                      "local/review-criteria.md.template"]:
        path = PIPELINE_ROOT / "templates" / template
        if path.exists():
            result.ok(f"Template exists: {template}")
        else:
            result.fail(f"Missing template: {template}")

    for backlog_template in REQUIRED_BACKLOG_TEMPLATES:
        path = PIPELINE_ROOT / backlog_template
        if path.exists():
            result.ok(f"Backlog template exists: {backlog_template}")
        else:
            result.fail(f"Missing backlog template: {backlog_template}")

    for script in REQUIRED_SCRIPTS:
        path = PIPELINE_ROOT / script
        if path.exists():
            result.ok(f"Script exists: {script}")
        else:
            result.fail(f"Missing script: {script}")


def check_adapter_completeness(result: ValidationResult) -> None:
    """Check each adapter has all required files."""
    for adapter in ADAPTERS:
        adapter_dir = PIPELINE_ROOT / "adapters" / adapter
        if not adapter_dir.is_dir():
            result.fail(f"Missing adapter directory: adapters/{adapter}/")
            continue

        for req_file in REQUIRED_ADAPTER_FILES:
            path = adapter_dir / req_file
            if path.exists():
                result.ok(f"Adapter {adapter}: {req_file} exists")
            else:
                result.fail(f"Adapter {adapter}: missing {req_file}")


def check_essential_overlay_size(result: ValidationResult) -> None:
    """Essential overlays must be compact (under threshold)."""
    for adapter in ADAPTERS:
        path = PIPELINE_ROOT / "adapters" / adapter / "implementer-overlay-essential.md"
        if not path.exists():
            continue  # already caught by completeness check

        size = len(path.read_text())
        if size <= ESSENTIAL_OVERLAY_MAX_CHARS:
            result.ok(f"Adapter {adapter}: essential overlay is {size} chars (under {ESSENTIAL_OVERLAY_MAX_CHARS})")
        else:
            result.fail(
                f"Adapter {adapter}: essential overlay is {size} chars "
                f"(exceeds {ESSENTIAL_OVERLAY_MAX_CHARS} limit)"
            )


def check_essential_overlay_no_pipeline_protocol_rules(result: ValidationResult) -> None:
    """Essential overlays must not duplicate pipeline-protocol rules from agent definitions (C1).

    The 'Never run git commit/git push' rule lives in implementer-agent.md (always loaded
    as system prompt). Repeating it in adapter essentials is pure duplication — Haiku tasks
    that read the agent definition + essential see the same rule twice.
    """
    overlay_paths = []
    for adapter in ADAPTERS:
        overlay_paths.append(PIPELINE_ROOT / "adapters" / adapter / "implementer-overlay-essential.md")
    for overlay in OVERLAYS:
        overlay_paths.append(PIPELINE_ROOT / "overlays" / overlay / "implementer-overlay-essential.md")

    for path in overlay_paths:
        if not path.exists():
            continue
        rel = path.relative_to(PIPELINE_ROOT)
        content = path.read_text()
        if "git commit" in content and "orchestrator commits" in content:
            result.fail(
                f"{rel}: still contains 'git commit' pipeline-protocol rule "
                f"(C1 regression — that rule belongs in implementer-agent.md)"
            )
        elif "Critical rules for Haiku execution. Violations will fail code review" in content:
            result.fail(
                f"{rel}: still contains boilerplate disclaimer "
                f"(C1 — remove this filler line, the rules speak for themselves)"
            )
        else:
            result.ok(f"{rel}: free of pipeline-protocol duplication")


def check_agent_markers(result: ValidationResult) -> None:
    """Agents must have the correct injection markers."""
    for agent_file, markers in AGENT_MARKERS.items():
        path = PIPELINE_ROOT / "agents" / agent_file
        if not path.exists():
            continue

        content = path.read_text()
        for marker in markers:
            if marker in content:
                result.ok(f"Agent {agent_file}: has marker {marker}")
            else:
                result.fail(f"Agent {agent_file}: missing marker {marker}")


def check_agent_protocols(result: ValidationResult) -> None:
    """Agents must document their output protocol keywords."""
    for agent_file, keywords in AGENT_PROTOCOLS.items():
        path = PIPELINE_ROOT / "agents" / agent_file
        if not path.exists():
            continue

        content = path.read_text()
        for kw in keywords:
            if kw in content:
                result.ok(f"Agent {agent_file}: documents '{kw}' protocol")
            else:
                result.fail(f"Agent {agent_file}: missing '{kw}' in output protocol")


def check_token_report_consistency(result: ValidationResult) -> None:
    """All agents that should emit TOKEN_REPORT must document the compact format.

    The compact format drops SELF_ASSESSED_* fields (unreliable self-reports) and
    consolidates FILES_READ/TOOL_CALLS to single-line entries. Agents must NOT
    re-introduce the verbose multi-line format.
    """
    token_report_agents = ["implementer-agent.md", "code-reviewer-agent.md", "architect-agent.md"]
    for agent_file in token_report_agents:
        path = PIPELINE_ROOT / "agents" / agent_file
        if not path.exists():
            continue

        content = path.read_text()
        has_start = "---TOKEN_REPORT---" in content
        has_end = "---END_TOKEN_REPORT---" in content
        has_files_read = "FILES_READ:" in content
        has_tool_calls = "TOOL_CALLS:" in content
        # Compact format: SELF_ASSESSED_* must be absent
        has_self_input = "SELF_ASSESSED_INPUT" in content
        has_self_output = "SELF_ASSESSED_OUTPUT" in content

        missing = []
        if not has_start:
            missing.append("---TOKEN_REPORT---")
        if not has_end:
            missing.append("---END_TOKEN_REPORT---")
        if not has_files_read:
            missing.append("FILES_READ:")
        if not has_tool_calls:
            missing.append("TOOL_CALLS:")

        bloat = []
        if has_self_input:
            bloat.append("SELF_ASSESSED_INPUT (compact format dropped this)")
        if has_self_output:
            bloat.append("SELF_ASSESSED_OUTPUT (compact format dropped this)")

        if not missing and not bloat:
            result.ok(f"Agent {agent_file}: TOKEN_REPORT compact format complete")
        else:
            details = []
            if missing:
                details.append(f"missing: {', '.join(missing)}")
            if bloat:
                details.append(f"bloat: {', '.join(bloat)}")
            result.fail(f"Agent {agent_file}: TOKEN_REPORT — {' | '.join(details)}")


def check_implementer_contract_references(result: ValidationResult) -> None:
    """implementer-contract.md must be referenced by both planner and implementer."""
    contract_path = PIPELINE_ROOT / "agents" / "implementer-contract.md"
    if not contract_path.exists():
        result.fail("implementer-contract.md does not exist")
        return

    # Check planner references it
    planner_path = PIPELINE_ROOT / "skills" / "architect-planner" / "SKILL.md"
    if planner_path.exists():
        content = planner_path.read_text()
        if "implementer-contract.md" in content:
            result.ok("Planner references implementer-contract.md")
        else:
            result.fail("Planner (architect-planner/SKILL.md) does not reference implementer-contract.md")

    # Check implementer references it
    impl_path = PIPELINE_ROOT / "agents" / "implementer-agent.md"
    if impl_path.exists():
        content = impl_path.read_text()
        if "implementer-contract.md" in content:
            result.ok("Implementer agent references implementer-contract.md")
        else:
            result.fail("implementer-agent.md does not reference implementer-contract.md")


def check_orchestrator_template_sections(result: ValidationResult) -> None:
    """ORCHESTRATOR.md template must have all sections the extract profiles expect."""
    template_path = PIPELINE_ROOT / "templates" / "ORCHESTRATOR.md.template"
    if not template_path.exists():
        result.fail("ORCHESTRATOR.md.template does not exist")
        return

    content = template_path.read_text()

    for section in ORCHESTRATOR_TEMPLATE_SECTIONS:
        if section in content:
            result.ok(f"Template has section: {section}")
        else:
            result.fail(f"Template missing section: {section}")


def check_extract_profile_headers(result: ValidationResult) -> None:
    """Scoped extract profiles in orchestrate must reference headers that exist in template."""
    orchestrate_path = PIPELINE_ROOT / "skills" / "orchestrate" / "SKILL.md"
    template_path = PIPELINE_ROOT / "templates" / "ORCHESTRATOR.md.template"
    if not orchestrate_path.exists() or not template_path.exists():
        return

    template_content = template_path.read_text()
    orchestrate_content = orchestrate_path.read_text()

    # Verify the orchestrate skill documents each profile
    for profile_name, headers in EXTRACT_PROFILES.items():
        profile_label = f"{profile_name} Extract"
        if profile_label in orchestrate_content:
            result.ok(f"Orchestrate documents {profile_label}")
        else:
            result.fail(f"Orchestrate missing {profile_label} definition")

        # Verify each header referenced by the profile exists in the template
        for header in headers:
            if f"## {header}" in template_content:
                result.ok(f"Extract {profile_name}: header '## {header}' exists in template")
            else:
                result.fail(f"Extract {profile_name}: header '## {header}' not found in template")


def check_token_analysis_output_baselines(result: ValidationResult) -> None:
    """Token-analysis skill must document per-agent-type output baselines (E1)."""
    path = PIPELINE_ROOT / "skills" / "token-analysis" / "SKILL.md"
    if not path.exists():
        return

    content = path.read_text()
    required_markers = [
        "Output Bloat Detection",
        "Soft cap exceeded",
        "Hard cap exceeded",
        "PLAN_WRITTEN",
        "implementer SUCCESS",
        "reviewer PASS",
    ]
    missing = [m for m in required_markers if m not in content]
    if missing:
        result.fail(f"token-analysis missing E1 baselines: {', '.join(missing)}")
    else:
        result.ok("token-analysis documents per-agent output baselines (E1)")


def check_token_analysis_fixed_overhead(result: ValidationResult) -> None:
    """Token-analysis skill must document fixed orchestrator overhead estimation (E2)."""
    path = PIPELINE_ROOT / "skills" / "token-analysis" / "SKILL.md"
    if not path.exists():
        return

    content = path.read_text()
    required_markers = [
        "Orchestrator Fixed Overhead",
        "fixed_overhead_chars",
        "Fixed orchestrator overhead",
        "25,000 tokens",
    ]
    missing = [m for m in required_markers if m not in content]
    if missing:
        result.fail(f"token-analysis missing E2 fixed-overhead docs: {', '.join(missing)}")
    else:
        result.ok("token-analysis documents fixed orchestrator overhead (E2)")


def check_clarification_round_caps(result: ValidationResult) -> None:
    """Architect skills must cap clarification round output to bound input bloat (B5)."""
    for skill_path in [
        PIPELINE_ROOT / "skills" / "architect-analyzer" / "SKILL.md",
        PIPELINE_ROOT / "skills" / "architect-planner" / "SKILL.md",
    ]:
        if not skill_path.exists():
            continue
        content = skill_path.read_text()
        rel_path = skill_path.relative_to(PIPELINE_ROOT)
        if "800 tokens" in content or "800 token" in content:
            result.ok(f"{rel_path}: documents 800-token clarification cap")
        else:
            result.fail(f"{rel_path}: missing clarification round output cap (B5)")


def check_reviewer_no_standalone_mode(result: ValidationResult) -> None:
    """Code-reviewer must not document a separate Standalone Mode (B3).

    The reviewer historically had a verbose 7-section format for non-orchestrator
    invocations. That format invited output bloat when prompts didn't crisply
    signal Pipeline Mode. The PASS/FAIL protocol is now the only supported format.
    """
    path = PIPELINE_ROOT / "agents" / "code-reviewer-agent.md"
    if not path.exists():
        return

    content = path.read_text()
    forbidden_markers = [
        "## CRITICAL ISSUES",
        "## SOLID / MAINTAINABILITY VIOLATIONS",
        "## PERFORMANCE KILLERS",
        "## RECOMMENDED REFACTORINGS",
        "Standalone Mode (launched directly by user)",
    ]
    found = [m for m in forbidden_markers if m in content]
    if found:
        result.fail(
            f"Code-reviewer still documents Standalone Mode (B3 regression): {', '.join(found)}"
        )
    else:
        result.ok("Code-reviewer does not document Standalone Mode")

    # Must still document the protocol guard
    if "Protocol Guard" in content or "If your first line is not" in content:
        result.ok("Code-reviewer documents protocol guard")
    else:
        result.fail("Code-reviewer missing protocol guard (PASS/FAIL header enforcement)")


def check_reviewer_optional_cap(result: ValidationResult) -> None:
    """Code-reviewer must document a cap on OPTIONAL IMPROVEMENTS to bound output."""
    path = PIPELINE_ROOT / "agents" / "code-reviewer-agent.md"
    if not path.exists():
        return

    content = path.read_text()
    if "maximum 5 entries" in content.lower() or "max 5 entries" in content.lower() or "Cap: maximum 5" in content:
        result.ok("Code-reviewer documents OPTIONAL IMPROVEMENTS cap")
    else:
        result.fail("Code-reviewer missing OPTIONAL IMPROVEMENTS cap (B2)")

    if "(N more not shown)" in content or "more not shown" in content:
        result.ok("Code-reviewer documents overflow indicator")
    else:
        result.fail("Code-reviewer missing overflow indicator for capped entries (B2)")


def check_planner_plan_stub(result: ValidationResult) -> None:
    """Planner must emit PLAN_WRITTEN stub instead of the full plan."""
    planner_path = PIPELINE_ROOT / "skills" / "architect-planner" / "SKILL.md"
    if not planner_path.exists():
        result.fail("architect-planner skill exists")
        return

    content = planner_path.read_text()
    if "PLAN_WRITTEN:" in content:
        result.ok("Planner documents PLAN_WRITTEN stub format")
    else:
        result.fail("Planner missing PLAN_WRITTEN stub documentation")

    # Regression guard: planner must NOT instruct the agent to re-emit the full plan.
    if "Output the plan as text to the orchestrator" in content:
        result.fail(
            "Planner still instructs agent to re-emit the full plan to orchestrator "
            "(B1 regression — should write to disk only and emit PLAN_WRITTEN stub)"
        )
    else:
        result.ok("Planner does not instruct double-pay full-plan emission")


def check_planner_exact_string_brief_hints(result: ValidationResult) -> None:
    """Planner must document line-range and TRUST THE BRIEF hints for exact-string edit tasks."""
    path = PIPELINE_ROOT / "skills" / "architect-planner" / "SKILL.md"
    if not path.exists():
        return

    content = path.read_text()

    if "exact-string edit" in content.lower() or "exact string edit" in content.lower():
        result.ok("Planner documents exact-string edit task brief requirements")
    else:
        result.fail("Planner missing exact-string edit task brief requirements")

    if "line range" in content.lower() or "line N" in content or "lines N" in content:
        result.ok("Planner documents line range hint to scope implementer file reads")
    else:
        result.fail("Planner missing line range hint for exact-string edit briefs")

    if "do not re-read" in content.lower() or "trust the brief" in content.lower():
        result.ok("Planner documents TRUST THE BRIEF / do-not-re-read note for exact-string briefs")
    else:
        result.fail("Planner missing TRUST THE BRIEF note for exact-string edit briefs")


def check_orchestrate_reads_plan_from_disk(result: ValidationResult) -> None:
    """Orchestrate must read 1b-plan.md from disk, not from agent output."""
    orchestrate_path = PIPELINE_ROOT / "skills" / "orchestrate" / "SKILL.md"
    if not orchestrate_path.exists():
        return

    content = orchestrate_path.read_text()

    if "PLAN_WRITTEN" in content:
        result.ok("Orchestrate references PLAN_WRITTEN stub")
    else:
        result.fail("Orchestrate missing PLAN_WRITTEN stub reference")

    if "read .claude/tmp/1b-plan.md" in content.lower() or "read `.claude/tmp/1b-plan.md`" in content.lower():
        result.ok("Orchestrate documents reading 1b-plan.md from disk")
    else:
        result.fail("Orchestrate missing 'read 1b-plan.md from disk' instruction")


def check_orchestrate_overlay_selection(result: ValidationResult) -> None:
    """Orchestrate must document Haiku vs full overlay selection logic."""
    orchestrate_path = PIPELINE_ROOT / "skills" / "orchestrate" / "SKILL.md"
    if not orchestrate_path.exists():
        return

    content = orchestrate_path.read_text()

    if "implementer-overlay-essential.md" in content:
        result.ok("Orchestrate references essential overlay for Haiku tasks")
    else:
        result.fail("Orchestrate does not reference implementer-overlay-essential.md")

    if "implementer-overlay.md" in content:
        result.ok("Orchestrate references full overlay for Sonnet/Opus tasks")
    else:
        result.fail("Orchestrate does not reference full implementer-overlay.md")


def check_orchestrate_token_ledger(result: ValidationResult) -> None:
    """Orchestrate must define TOKEN_LEDGER schema and recording instructions."""
    orchestrate_path = PIPELINE_ROOT / "skills" / "orchestrate" / "SKILL.md"
    if not orchestrate_path.exists():
        return

    content = orchestrate_path.read_text()

    required_fields = [
        "step", "agent", "model", "input_chars", "output_chars",
        "is_retry", "is_escalation", "files_read", "tool_calls",
    ]

    for field in required_fields:
        if f"`{field}`" in content:
            result.ok(f"TOKEN_LEDGER schema has field: {field}")
        else:
            result.fail(f"TOKEN_LEDGER schema missing field: {field}")


def check_orchestrate_reviewer_reuse(result: ValidationResult) -> None:
    """Orchestrate must document reviewer reuse via SendMessage."""
    orchestrate_path = PIPELINE_ROOT / "skills" / "orchestrate" / "SKILL.md"
    if not orchestrate_path.exists():
        return

    content = orchestrate_path.read_text()

    if "SendMessage" in content and "NEW REVIEW" in content:
        result.ok("Orchestrate documents reviewer reuse via SendMessage")
    else:
        result.fail("Orchestrate missing reviewer reuse (SendMessage + NEW REVIEW)")

    if "Cap at 8 reviews" in content or ("cap" in content.lower() and "8 reviews" in content.lower()):
        result.ok("Orchestrate documents 8-review cap per reviewer agent")
    else:
        result.fail("Orchestrate missing 8-review cap documentation")


def check_init_script(result: ValidationResult) -> None:
    """init.sh must exist and reference all adapters."""
    init_path = PIPELINE_ROOT / "init.sh"
    if not init_path.exists():
        result.fail("init.sh does not exist")
        return

    content = init_path.read_text()
    result.ok("init.sh exists")

    # Check it references key operations
    checks = {
        "pipeline.config": "writes pipeline.config",
        "symlink": "creates symlinks",
        "settings.json": "merges settings",
    }
    for keyword, desc in checks.items():
        if keyword.lower() in content.lower():
            result.ok(f"init.sh: {desc}")
        else:
            result.fail(f"init.sh: does not appear to {desc}")


def check_version_file(result: ValidationResult) -> None:
    """Pipeline must have a VERSION file with a semver string."""
    version_path = PIPELINE_ROOT / "VERSION"
    if not version_path.exists():
        result.fail("VERSION file exists")
        return

    content = version_path.read_text().strip()
    if re.match(r"^\d+\.\d+\.\d+$", content):
        result.ok(f"VERSION file contains valid semver: {content}")
    else:
        result.fail(f"VERSION file has invalid format: '{content}' (expected X.Y.Z)")


def check_orchestrate_local_overlay_loading(result: ValidationResult) -> None:
    """Orchestrate must document local overlay loading from .claude/local/."""
    orchestrate_path = PIPELINE_ROOT / "skills" / "orchestrate" / "SKILL.md"
    if not orchestrate_path.exists():
        return

    content = orchestrate_path.read_text()

    if ".claude/local/" in content:
        result.ok("Orchestrate documents local overlay loading")
    else:
        result.fail("Orchestrate missing local overlay loading documentation")

    if "LOCAL_OVERLAYS" in content:
        result.ok("Orchestrate defines LOCAL_OVERLAYS registry")
    else:
        result.fail("Orchestrate missing LOCAL_OVERLAYS registry definition")

    if "Project:" in content:
        result.ok("Orchestrate documents project overlay composition headers")
    else:
        result.fail("Orchestrate missing project overlay composition headers")


def check_orchestrate_workflow_optimizations(result: ValidationResult) -> None:
    """Orchestrate must document key workflow optimizations."""
    orchestrate_path = PIPELINE_ROOT / "skills" / "orchestrate" / "SKILL.md"
    if not orchestrate_path.exists():
        return

    content = orchestrate_path.read_text()

    # Streaming reviews: reviews start as implementers complete, not after full wave
    if "Streaming review" in content or "streaming review" in content.lower():
        result.ok("Orchestrate documents streaming wave reviews")
    else:
        result.fail("Orchestrate missing streaming wave reviews documentation")

    # Bug-fix reviewer reuse via SendMessage (same pattern as wave reviews)
    if "bug-fix reviewer" in content.lower() or "bug-fix review" in content.lower():
        result.ok("Orchestrate documents bug-fix reviewer reuse")
    else:
        result.fail("Orchestrate missing bug-fix reviewer reuse documentation")

    # Parallel bug fixes for independent bugs
    if "Parallel bug fix" in content or "parallel bug fix" in content.lower():
        result.ok("Orchestrate documents parallel bug fixes")
    else:
        result.fail("Orchestrate missing parallel bug fixes documentation")

    # HTML comment stripping for local overlays
    if "strip HTML comment" in content or "strip html comment" in content.lower():
        result.ok("Orchestrate documents HTML comment stripping for local overlays")
    else:
        result.fail("Orchestrate missing HTML comment stripping for local overlays")

    # Token analysis runs in background during finalization
    if "background" in content.lower() and "token analysis" in content.lower():
        result.ok("Orchestrate documents background token analysis")
    else:
        result.fail("Orchestrate missing background token analysis documentation")


def check_orchestrate_fold_notes(result: ValidationResult) -> None:
    """Folded tasks must use a `fold:<phase>:<title>` notes convention (M5 — issue #35).

    Folds are reviewer/planner-spawned mid-run tasks (Haiku impl + Sonnet review) that
    inflate cost-weighted model distribution but don't show separately in the planned
    Step 2/2.1 lines. The `fold:` notes prefix lets token-analysis aggregate fold cost
    into a dedicated "Folds" row so users see fold spend distinct from planned waves.
    """
    orchestrate_path = PIPELINE_ROOT / "skills" / "orchestrate" / "SKILL.md"
    if not orchestrate_path.exists():
        return

    content = orchestrate_path.read_text()

    if "fold:" in content and "fold:<source-phase>" in content:
        result.ok("Orchestrate Backlog Integration documents fold-cost notes pattern")
    else:
        result.fail(
            "Orchestrate Backlog Integration missing 'fold:<source-phase>:...' notes "
            "convention (M5 mitigation for issue #35)"
        )


def check_token_analysis_fold_line(result: ValidationResult) -> None:
    """Token-analysis skill must surface fold cost as a separate line (M5)."""
    path = PIPELINE_ROOT / "skills" / "token-analysis" / "SKILL.md"
    if not path.exists():
        return

    content = path.read_text()

    if "Folds" in content and "notes" in content and "fold:" in content:
        result.ok("Token-analysis skill aggregates fold entries via notes prefix")
    else:
        result.fail(
            "Token-analysis skill missing Folds line / notes-prefix aggregation "
            "(M5 mitigation for issue #35)"
        )


def check_orchestrate_clarification_cap(result: ValidationResult) -> None:
    """Step 1a must document a round cap with cumulative token budget (M4 — issue #35).

    On the 7-task feat run analyzed in issue #35, a 3-round 1a clarification added
    ~31K incremental tokens beyond the initial launch (Q1-Q5 + sub-questions on Q2/Q3/Q4).
    Soft-cap of 2 rounds with a 150K cumulative-token hard cap forces closure when the
    user is digging deeper rather than introducing new decision points.
    """
    orchestrate_path = PIPELINE_ROOT / "skills" / "orchestrate" / "SKILL.md"
    if not orchestrate_path.exists():
        return

    content = orchestrate_path.read_text()

    if "Round cap" in content and "150K" in content:
        result.ok("Orchestrate Step 1a documents clarification round cap with token budget")
    else:
        result.fail(
            "Orchestrate Step 1a missing 'Round cap' with cumulative token budget "
            "(M4 mitigation for issue #35)"
        )

    if "FINALIZE NOW" in content:
        result.ok("Orchestrate Step 1a documents FINALIZE NOW escape hatch")
    else:
        result.fail(
            "Orchestrate Step 1a missing 'FINALIZE NOW' escape hatch on token-cap hit "
            "(M4 mitigation for issue #35)"
        )


def check_orchestrate_micro_plan_haiku_review(result: ValidationResult) -> None:
    """Step 2.1 must document micro-plan Haiku reviewer policy (M3 — issue #39).

    The review-cost ratio of 5.0x on micro-plans is structural: each Haiku implementation
    task is ~$0.003 vs. each Sonnet review at ~$0.046. Cost-proportional review on
    single-wave plans with <3KB briefs uses Haiku first-pass with Sonnet escalation on
    FAIL (~60% review-cost savings on micro-plans).
    """
    orchestrate_path = PIPELINE_ROOT / "skills" / "orchestrate" / "SKILL.md"
    if not orchestrate_path.exists():
        return

    content = orchestrate_path.read_text()

    if "Micro-plan exception" in content and "Haiku" in content:
        result.ok("Orchestrate Step 2.1 documents micro-plan Haiku review escalation")
    else:
        result.fail(
            "Orchestrate Step 2.1 missing 'Micro-plan exception' Haiku reviewer policy "
            "(M3 mitigation for issue #39)"
        )

    if "haiku→sonnet review escalation" in content:
        result.ok("Orchestrate Step 2.1 documents haiku→sonnet review escalation note")
    else:
        result.fail(
            "Orchestrate Step 2.1 missing 'haiku→sonnet review escalation' notes string "
            "(M3 mitigation for issue #39)"
        )


def check_orchestrate_no_full_orchestrator_fallback(result: ValidationResult) -> None:
    """Step 0.7 must not paste the full ORCHESTRATOR.md as a fallback (M2 — issue #39).

    The fixed-overhead finding identified ~6.5K tokens added per agent prompt when the
    extract logic fell back to loading the entire ORCHESTRATOR.md. The mitigation is
    partial-extract + missing-header note, never full file.
    """
    orchestrate_path = PIPELINE_ROOT / "skills" / "orchestrate" / "SKILL.md"
    if not orchestrate_path.exists():
        return

    content = orchestrate_path.read_text()

    if "paste the full file" in content.lower():
        result.fail(
            "Orchestrate Step 0.7 still has 'paste the full file' fallback for "
            "ORCHESTRATOR.md (defeats extract budget — see issue #39)"
        )
    else:
        result.ok("Orchestrate Step 0.7 does not paste full ORCHESTRATOR.md as fallback")

    if "Missing-header handling" in content:
        result.ok("Orchestrate Step 0.7 documents missing-header handling")
    else:
        result.fail(
            "Orchestrate Step 0.7 missing 'Missing-header handling' section "
            "(M2 mitigation for issue #39)"
        )


def check_agent_frontmatter(result: ValidationResult) -> None:
    """Agent files must have valid YAML frontmatter with name, model, description."""
    frontmatter_re = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
    for agent in REQUIRED_AGENTS:
        if agent == "implementer-contract.md":
            continue  # not an agent definition

        path = PIPELINE_ROOT / "agents" / agent
        if not path.exists():
            continue

        content = path.read_text()
        match = frontmatter_re.match(content)
        if not match:
            result.fail(f"Agent {agent}: missing YAML frontmatter")
            continue

        fm = match.group(1)
        for field in ["name:", "model:", "description:"]:
            if field in fm:
                result.ok(f"Agent {agent}: frontmatter has {field.rstrip(':')}")
            else:
                result.fail(f"Agent {agent}: frontmatter missing {field.rstrip(':')}")


def check_skill_frontmatter(result: ValidationResult) -> None:
    """Skill files must have valid YAML frontmatter with name and description."""
    frontmatter_re = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
    for skill in REQUIRED_SKILLS:
        path = PIPELINE_ROOT / "skills" / skill
        if not path.exists():
            continue

        content = path.read_text()
        match = frontmatter_re.match(content)
        if not match:
            result.fail(f"Skill {skill}: missing YAML frontmatter")
            continue

        fm = match.group(1)
        for field in ["name:", "description:"]:
            if field in fm:
                result.ok(f"Skill {skill}: frontmatter has {field.rstrip(':')}")
            else:
                result.fail(f"Skill {skill}: frontmatter missing {field.rstrip(':')}")


def check_cross_references(result: ValidationResult) -> None:
    """Verify key cross-references between pipeline files resolve."""
    orchestrate_path = PIPELINE_ROOT / "skills" / "orchestrate" / "SKILL.md"
    if not orchestrate_path.exists():
        return

    content = orchestrate_path.read_text()

    # Orchestrate must reference all agent types it launches
    agent_refs = {
        "architect-agent": "architect-agent",
        "implementer-agent": "implementer-agent",
        "code-reviewer-agent": "code-reviewer-agent",
    }
    for ref, name in agent_refs.items():
        if ref in content:
            result.ok(f"Orchestrate references {name}")
        else:
            result.fail(f"Orchestrate missing reference to {name}")

    # Orchestrate must reference key skills
    # Note: build-runner and test-runner are invoked by implementer agents, not the
    # orchestrator directly. The orchestrator references them via scripts/build.py
    # and scripts/test.py in the adapter config.
    skill_refs = ["open-pr", "token-analysis"]
    for skill in skill_refs:
        if skill in content:
            result.ok(f"Orchestrate references skill: {skill}")
        else:
            result.fail(f"Orchestrate missing reference to skill: {skill}")

    # Build/test are referenced via adapter commands, not skill names
    for cmd in ["build.py", "test.py"]:
        if cmd in content:
            result.ok(f"Orchestrate references build/test via {cmd}")
        else:
            result.fail(f"Orchestrate missing reference to {cmd}")


def check_fix_defects_skill(result: ValidationResult) -> None:
    """Validate the fix-defects skill references required patterns."""
    path = PIPELINE_ROOT / "skills" / "fix-defects" / "SKILL.md"
    if not path.exists():
        result.fail("fix-defects SKILL.md exists")
        return

    content = path.read_text()

    # Must reference the defect report template
    if "defect-report.md" in content:
        result.ok("fix-defects references defect-report.md template")
    else:
        result.fail("fix-defects missing reference to defect-report.md template")

    # Must reference PR comment reading via gh api
    if "gh api" in content:
        result.ok("fix-defects uses gh api for PR comment reading")
    else:
        result.fail("fix-defects missing gh api for PR comment reading")

    # Must reference the defect report header marker
    if "DEFECT REPORT" in content:
        result.ok("fix-defects references DEFECT REPORT header marker")
    else:
        result.fail("fix-defects missing DEFECT REPORT header marker")

    # Must define severity levels matching the template
    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        if severity in content:
            result.ok(f"fix-defects defines severity: {severity}")
        else:
            result.fail(f"fix-defects missing severity: {severity}")

    # Must reference agent types it launches
    for agent in ["architect-agent", "implementer-agent", "code-reviewer-agent"]:
        if agent in content:
            result.ok(f"fix-defects references {agent}")
        else:
            result.fail(f"fix-defects missing reference to {agent}")

    # Must reference token tracking
    if "TOKEN_LEDGER" in content:
        result.ok("fix-defects tracks TOKEN_LEDGER")
    else:
        result.fail("fix-defects missing TOKEN_LEDGER tracking")

    # Must handle replying to PR comments
    if "comment_id" in content.lower() or "reply" in content.lower():
        result.ok("fix-defects replies to PR comments after fix")
    else:
        result.fail("fix-defects missing PR comment reply mechanism")


def check_overlay_completeness(result: ValidationResult) -> None:
    """Check each overlay has all required files."""
    for overlay in OVERLAYS:
        overlay_dir = PIPELINE_ROOT / "overlays" / overlay
        if not overlay_dir.is_dir():
            result.fail(f"Missing overlay directory: overlays/{overlay}/")
            continue

        for req_file in REQUIRED_OVERLAY_FILES:
            path = overlay_dir / req_file
            if path.exists():
                result.ok(f"Overlay {overlay}: {req_file} exists")
            else:
                result.fail(f"Overlay {overlay}: missing {req_file}")


def check_overlay_essential_size(result: ValidationResult) -> None:
    """Overlay essential overlays must be compact (under threshold)."""
    for overlay in OVERLAYS:
        path = PIPELINE_ROOT / "overlays" / overlay / "implementer-overlay-essential.md"
        if not path.exists():
            continue  # already caught by completeness check

        size = len(path.read_text())
        if size <= ESSENTIAL_OVERLAY_MAX_CHARS:
            result.ok(f"Overlay {overlay}: essential overlay is {size} chars (under {ESSENTIAL_OVERLAY_MAX_CHARS})")
        else:
            result.fail(
                f"Overlay {overlay}: essential overlay is {size} chars "
                f"(exceeds {ESSENTIAL_OVERLAY_MAX_CHARS} limit)"
            )


def check_orchestrate_overlay_loading(result: ValidationResult) -> None:
    """Orchestrate must document cross-cutting overlay loading."""
    orchestrate_path = PIPELINE_ROOT / "skills" / "orchestrate" / "SKILL.md"
    if not orchestrate_path.exists():
        return

    content = orchestrate_path.read_text()

    if "overlays" in content.lower():
        result.ok("Orchestrate documents overlay loading")
    else:
        result.fail("Orchestrate missing overlay loading documentation")

    if "Cross-Cutting" in content:
        result.ok("Orchestrate documents cross-cutting overlay composition")
    else:
        result.fail("Orchestrate missing cross-cutting overlay composition documentation")


REQUIRED_ADAPTER_MANIFEST_FIELDS = ["name", "display_name", "capabilities", "detection", "stack_paths"]
REQUIRED_OVERLAY_MANIFEST_FIELDS = ["name", "display_name", "capabilities", "detection"]
VALID_DETECTION_TYPES = {"file_exists", "file_glob", "file_contains", "file_glob_contains"}


def check_manifest_validity(result: ValidationResult) -> None:
    """Each adapter/overlay manifest.json must have required fields and valid structure."""
    for adapter in ADAPTERS:
        manifest_path = PIPELINE_ROOT / "adapters" / adapter / "manifest.json"
        if not manifest_path.exists():
            result.fail(f"Adapter {adapter}: missing manifest.json")
            continue

        try:
            data = json.loads(manifest_path.read_text())
        except json.JSONDecodeError as e:
            result.fail(f"Adapter {adapter}: manifest.json is invalid JSON: {e}")
            continue

        for field in REQUIRED_ADAPTER_MANIFEST_FIELDS:
            if field in data:
                result.ok(f"Adapter {adapter}: manifest has '{field}'")
            else:
                result.fail(f"Adapter {adapter}: manifest missing '{field}'")

        # Verify name matches directory
        if data.get("name") == adapter:
            result.ok(f"Adapter {adapter}: manifest name matches directory")
        else:
            result.fail(f"Adapter {adapter}: manifest name '{data.get('name')}' != directory name '{adapter}'")

        # Verify capabilities is a list
        caps = data.get("capabilities")
        if isinstance(caps, list):
            result.ok(f"Adapter {adapter}: capabilities is a list")
        else:
            result.fail(f"Adapter {adapter}: capabilities must be a list")

        # Verify detection rules have valid types
        for rule in data.get("detection", []):
            rtype = rule.get("type", "")
            if rtype in VALID_DETECTION_TYPES:
                result.ok(f"Adapter {adapter}: detection rule type '{rtype}' is valid")
            else:
                result.fail(f"Adapter {adapter}: invalid detection rule type '{rtype}'")

        # Verify detection_fallback rules (if present) have valid types
        fallback = data.get("detection_fallback")
        if fallback is not None:
            for rule in fallback.get("rules", []):
                rtype = rule.get("type", "")
                if rtype in VALID_DETECTION_TYPES:
                    result.ok(f"Adapter {adapter}: fallback rule type '{rtype}' is valid")
                else:
                    result.fail(f"Adapter {adapter}: invalid fallback rule type '{rtype}'")

        # Verify implies_overlays is a list and references existing overlay directories
        implies = data.get("implies_overlays")
        if implies is not None:
            if isinstance(implies, list):
                result.ok(f"Adapter {adapter}: implies_overlays is a list")
                for ov_name in implies:
                    ov_dir = PIPELINE_ROOT / "overlays" / ov_name
                    if ov_dir.is_dir():
                        result.ok(f"Adapter {adapter}: implied overlay '{ov_name}' exists")
                    else:
                        result.fail(f"Adapter {adapter}: implied overlay '{ov_name}' not found at overlays/{ov_name}/")
            else:
                result.fail(f"Adapter {adapter}: implies_overlays must be a list")

    for overlay in OVERLAYS:
        manifest_path = PIPELINE_ROOT / "overlays" / overlay / "manifest.json"
        if not manifest_path.exists():
            result.fail(f"Overlay {overlay}: missing manifest.json")
            continue

        try:
            data = json.loads(manifest_path.read_text())
        except json.JSONDecodeError as e:
            result.fail(f"Overlay {overlay}: manifest.json is invalid JSON: {e}")
            continue

        for field in REQUIRED_OVERLAY_MANIFEST_FIELDS:
            if field in data:
                result.ok(f"Overlay {overlay}: manifest has '{field}'")
            else:
                result.fail(f"Overlay {overlay}: manifest missing '{field}'")

        if data.get("name") == overlay:
            result.ok(f"Overlay {overlay}: manifest name matches directory")
        else:
            result.fail(f"Overlay {overlay}: manifest name '{data.get('name')}' != directory name '{overlay}'")

        # Verify detection rules have valid types
        for rule in data.get("detection", []):
            rtype = rule.get("type", "")
            if rtype in VALID_DETECTION_TYPES:
                result.ok(f"Overlay {overlay}: detection rule type '{rtype}' is valid")
            else:
                result.fail(f"Overlay {overlay}: invalid detection rule type '{rtype}'")


def run_all_checks(verbose: bool = False) -> ValidationResult:
    result = ValidationResult()

    checks = [
        ("Required files", check_required_files),
        ("Adapter completeness", check_adapter_completeness),
        ("Essential overlay size", check_essential_overlay_size),
        ("Essential overlay no pipeline-protocol rules", check_essential_overlay_no_pipeline_protocol_rules),
        ("Agent injection markers", check_agent_markers),
        ("Agent output protocols", check_agent_protocols),
        ("TOKEN_REPORT consistency", check_token_report_consistency),
        ("Implementer contract references", check_implementer_contract_references),
        ("Reviewer no Standalone Mode", check_reviewer_no_standalone_mode),
        ("Reviewer OPTIONAL IMPROVEMENTS cap", check_reviewer_optional_cap),
        ("Clarification round caps", check_clarification_round_caps),
        ("Token-analysis output baselines", check_token_analysis_output_baselines),
        ("Token-analysis fixed overhead", check_token_analysis_fixed_overhead),
        ("Planner PLAN_WRITTEN stub", check_planner_plan_stub),
        ("Planner exact-string brief hints", check_planner_exact_string_brief_hints),
        ("Orchestrate reads plan from disk", check_orchestrate_reads_plan_from_disk),
        ("ORCHESTRATOR.md template sections", check_orchestrator_template_sections),
        ("Extract profile headers", check_extract_profile_headers),
        ("Overlay selection logic", check_orchestrate_overlay_selection),
        ("TOKEN_LEDGER schema", check_orchestrate_token_ledger),
        ("Reviewer reuse", check_orchestrate_reviewer_reuse),
        ("init.sh", check_init_script),
        ("Version file", check_version_file),
        ("Orchestrate local overlay loading", check_orchestrate_local_overlay_loading),
        ("Workflow optimizations", check_orchestrate_workflow_optimizations),
        ("ORCHESTRATOR.md no full-file fallback (M2)", check_orchestrate_no_full_orchestrator_fallback),
        ("Micro-plan Haiku review (M3)", check_orchestrate_micro_plan_haiku_review),
        ("1a clarification round cap (M4)", check_orchestrate_clarification_cap),
        ("Fold-cost notes pattern (M5)", check_orchestrate_fold_notes),
        ("Token-analysis fold line (M5)", check_token_analysis_fold_line),
        ("Agent frontmatter", check_agent_frontmatter),
        ("Skill frontmatter", check_skill_frontmatter),
        ("Cross-references", check_cross_references),
        ("Fix-defects skill", check_fix_defects_skill),
        ("Overlay completeness", check_overlay_completeness),
        ("Overlay essential size", check_overlay_essential_size),
        ("Orchestrate overlay loading", check_orchestrate_overlay_loading),
        ("Manifest validity", check_manifest_validity),
    ]

    for name, check_fn in checks:
        before_fail = len(result.failed)
        check_fn(result)
        after_fail = len(result.failed)
        if verbose:
            status = "PASS" if after_fail == before_fail else "FAIL"
            print(f"  [{status}] {name}")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate pipeline structural integrity")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show per-check status")
    args = parser.parse_args()

    print(f"Pipeline root: {PIPELINE_ROOT}")
    print()

    result = run_all_checks(verbose=args.verbose)

    print()
    print(f"Passed: {len(result.passed)}")
    print(f"Failed: {len(result.failed)}")

    if result.failed:
        print()
        print("FAILURES:")
        for msg in result.failed:
            print(f"  - {msg}")
        print()
        print("VALIDATION FAILED")
        sys.exit(1)
    else:
        print()
        print("ALL CHECKS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
