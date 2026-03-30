#!/usr/bin/env bash
#
# claude-code-pipeline/init.sh
# Bootstrap script: links the pipeline into a target project's .claude/ directory
#
# Usage:
#   bash init.sh /path/to/project [--stack=<name>]... [--force]
#   Supports multiple --stack flags for multi-stack repos.
#

set -euo pipefail

# --- Constants ---
PIPELINE_ROOT="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_NAME="$(basename "$0")"

# --- Helpers ---
info()  { echo "[pipeline] $*"; }
warn()  { echo "[pipeline] WARNING: $*" >&2; }
error() { echo "[pipeline] ERROR: $*" >&2; exit 1; }

# jq is required for manifest-driven adapter discovery
command -v jq &>/dev/null || error "jq is required but not installed. Install via: brew install jq (macOS) or apt-get install jq (Linux)"

# Discover available adapters from manifest files
available_adapters() {
    local names=()
    for manifest in "$PIPELINE_ROOT"/adapters/*/manifest.json; do
        [ -f "$manifest" ] || continue
        names+=("$(jq -r '.name' "$manifest")")
    done
    echo "${names[*]}"
}

usage() {
    local adapters
    adapters=$(available_adapters | tr ' ' ', ')
    cat <<EOF
Usage: bash $SCRIPT_NAME <project-dir> [OPTIONS]

Bootstrap the Claude Code Pipeline into a project.

Arguments:
  project-dir          Path to the target project root

Options:
  --stack=<name>       Force a specific adapter ($adapters)
                       Can be specified multiple times for multi-stack repos.
                       Auto-detected from project files if omitted.
  --force              Overwrite existing symlinks and config
  --help               Show this help message

Examples:
  bash $SCRIPT_NAME .
  bash $SCRIPT_NAME /path/to/myapp --stack=react
  bash $SCRIPT_NAME /path/to/myapp --stack=react --stack=python --stack=bicep
  bash $SCRIPT_NAME . --force
EOF
    exit 0
}

# --- Parse arguments ---
PROJECT_DIR=""
STACKS=()
FORCE=false

for arg in "$@"; do
    case "$arg" in
        --stack=*)  STACKS+=("${arg#--stack=}") ;;
        --force)    FORCE=true ;;
        --help|-h)  usage ;;
        -*)         error "Unknown option: $arg" ;;
        *)
            if [ -z "$PROJECT_DIR" ]; then
                PROJECT_DIR="$arg"
            else
                error "Unexpected argument: $arg"
            fi
            ;;
    esac
done

[ -z "$PROJECT_DIR" ] && error "Missing required argument: project-dir. Run with --help for usage."
[ -d "$PROJECT_DIR" ] || error "Project directory does not exist: $PROJECT_DIR"

PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"

# --- Step 1: Ensure .claude/ exists ---
CLAUDE_DIR="$PROJECT_DIR/.claude"
mkdir -p "$CLAUDE_DIR"
mkdir -p "$CLAUDE_DIR/tmp"

# --- Step 2: Manifest-driven stack detection ---

# Evaluate a single detection rule against a project directory
# Returns 0 (true) if the rule matches, 1 (false) otherwise
eval_detection_rule() {
    local dir="$1"
    local rtype="$2"
    local rpath="$3"
    local rpattern="$4"

    case "$rtype" in
        file_exists)
            [ -f "$dir/$rpath" ] && return 0
            ;;
        file_glob)
            compgen -G "$dir/$rpattern" > /dev/null 2>&1 && return 0
            ;;
        file_contains)
            [ -f "$dir/$rpath" ] && grep -qE "$rpattern" "$dir/$rpath" 2>/dev/null && return 0
            ;;
        file_glob_contains)
            # Match files by glob, then check content of each
            for _f in "$dir"/$rpath; do
                if [ -e "$_f" ] && grep -qE "$rpattern" "$_f" 2>/dev/null; then
                    return 0
                fi
            done
            ;;
    esac
    return 1
}

# Evaluate all detection rules in a manifest's detection array
# Returns 0 if any rule matches (OR logic)
eval_detection_rules() {
    local dir="$1"
    local manifest="$2"
    local rules_path="${3:-.detection}"

    local rule_count
    rule_count=$(jq "$rules_path | length" "$manifest" 2>/dev/null) || return 1
    [ "$rule_count" -gt 0 ] 2>/dev/null || return 1

    for ((i=0; i<rule_count; i++)); do
        local rtype rpath rpattern
        rtype=$(jq -r "${rules_path}[$i].type" "$manifest")
        rpath=$(jq -r "${rules_path}[$i].path // empty" "$manifest")
        rpattern=$(jq -r "${rules_path}[$i].pattern // empty" "$manifest")

        if eval_detection_rule "$dir" "$rtype" "$rpath" "$rpattern"; then
            return 0
        fi
    done
    return 1
}

detect_stacks() {
    local dir="$1"
    local found=()
    local fallback_candidates=()

    for manifest in "$PIPELINE_ROOT"/adapters/*/manifest.json; do
        [ -f "$manifest" ] || continue
        local adapter_name
        adapter_name=$(jq -r '.name' "$manifest")

        if eval_detection_rules "$dir" "$manifest" ".detection"; then
            found+=("$adapter_name")
        else
            # Check if this adapter has a fallback detection
            local has_fallback
            has_fallback=$(jq -r '.detection_fallback // empty' "$manifest")
            if [ -n "$has_fallback" ] && [ "$has_fallback" != "null" ]; then
                fallback_candidates+=("$adapter_name|$manifest")
            fi
        fi
    done

    # Process fallback candidates (e.g., react for generic Node/TS projects)
    # Fallback activates when no other stacks matched OR tsconfig.json exists
    if [ ${#found[@]} -eq 0 ]; then
        for candidate in "${fallback_candidates[@]}"; do
            local cname="${candidate%%|*}"
            local cmanifest="${candidate##*|}"
            if eval_detection_rules "$dir" "$cmanifest" ".detection_fallback.rules"; then
                found+=("$cname")
            fi
        done
    else
        # Even with other stacks found, check fallback if tsconfig.json exists (multi-stack TS)
        for candidate in "${fallback_candidates[@]}"; do
            local cname="${candidate%%|*}"
            local cmanifest="${candidate##*|}"
            if [ -f "$dir/tsconfig.json" ]; then
                if eval_detection_rules "$dir" "$cmanifest" ".detection_fallback.rules"; then
                    found+=("$cname")
                fi
            fi
        done
    fi

    echo "${found[*]}"
}

# Generate stack_paths from adapter manifests
generate_stack_paths() {
    local dir="$1"
    shift
    local stacks=("$@")

    for stack in "${stacks[@]}"; do
        local manifest="$PIPELINE_ROOT/adapters/$stack/manifest.json"
        [ -f "$manifest" ] || continue

        local paths=""

        # Check preferred directories first (first match wins)
        local dir_count
        dir_count=$(jq '.stack_paths.directories | length' "$manifest" 2>/dev/null) || dir_count=0
        for ((i=0; i<dir_count; i++)); do
            local candidate
            candidate=$(jq -r ".stack_paths.directories[$i]" "$manifest")
            if [ -d "$dir/$candidate" ]; then
                paths="$candidate/**"
                break
            fi
        done

        # Fallback to glob patterns
        if [ -z "$paths" ]; then
            paths=$(jq -r '.stack_paths.fallback_globs | join(",")' "$manifest" 2>/dev/null)
        fi

        echo "stack_paths.$stack=$paths"
    done
}

# Detect overlays from adapter implies_overlays + overlay self-detection
detect_overlays() {
    local dir="$1"
    shift
    local stacks=("$@")
    local overlays=()

    # Collect overlays implied by active adapters
    for stack in "${stacks[@]}"; do
        local manifest="$PIPELINE_ROOT/adapters/$stack/manifest.json"
        [ -f "$manifest" ] || continue
        while IFS= read -r ov; do
            [ -n "$ov" ] && overlays+=("$ov")
        done < <(jq -r '.implies_overlays[]? // empty' "$manifest" 2>/dev/null)
    done

    # Check each overlay's own detection rules
    for ov_manifest in "$PIPELINE_ROOT"/overlays/*/manifest.json; do
        [ -f "$ov_manifest" ] || continue
        local ov_name
        ov_name=$(jq -r '.name' "$ov_manifest")

        # Skip if already implied
        local already=false
        for existing in "${overlays[@]}"; do
            [ "$existing" = "$ov_name" ] && already=true && break
        done
        [ "$already" = true ] && continue

        # Run overlay's own detection rules
        if eval_detection_rules "$dir" "$ov_manifest" ".detection"; then
            overlays+=("$ov_name")
        fi
    done

    # Deduplicate and return comma-separated
    local unique
    unique=$(printf '%s\n' "${overlays[@]}" | sort -u | tr '\n' ',' | sed 's/,$//')
    echo "$unique"
}

# Aggregate capabilities from active adapters and overlays
aggregate_capabilities() {
    local stacks_csv="$1"
    local overlays_csv="$2"
    local caps=()

    # From adapters
    IFS=',' read -ra stack_arr <<< "$stacks_csv"
    for stack in "${stack_arr[@]}"; do
        local manifest="$PIPELINE_ROOT/adapters/$stack/manifest.json"
        [ -f "$manifest" ] || continue
        while IFS= read -r cap; do
            [ -n "$cap" ] && caps+=("$cap")
        done < <(jq -r '.capabilities[]? // empty' "$manifest" 2>/dev/null)
    done

    # From overlays
    if [ -n "$overlays_csv" ]; then
        IFS=',' read -ra ov_arr <<< "$overlays_csv"
        for ov in "${ov_arr[@]}"; do
            local ov_manifest="$PIPELINE_ROOT/overlays/$ov/manifest.json"
            [ -f "$ov_manifest" ] || continue
            while IFS= read -r cap; do
                [ -n "$cap" ] && caps+=("$cap")
            done < <(jq -r '.capabilities[]? // empty' "$ov_manifest" 2>/dev/null)
        done
    fi

    # Deduplicate and return comma-separated
    local unique
    unique=$(printf '%s\n' "${caps[@]}" | sort -u | tr '\n' ',' | sed 's/,$//')
    echo "$unique"
}

if [ ${#STACKS[@]} -eq 0 ]; then
    read -ra STACKS <<< "$(detect_stacks "$PROJECT_DIR")"
    if [ ${#STACKS[@]} -eq 0 ]; then
        avail=$(available_adapters | tr ' ' ', ')
        error "Could not auto-detect tech stack. Use --stack=<name> to specify.\nAvailable: $avail"
    fi
    info "Auto-detected stack(s): ${STACKS[*]}"
else
    info "Using specified stack(s): ${STACKS[*]}"
fi

# Validate all specified adapters exist
for s in "${STACKS[@]}"; do
    [ -d "$PIPELINE_ROOT/adapters/$s" ] || error "Adapter not found: $PIPELINE_ROOT/adapters/$s"
done

STACKS_CSV=$(IFS=,; echo "${STACKS[*]}")

# --- Step 3: Detect overlays and write pipeline.config ---
OVERLAYS=$(detect_overlays "$PROJECT_DIR" "${STACKS[@]}")
if [ -n "$OVERLAYS" ]; then
    info "Detected overlay(s): $OVERLAYS"
fi

# Generate stack_paths
STACK_PATHS_LINES=$(generate_stack_paths "$PROJECT_DIR" "${STACKS[@]}")

# Aggregate capabilities from adapters + overlays
CAPABILITIES=$(aggregate_capabilities "$STACKS_CSV" "$OVERLAYS")
if [ -n "$CAPABILITIES" ]; then
    info "Active capabilities: $CAPABILITIES"
fi

CONFIG_FILE="$CLAUDE_DIR/pipeline.config"
if [ -f "$CONFIG_FILE" ] && [ "$FORCE" = false ]; then
    info "pipeline.config already exists. Use --force to overwrite."
else
    cat > "$CONFIG_FILE" <<EOF
# Claude Code Pipeline Configuration
# Generated by init.sh — edit as needed

# Active tech-stack adapters (comma-separated, first is primary/fallback)
stacks=$STACKS_CSV

# File-to-stack mapping (glob patterns, comma-separated per stack)
# Edit these to match your project structure
$STACK_PATHS_LINES

# Absolute path to the pipeline repo
pipeline_root=$PIPELINE_ROOT

# Cross-cutting overlays (comma-separated, empty if none)
overlays=$OVERLAYS

# Capabilities aggregated from active adapters and overlays
# Used by skills for conditional behavior (e.g., azure-auth triggers Azure login pre-flight)
capabilities=$CAPABILITIES

# Date this config was generated
initialized=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF
    info "Wrote $CONFIG_FILE"
fi

# --- Step 4: Create symlinks ---
create_symlink() {
    local target="$1"
    local link="$2"
    local desc="$3"

    if [ -L "$link" ]; then
        if [ "$FORCE" = true ]; then
            rm "$link"
        else
            local existing
            existing=$(readlink "$link" 2>/dev/null || echo "unknown")
            if [ "$existing" = "$target" ]; then
                info "Symlink already correct: $desc"
                return
            fi
            warn "Symlink exists but points elsewhere: $link -> $existing (expected $target). Use --force to fix."
            return
        fi
    elif [ -e "$link" ]; then
        if [ "$FORCE" = true ]; then
            # It's a real directory/file — back it up
            local backup="${link}.backup.$(date +%s)"
            mv "$link" "$backup"
            warn "Backed up existing $desc to $backup"
        else
            warn "$desc already exists as a regular file/directory. Use --force to replace (will backup)."
            return
        fi
    fi

    ln -s "$target" "$link"
    info "Linked: $desc -> $target"
}

# Agents
create_symlink "$PIPELINE_ROOT/agents" "$CLAUDE_DIR/agents" "agents"

# Skills
create_symlink "$PIPELINE_ROOT/skills" "$CLAUDE_DIR/skills" "skills"

# Scripts (per-stack subdirectories)
# Remove legacy flat symlink if present
if [ -L "$CLAUDE_DIR/scripts" ]; then
    if [ "$FORCE" = true ]; then
        rm "$CLAUDE_DIR/scripts"
        info "Removed legacy flat scripts symlink"
    else
        legacy_target=$(readlink "$CLAUDE_DIR/scripts" 2>/dev/null || echo "unknown")
        if [[ "$legacy_target" == */adapters/*/scripts ]]; then
            rm "$CLAUDE_DIR/scripts"
            info "Migrated legacy flat scripts symlink to per-stack layout"
        fi
    fi
fi
mkdir -p "$CLAUDE_DIR/scripts"
for s in "${STACKS[@]}"; do
    create_symlink "$PIPELINE_ROOT/adapters/$s/scripts" "$CLAUDE_DIR/scripts/$s" "scripts/$s"
done

# Overlays (cross-cutting, only when detected)
if [ -n "$OVERLAYS" ]; then
    OVERLAYS_DIR="$PIPELINE_ROOT/overlays"
    if [ -d "$OVERLAYS_DIR" ]; then
        create_symlink "$OVERLAYS_DIR" "$CLAUDE_DIR/overlays" "overlays"
    fi
fi

# --- Step 5: Merge hooks into settings.json ---
SETTINGS_FILE="$CLAUDE_DIR/settings.json"

for s in "${STACKS[@]}"; do
    ADAPTER_HOOKS="$PIPELINE_ROOT/adapters/$s/hooks.json"
    if [ -f "$ADAPTER_HOOKS" ]; then
        if [ -f "$SETTINGS_FILE" ]; then
            MERGED=$(jq -s '
                (.[0].hooks.PreToolUse // []) as $existing |
                (.[1].hooks.PreToolUse // []) as $adapter |
                .[0] * {hooks: {PreToolUse: ($existing + $adapter | unique_by(.matcher + (.hooks | tostring)))}}
            ' "$SETTINGS_FILE" "$ADAPTER_HOOKS" 2>/dev/null || echo "")

            if [ -n "$MERGED" ]; then
                echo "$MERGED" > "$SETTINGS_FILE"
                info "Merged $s adapter hooks into settings.json"
            else
                warn "Could not merge $s hooks."
            fi
        else
            cp "$ADAPTER_HOOKS" "$SETTINGS_FILE"
            info "Created settings.json from $s adapter hooks"
        fi
    fi
done

# --- Step 6: Generate CLAUDE.md if not present ---
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
if [ ! -f "$CLAUDE_MD" ]; then
    TEMPLATE="$PIPELINE_ROOT/templates/CLAUDE.md.template"
    if [ -f "$TEMPLATE" ]; then
        cp "$TEMPLATE" "$CLAUDE_MD"
        info "Generated CLAUDE.md from template (edit to customize)"
    fi
else
    info "CLAUDE.md already exists — not overwriting"
fi

# --- Step 7: Generate ORCHESTRATOR.md skeleton if not present ---
ORCHESTRATOR_MD="$CLAUDE_DIR/ORCHESTRATOR.md"
if [ ! -f "$ORCHESTRATOR_MD" ]; then
    TEMPLATE="$PIPELINE_ROOT/templates/ORCHESTRATOR.md.template"
    if [ -f "$TEMPLATE" ]; then
        cp "$TEMPLATE" "$ORCHESTRATOR_MD"
        info "Generated ORCHESTRATOR.md skeleton from template (edit to customize)"
    fi
else
    info "ORCHESTRATOR.md already exists — not overwriting"
fi

# --- Step 8: Summary ---
echo ""
echo "========================================"
echo "  Claude Code Pipeline initialized!"
echo "========================================"
echo ""
echo "  Project:    $PROJECT_DIR"
echo "  Stack(s):   $STACKS_CSV"
echo "  Pipeline:   $PIPELINE_ROOT"
echo ""
echo "  Symlinks:"
echo "    .claude/agents  -> pipeline/agents"
echo "    .claude/skills  -> pipeline/skills"
for s in "${STACKS[@]}"; do
echo "    .claude/scripts/$s -> pipeline/adapters/$s/scripts"
done
if [ -n "$OVERLAYS" ]; then
echo "    .claude/overlays -> pipeline/overlays"
fi
echo ""
echo "  Config:     .claude/pipeline.config"
echo "  Hooks:      .claude/settings.json"
if [ -n "$OVERLAYS" ]; then
echo "  Overlays:   $OVERLAYS"
fi
echo ""
echo "  Next steps:"
echo "    1. Edit .claude/pipeline.config — review stack_paths mappings"
echo "    2. Edit .claude/CLAUDE.md with your project description"
echo "    3. Edit .claude/ORCHESTRATOR.md with your architecture"
echo "    4. Run 'claude' and use /orchestrate to start the pipeline"
echo ""
