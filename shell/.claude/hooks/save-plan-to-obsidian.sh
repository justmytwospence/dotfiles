#!/usr/bin/env bash
set -euo pipefail

input=$(cat)

cwd=$(echo "$input" | jq -r '.cwd // empty')
plan_file=$(echo "$input" | jq -r '.tool_response.filePath // empty')

if [[ -z "$plan_file" ]]; then
  exit 0
fi

# Derive project name
git_root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || true)
project=$(basename "${git_root:-$cwd}")

# Extract title from first heading in plan file
plan_title=$(grep -m1 '^#' "$plan_file" 2>/dev/null | sed 's/^#* *//' | head -c 80 || true)
plan_title="${plan_title:-Unnamed Plan}"

# Build slug
slug=$(echo "$plan_title" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9 -]//g' | tr ' ' '-' | sed 's/--*/-/g; s/^-//; s/-$//')
date=$(date +%Y-%m-%d)
obsidian_path="Claude Code Plans/${project}/${date} - ${slug}.md"

cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "IMPORTANT: A plan was just approved. Before starting any implementation, save this plan to Obsidian using mcp__mcpjungle__obsidian__write_note. Use path '${obsidian_path}', read the plan content from '${plan_file}', and include frontmatter with date '${date}', project '${project}', and tags ['claude-code-plan']. If the Obsidian MCP is unavailable, skip silently and proceed with implementation."
  }
}
EOF
