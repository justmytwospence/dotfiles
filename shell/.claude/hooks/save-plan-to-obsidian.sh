#!/usr/bin/env bash
set -euo pipefail

input=$(cat)

cwd=$(echo "$input" | jq -r '.cwd // empty')
plan_file=$(echo "$input" | jq -r '.tool_response.filePath // empty')

if [[ -z "$plan_file" ]]; then
  exit 0
fi

# Derive project (main repo dir) and optional worktree subdir.
# git_root is the current worktree's root; git_common_dir's parent is the main repo root.
git_root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || true)
git_common_dir=$(git -C "$cwd" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)
if [[ -n "$git_common_dir" ]]; then
  main_root=$(dirname "$git_common_dir")
else
  main_root="${git_root:-$cwd}"
fi
project=$(basename "$main_root")
worktree_subdir=""
if [[ -n "$git_root" && "$git_root" != "$main_root" ]]; then
  worktree_subdir="$(basename "$git_root")/"
fi

# Extract title from first heading in plan file
plan_title=$(grep -m1 '^#' "$plan_file" 2>/dev/null | sed 's/^#* *//' | head -c 80 || true)
plan_title="${plan_title:-Unnamed Plan}"

# Build slug
slug=$(echo "$plan_title" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9 -]//g' | tr ' ' '-' | sed 's/--*/-/g; s/^-//; s/-$//')
date=$(date +%Y-%m-%d)
obsidian_path="Claude Code Plans/${project}/${worktree_subdir}${date} - ${slug}.md"

# Resolve the vault path on disk (open vault first, else the first one).
vault_path=$(jq -r '.vaults | to_entries | map(.value) | ((map(select(.open)) + .)[0]).path // empty' \
  "$HOME/Library/Application Support/obsidian/obsidian.json" 2>/dev/null || true)

body=$(cat "$plan_file")
content=$(printf -- '---\ndate: %s\nproject: %s\ntags: [claude-code-plan]\n---\n\n%s' \
  "$date" "$project" "$body")

# Write the note straight to the vault on disk. Deliberately avoids the `obsidian`
# CLI and `open` — both can launch/surface/restore the app window. A plain file
# write never touches the GUI; Obsidian indexes it via its watcher (if running) or
# on next launch. Atomic temp+rename so a killed write can't leave a partial file.
saved=0
if [[ -n "$vault_path" && -d "$vault_path" ]]; then
  dest="$vault_path/$obsidian_path"
  tmp="$dest.tmp.$$"
  if mkdir -p "$(dirname "$dest")" && printf '%s' "$content" > "$tmp" && mv -f "$tmp" "$dest"; then
    saved=1
  else
    rm -f "$tmp" 2>/dev/null || true
  fi
fi

if [[ $saved -eq 1 ]]; then
  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "Plan already saved to Obsidian at '${obsidian_path}'. Do not call mcp__obsidian__write_note for this plan."
  }
}
EOF
  exit 0
fi

cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "IMPORTANT: A plan was just approved. Before starting any implementation, save this plan to Obsidian using mcp__obsidian__write_note. Use path '${obsidian_path}', read the plan content from '${plan_file}', and include frontmatter with date '${date}', project '${project}', and tags ['claude-code-plan']. If the Obsidian MCP is unavailable, skip silently and proceed with implementation."
  }
}
EOF
