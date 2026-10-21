# Project-scoped MCP servers (mcp.json "projects": "<marker>"): switched on in each repo in
# ~/Projects that has the marker, for pi, Codex and opencode. Claude Code's local-scope
# entries come from modify_private_dot_claude.json. Prints only what it changed; a failure
# here only warns, never fails the apply.
converge_project_mcp() {
    python3 -B - {{ joinPath .chezmoi.sourceDir "lib" | quote }} <<'PY' || echo "project MCP servers: failed" >&2
import sys
sys.path.insert(0, sys.argv[1])
import agent_settings
agent_settings.enable_project_servers()
PY
}
run converge_project_mcp
