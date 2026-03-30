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
import re
import sys
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parent.parent

ADAPTERS = ["python", "react", "swift-ios", "bicep"]

REQUIRED_ADAPTER_FILES = [
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
]

ESSENTIAL_OVERLAY_MAX_CHARS = 1000

OVERLAYS = ["azure-sdk"]

# Overlays intentionally omit test-overlay.md: testing patterns for Azure SDK
# are language-specific and covered by each adapter's own test overlay.
REQUIRED_OVERLAY_FILES = [
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
        "Architecture",
        "Key Services / Modules",
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
                      "pipeline.config.template", "defect-report.md"]:
        path = PIPELINE_ROOT / "templates" / template
        if path.exists():
            result.ok(f"Template exists: {template}")
        else:
            result.fail(f"Missing template: {template}")


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
    """All agents that should emit TOKEN_REPORT must document the format."""
    token_report_agents = ["implementer-agent.md", "code-reviewer-agent.md", "architect-agent.md"]
    for agent_file in token_report_agents:
        path = PIPELINE_ROOT / "agents" / agent_file
        if not path.exists():
            continue

        content = path.read_text()
        has_start = "---TOKEN_REPORT---" in content
        has_end = "---END_TOKEN_REPORT---" in content
        has_files_read = "FILES_READ:" in content
        has_self_input = "SELF_ASSESSED_INPUT:" in content
        has_self_output = "SELF_ASSESSED_OUTPUT:" in content

        if all([has_start, has_end, has_files_read, has_self_input, has_self_output]):
            result.ok(f"Agent {agent_file}: TOKEN_REPORT format complete")
        else:
            missing = []
            if not has_start:
                missing.append("---TOKEN_REPORT---")
            if not has_end:
                missing.append("---END_TOKEN_REPORT---")
            if not has_files_read:
                missing.append("FILES_READ:")
            if not has_self_input:
                missing.append("SELF_ASSESSED_INPUT:")
            if not has_self_output:
                missing.append("SELF_ASSESSED_OUTPUT:")
            result.fail(f"Agent {agent_file}: TOKEN_REPORT missing: {', '.join(missing)}")


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
        "agent_input_self", "agent_output_self",
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


def check_init_bicep_detection(result: ValidationResult) -> None:
    """init.sh must contain Bicep stack detection."""
    init_path = PIPELINE_ROOT / "init.sh"
    if not init_path.exists():
        return

    content = init_path.read_text()

    if "bicep" in content.lower():
        result.ok("init.sh references bicep stack")
    else:
        result.fail("init.sh missing bicep stack detection")

    if "detect_overlays" in content or "overlays" in content:
        result.ok("init.sh supports overlay detection")
    else:
        result.fail("init.sh missing overlay detection support")


def run_all_checks(verbose: bool = False) -> ValidationResult:
    result = ValidationResult()

    checks = [
        ("Required files", check_required_files),
        ("Adapter completeness", check_adapter_completeness),
        ("Essential overlay size", check_essential_overlay_size),
        ("Agent injection markers", check_agent_markers),
        ("Agent output protocols", check_agent_protocols),
        ("TOKEN_REPORT consistency", check_token_report_consistency),
        ("Implementer contract references", check_implementer_contract_references),
        ("ORCHESTRATOR.md template sections", check_orchestrator_template_sections),
        ("Extract profile headers", check_extract_profile_headers),
        ("Overlay selection logic", check_orchestrate_overlay_selection),
        ("TOKEN_LEDGER schema", check_orchestrate_token_ledger),
        ("Reviewer reuse", check_orchestrate_reviewer_reuse),
        ("init.sh", check_init_script),
        ("Agent frontmatter", check_agent_frontmatter),
        ("Skill frontmatter", check_skill_frontmatter),
        ("Cross-references", check_cross_references),
        ("Fix-defects skill", check_fix_defects_skill),
        ("Overlay completeness", check_overlay_completeness),
        ("Overlay essential size", check_overlay_essential_size),
        ("Orchestrate overlay loading", check_orchestrate_overlay_loading),
        ("init.sh bicep detection", check_init_bicep_detection),
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
