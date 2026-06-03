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

# Locate the obsidian CLI (PATH first, then the app bundle).
obsidian_bin=""
if command -v obsidian >/dev/null 2>&1; then
  obsidian_bin="obsidian"
elif [[ -x "/Applications/Obsidian.app/Contents/MacOS/obsidian" ]]; then
  obsidian_bin="/Applications/Obsidian.app/Contents/MacOS/obsidian"
fi

# Resolve the vault path on disk (open vault first, else the first one) so we can
# write directly when Obsidian isn't running, without launching/activating the app.
vault_path=$(jq -r '.vaults | to_entries | map(.value) | ((map(select(.open)) + .)[0]).path // empty' \
  "$HOME/Library/Application Support/obsidian/obsidian.json" 2>/dev/null || true)

try_cli_save() {
  "$obsidian_bin" create path="$obsidian_path" content="$content" overwrite >/dev/null 2>&1
}

body=$(cat "$plan_file")
content=$(printf -- '---\ndate: %s\nproject: %s\ntags: [claude-code-plan]\n---\n\n%s' \
  "$date" "$project" "$body")

saved=0
if [[ -n "$obsidian_bin" ]] && try_cli_save; then
  saved=1
elif [[ -n "$vault_path" && -d "$vault_path" ]]; then
  # CLI unavailable or Obsidian not running. Write straight to the vault on disk
  # instead of launching the app with `open` — which would restore a minimized
  # Obsidian window. Obsidian indexes the file via its watcher / on next launch.
  dest="$vault_path/$obsidian_path"
  if mkdir -p "$(dirname "$dest")" && printf '%s' "$content" > "$dest"; then
    saved=1
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
