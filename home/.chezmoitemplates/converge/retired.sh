# Removes what this repo used to install or what other tools left behind. Dropping the
# line that installed something leaves existing installs in place; the step that removes
# it goes here, in the same change (AGENTS.md "Provisioning"). Every step is a cheap
# check that does nothing once the thing is gone. Runs first, so a replacement installed
# later in the converge never collides with what it replaces.
converge_retired() {
gone() { echo "retired: $*"; }

# beads (bd): dropped for the harnesses' own task tools. Projects that still
# carry a .beads/ directory keep their data; only the CLI and its telemetry go.
if command -v brew >/dev/null 2>&1 && brew list --formula beads >/dev/null 2>&1; then
    brew uninstall --formula beads >/dev/null && gone "beads (brew)"
fi
bd=$(command -v bd 2>/dev/null || true)
case $bd in
    "") ;;
    "$HOME"/*) rm -f "$bd" && gone "$bd" ;;
    *) echo "retired: bd is still installed at $bd; remove it by hand" >&2 ;;
esac
[ -e "$HOME/.beads" ] && rm -rf "$HOME/.beads" && gone "~/.beads"
[ -d /opt/homebrew/etc/dolt ] && ! command -v dolt >/dev/null 2>&1 && rm -rf /opt/homebrew/etc/dolt && gone "beads' dolt config"

# Cursor. --zap also takes ~/.cursor and its Library state.
if command -v brew >/dev/null 2>&1 && brew list --cask cursor >/dev/null 2>&1; then
    brew uninstall --zap --cask cursor >/dev/null && gone "Cursor"
fi

# Codex desktop's agent import, now pinned off (CODEX_PINS in lib/agent_settings.py), left
# a stow-era copy of AGENTS.md in $HOME (pi and opencode load it as an ancestor of every
# project, after the real one) and Cursor's built-in skills in the shared skills directory.
if [ -f "$HOME/AGENTS.md" ] && grep -q "GNU stow" "$HOME/AGENTS.md"; then
    rm -f "$HOME/AGENTS.md" && gone "~/AGENTS.md"
fi
for skill in create-rule create-skill create-subagent migrate-to-skills shell update-cursor-settings .trash; do
    [ -e "$HOME/.agents/skills/$skill" ] && rm -rf "$HOME/.agents/skills/$skill" && gone "~/.agents/skills/$skill"
done

# Per-agent links back into ~/.agents/skills, which `npx skills add` without `-a` fans out to every agent it detects. These agents read
# ~/.agents/skills already, so these per-skill links only duplicate the shared root.
for dir in "$HOME/.pi/agent/skills" "$HOME/.config/opencode/skills" "$HOME/.codeium/windsurf/skills" "$HOME/.kiro/skills" "$HOME/.snowflake/cortex/skills"; do
    [ -d "$dir" ] && [ ! -L "$dir" ] || continue
    for link in "$dir"/*; do
        [ -L "$link" ] && case $(readlink "$link") in *.agents/skills/*) rm -f "$link" && gone "$link" ;; esac
    done
    rmdir "$dir" 2>/dev/null && gone "$dir"
done

# Superset (its hooks are purged by DENY in lib/agent_settings.py) left slash commands here.
if [ -d "$HOME/.agents/commands/superset" ]; then
    rm -rf "$HOME/.agents/commands/superset" && gone "~/.agents/commands/superset"
    rmdir "$HOME/.agents/commands" 2>/dev/null
fi

# pi-voice: dictation belongs to the OS (Handy), not to one harness. Its Parakeet model
# stays in the Hugging Face cache, which Handy uses.
[ -e "$HOME/.pi/agent/pi-voice.json" ] && rm -f "$HOME/.pi/agent/pi-voice.json" && gone "~/.pi/agent/pi-voice.json"
# pi-cc-extensions: replaced by the suite's pi-cc-render (configured in pi-cc-render.json).
[ -e "$HOME/.pi/agent/pi-cc-extensions.json" ] && rm -f "$HOME/.pi/agent/pi-cc-extensions.json" && gone "~/.pi/agent/pi-cc-extensions.json"

# Skills no longer used (tmux: herdr replaced it), or moved out of the global set because they
# only matter in a few projects (install those per project:
# `npx skills add <repo> -s <skill> -a codex claude-code -y`).
# Their entries in skills' lock file go too, so the CLI does not list them as installed.
lock="$HOME/.agents/.skill-lock.json"
for skill in dotfiles-sync marimo-export-on-commit jupyter-to-marimo marimo-notebook marimo-pair marimo-lens mcp-builder pymc-modeling priorlabs typesafe-ai typst coral-quickstart setting-up-coral creating-a-coral-task running-coral-experiments orca-cli orchestration tmux; do
    [ -e "$HOME/.agents/skills/$skill" ] && rm -rf "$HOME/.agents/skills/$skill" && gone "~/.agents/skills/$skill"
    if [ -f "$lock" ] && command -v jq >/dev/null 2>&1 && jq -e --arg s "$skill" '.skills | has($s)' "$lock" >/dev/null 2>&1; then
        jq --arg s "$skill" 'del(.skills[$s])' "$lock" >"$lock.tmp" && mv "$lock.tmp" "$lock"
    fi
done

# Superset (agent IDE), retired. Its hooks in Claude Code and Codex are purged by DENY in
# lib/agent_settings.py; its pi extension, its hooks in the other agents' configs (Devin,
# Gemini: entries whose command names it; Muse Code: its managed-hooks path and env list),
# its Amp plugin, and the app's own state go here. Unrelated hooks stay.
[ -e "$HOME/.pi/agent/extensions/superset-hooks.ts" ] && rm -f "$HOME/.pi/agent/extensions/superset-hooks.ts" && gone "~/.pi/agent/extensions/superset-hooks.ts"
[ -e "$HOME/.config/amp/plugins/superset-lifecycle.ts" ] && rm -f "$HOME/.config/amp/plugins/superset-lifecycle.ts" && gone "Amp plugin superset-lifecycle.ts"
for f in "$HOME/.config/devin/config.json" "$HOME/.gemini/settings.json" "$HOME/.config/muse/settings.json"; do
    [ -f "$f" ] && grep -q -e SUPERSET -e '\.superset' "$f" || continue
    python3 - "$f" <<'PY' && gone "Superset hooks in $f"
import json, os, sys
path = sys.argv[1]
d = json.load(open(path))
ours = lambda s: isinstance(s, str) and ("SUPERSET" in s or ".superset" in s)
hooks = d.get("hooks")
if isinstance(hooks, dict):
    for event in list(hooks):
        groups = [dict(g, hooks=[h for h in g.get("hooks", []) if not ours(h.get("command"))])
                  for g in hooks[event] if isinstance(g, dict)]
        groups = [g for g in groups if g["hooks"]]
        if groups:
            hooks[event] = groups
        else:
            del hooks[event]
    if not hooks:
        del d["hooks"]
if ours(d.get("managed_hooks_path")):
    d.pop("managed_hooks_path")
    d.pop("managed_hooks_env_vars", None)
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(d, f, indent=2)
    f.write("\n")
os.replace(tmp, path)
PY
done
for d in "$HOME/.superset" "$HOME/Library/Application Support/Superset"; do
    [ -e "$d" ] && rm -rf "$d" && gone "$d"
done
if [ -f "$HOME/Library/Preferences/com.superset.desktop.plist" ]; then
    defaults delete com.superset.desktop >/dev/null 2>&1
    rm -f "$HOME/Library/Preferences/com.superset.desktop.plist" && gone "Superset preferences"
fi

# Orca (Stably's agent IDE), retired 2026-10-20: it needs its desktop GUI. The homelab
# stack is only disabled, so the NUC keeps the server's state (~/.config/orca) for a
# revival; everything Orca wrote into the agents goes. Its Claude Code and Codex hooks are
# purged by DENY in lib/agent_settings.py; its pi/OMP extensions (marked
# @orca-managed-pi-extension), OpenCode status plugins, hook scripts, CLI dispatchers,
# hooks in other agents' configs, and on the Macs the app (zapped) and its tap go here.
if command -v brew >/dev/null 2>&1; then
    if brew list --cask --full-name 2>/dev/null | grep -qx 'stablyai/orca/orca'; then
        brew uninstall --zap --cask stablyai/orca/orca >/dev/null && gone "Orca (brew cask)"
    fi
    brew tap 2>/dev/null | grep -qx 'stablyai/orca' && brew untap stablyai/orca >/dev/null 2>&1 && gone "stablyai/orca tap"
fi
for dir in "$HOME/.pi/agent/extensions" "$HOME/.omp/agent/extensions"; do
    for f in "$dir"/orca-*.ts; do
        [ -f "$f" ] && grep -q '@orca-managed-pi-extension' "$f" && rm -f "$f" && gone "$f"
    done
done
for p in "$HOME/.config/opencode/plugins/orca-opencode-status.js" "$HOME/.config/opencode/plugins/orca-opencode-status-tui" "$HOME/.orca" "$HOME/.local/bin/orca-setup"; do
    [ -e "$p" ] && rm -rf "$p" && gone "$p"
done
for p in "$HOME/.local/bin/orca" "$HOME/.local/bin/orca-ide" /usr/local/bin/orca /usr/local/bin/orca-ide /opt/homebrew/bin/orca; do
    if [ -L "$p" ]; then
        case $(readlink "$p") in
            */Orca/*|*Orca.app*) if rm -f "$p" 2>/dev/null; then gone "$p"; else echo "retired: remove $p by hand" >&2; fi ;;
        esac
    elif [ -f "$p" ] && grep -q -e 'orca-serve-bare-orca-dispatcher' -e 'Orca.app' -e '/opt/Orca/' "$p" 2>/dev/null; then
        if rm -f "$p" 2>/dev/null; then gone "$p"; else echo "retired: remove $p by hand" >&2; fi
    fi
done
for f in "$HOME/.gemini/settings.json" "$HOME/.factory/settings.json" "$HOME/.cursor/hooks.json" "$HOME/.config/devin/config.json"; do
    [ -f "$f" ] && grep -q -e ORCA_AGENT_HOOK_ -e orca-agent-hook-form "$f" || continue
    python3 - "$f" <<'PY' && gone "Orca hooks in $f"
import json, os, sys
path = sys.argv[1]
d = json.load(open(path))
ours = lambda s: isinstance(s, str) and ("ORCA_AGENT_HOOK_" in s or "orca-agent-hook-form" in s)
hooks = d.get("hooks")
if isinstance(hooks, dict):
    for event in list(hooks):
        kept = []
        for g in hooks[event]:
            if isinstance(g, dict) and isinstance(g.get("hooks"), list):
                g = dict(g, hooks=[h for h in g["hooks"] if not ours(h.get("command"))])
                if g["hooks"]:
                    kept.append(g)
            elif not (isinstance(g, dict) and ours(g.get("command"))):
                kept.append(g)
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    if not hooks:
        del d["hooks"]
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(d, f, indent=2)
    f.write("\n")
os.replace(tmp, path)
PY
done
if [ "$(uname)" = Darwin ]; then
    [ -d "$HOME/.config/orca" ] && rm -rf "$HOME/.config/orca" && gone "~/.config/orca"
    rmdir "$HOME/orca/workspaces" "$HOME/orca" 2>/dev/null && gone "~/orca (empty)"
fi

# tmux-agents, retired 2026-10-20: herdr replaced tmux for agents. Its Claude Code and Codex
# hooks are purged by DENY in lib/agent_settings.py; the archive, its compatibility and
# opencode links, pi's Git checkout of it, and the Mac's remote-notification receiver go here.
link="$HOME/.config/opencode/plugins/tmux-agents"
[ -L "$link" ] && rm -f "$link" && gone "$link"
link="$HOME/.local/share/plugins/tmux-agents"
[ -L "$link" ] && rm -f "$link" && gone "$link"
# The archive is chezmoi's copy; a Git checkout there would be local work, so it stays.
d="$HOME/.tmux/plugins/tmux-agents"
[ -d "$d" ] && [ ! -e "$d/.git" ] && rm -rf "$d" && gone "$d"
d="$HOME/.pi/agent/git/github.com/justmytwospence/tmux-agents"
[ -d "$d" ] && rm -rf "$d" && gone "$d"
plist="$HOME/Library/LaunchAgents/com.spencerboucher.claude-notify.plist"
if [ -f "$plist" ]; then
    launchctl bootout "gui/$(id -u)/com.spencerboucher.claude-notify" >/dev/null 2>&1
    rm -f "$plist" "$HOME/.local/state/claude-notify.sock" && gone "claude-notify LaunchAgent"
fi

# Claude Code plugins and marketplaces no longer used. (Linear stays, installed at project
# scope in the projects that use it.)
if command -v claude >/dev/null 2>&1; then
    for plugin in superwhisper@superwhisper; do
        grep -q "\"$plugin\"" "$HOME/.claude/plugins/installed_plugins.json" 2>/dev/null &&
            claude plugin uninstall "$plugin" >/dev/null 2>&1 && gone "Claude plugin $plugin"
    done
    for market in superwhisper beads-marketplace; do
        grep -q "\"$market\"" "$HOME/.claude/plugins/known_marketplaces.json" 2>/dev/null &&
            claude plugin marketplace remove "$market" >/dev/null 2>&1 && gone "Claude marketplace $market"
    done
fi

# ~/.local/bin/worktree, opencode's /worktree front end to it, and the symlinks it kept under herdr's worktree root:
# each harness now creates <repo>/.worktrees checkouts itself (docs/agents.md
# "Worktrees"). Only links go; a real directory there holds checkouts.
[ -e "$HOME/.local/bin/worktree" ] && rm -f "$HOME/.local/bin/worktree" && gone "~/.local/bin/worktree"
[ -e "$HOME/.config/opencode/commands/worktree.md" ] && rm -f "$HOME/.config/opencode/commands/worktree.md" && gone "opencode /worktree"
if [ -d "$HOME/.herdr/worktrees" ]; then
    for link in "$HOME"/.herdr/worktrees/*; do
        [ -L "$link" ] && rm -f "$link" && gone "herdr worktree link ${link##*/}"
    done
fi
{{- if hasPrefix "mac-" .host }}

# Claude Code's native installer, left over from before the claude-code@latest cask;
# the cask comes first on PATH, so the native copy only goes stale.
if [ -x /opt/homebrew/bin/claude ] && [ -L "$HOME/.local/bin/claude" ] &&
    case $(readlink "$HOME/.local/bin/claude") in "$HOME"/.local/share/claude/*) true ;; *) false ;; esac; then
    rm -f "$HOME/.local/bin/claude" && rm -rf "$HOME/.local/share/claude" && gone "native Claude Code install"
fi

# Secure Enclave SSH identity via ssh-keychain.dylib, tried 2026-10-20 and replaced by
# Bitwarden's SSH agent: Apple's Touch ID prompt cannot say what is asking, and every new
# connection asked. The identity itself (sc_auth) is deleted by hand.
plist="$HOME/Library/LaunchAgents/com.justmytwospence.ssh-enclave.plist"
if [ -f "$plist" ]; then
    launchctl bootout "gui/$(id -u)/com.justmytwospence.ssh-enclave" >/dev/null 2>&1
    rm -f "$plist" "$HOME/Library/Logs/ssh-enclave.log" && gone "ssh-enclave LaunchAgent"
fi
[ -e "$HOME/.ssh/config.d/secure-enclave" ] && rm -f "$HOME/.ssh/config.d/secure-enclave" && gone "~/.ssh/config.d/secure-enclave"
{{- end }}

{{- if eq .host "nuc" }}

# herdr-homelab.service: the NUC's herdr was the `homelab` session until 2026-10-13; the
# default session runs under herdr.service now. Disabled and removed, never stopped here:
# stopping a running server ends its panes, so the move itself is done by hand.
unit="$HOME/.config/systemd/user/herdr-homelab.service"
if [ -f "$unit" ]; then
    systemctl --user disable herdr-homelab.service >/dev/null 2>&1
    rm -f "$unit" "$HOME/.config/systemd/user/default.target.wants/herdr-homelab.service"
    systemctl --user daemon-reload
    gone "herdr-homelab.service"
fi

# droidtty: tried 2026-10-13 and dropped for Paseo and herdr-web-ui.
unit="$HOME/.config/systemd/user/droidtty.service"
if [ -f "$unit" ]; then
    systemctl --user disable --now droidtty.service >/dev/null 2>&1
    rm -f "$unit" "$HOME/.config/systemd/user/default.target.wants/droidtty.service"
    systemctl --user daemon-reload
    gone "droidtty.service"
fi
command -v droidtty-cli >/dev/null 2>&1 && npm uninstall -g @droidtty/cli >/dev/null 2>&1 && gone "droidtty-cli"
rm -rf "$HOME/.config/droidtty"

# llm-window-prime, renamed defenestrator on 2026-10-24: its units, scripts and pending
# booking go; its state and optional env file move to the new names, and the new timer
# takes over (the files are already written when this runs).
units="$HOME/.config/systemd/user"
old=0
[ -e "$units/llm-window-prime.timer" ] || [ -L "$units/timers.target.wants/llm-window-prime.timer" ] && old=1
[ "$old" = 1 ] && systemctl --user stop llm-window-prime.timer llm-window-prime-next.timer llm-window-prime.service >/dev/null 2>&1
if [ -d "$HOME/.local/state/llm-window-prime" ] && [ ! -e "$HOME/.local/state/defenestrator" ]; then
    rm -f "$HOME/.local/state/llm-window-prime/next"
    mv "$HOME/.local/state/llm-window-prime" "$HOME/.local/state/defenestrator" && gone "~/.local/state/llm-window-prime (now defenestrator)"
fi
if [ -e "$HOME/.config/llm-window-prime.env" ] && [ ! -e "$HOME/.config/defenestrator.env" ]; then
    mv "$HOME/.config/llm-window-prime.env" "$HOME/.config/defenestrator.env" && gone "~/.config/llm-window-prime.env (now defenestrator.env)"
fi
if [ "$old" = 1 ]; then
    rm -f "$units/llm-window-prime.timer" "$units/llm-window-prime.service" "$units/timers.target.wants/llm-window-prime.timer" \
        "$HOME/.local/bin/llm-window-prime" "$HOME/.local/bin/llm-window-plan"
    systemctl --user daemon-reload
    gone "llm-window-prime"
fi

# The defenestrator moved to a homelab docker stack on 2026-10-29 (justmytwospence/defenestrator,
# docs/agents.md): its timers, units and scripts go. The state in ~/.local/state/defenestrator
# is left alone (the stack's ./data/state was synced from it).
units="$HOME/.config/systemd/user"
if [ -e "$units/defenestrator.timer" ] || [ -L "$units/timers.target.wants/defenestrator.timer" ] || [ -e "$HOME/.local/bin/defenestrator" ]; then
    systemctl --user disable --now defenestrator.timer defenestrator-next.timer >/dev/null 2>&1
    systemctl --user stop defenestrator.service >/dev/null 2>&1
    rm -f "$units/defenestrator.timer" "$units/defenestrator.service" "$units/timers.target.wants/defenestrator.timer" \
        "$HOME/.local/bin/defenestrator" "$HOME/.local/bin/defenestrator-plan"
    systemctl --user daemon-reload
    gone "defenestrator systemd units (now a homelab docker stack)"
fi
{{- end }}

# Chezmoi and the native tools now own plugin/skill deployment. Remove only the
# retired manager commands and manifest, not any installation directories.
for retired in "$HOME/.local/bin/plugins" "$HOME/.local/bin/skills-install" "$HOME/.config/plugins/pins"; do
    if [ -f "$retired" ]; then
        rm -f "$retired"
        gone "$retired"
    fi
done
# The skills CLI no longer owns these global directories. Preserve other
# registrations, but remove these stale entries from its local lock file.
lock="$HOME/.agents/.skill-lock.json"
if [ -f "$lock" ]; then
    python3 - "$lock" <<'PY'
import json, os, sys
path = sys.argv[1]
with open(path) as handle:
    data = json.load(handle)
changed = False
for name in ("find-skills", "tmux", "vercel-cli", "orca-cli", "orchestration"):
    if name in data.get("skills", {}):
        del data["skills"][name]
        changed = True
if changed:
    temporary = path + ".tmp"
    with open(temporary, "w") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    os.replace(temporary, path)
PY
fi
# 2026-10-30: obsolete plan-mode implementation defaults. Live settings win the
# seed_defaults merge, so remove only these exact old strings, not user choices
# (including empty/new list overrides). Keep the map itself and unrelated settings.
python3 -B - "$HOME/.pi/agent/pi-plan-mode.json" <<'PY' || return 1
import json, os, sys
path = sys.argv[1]
try:
    with open(path) as handle:
        data = json.load(handle)
except FileNotFoundError:
    sys.exit(0)
mapping = data.get("implementationModelMap") if isinstance(data, dict) else None
if not isinstance(mapping, dict):
    sys.exit(0)
legacy = {
    "anthropic/claude-fable-5-1": "anthropic/claude-opus-5-5:high",
    "anthropic/claude-opus-5-5": "anthropic/claude-sonnet-5-5:high",
    "openai-codex/gpt-6-astra": "openai-codex/gpt-6.1-terra:high",
    "openai-codex/gpt-6.1-sol": "openai-codex/gpt-6.1-terra:high",
}
changed = False
for model, value in legacy.items():
    if mapping.get(model) == value:
        del mapping[model]
        changed = True
if changed:
    temporary = path + ".tmp"
    with open(temporary, "w") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.chmod(temporary, os.stat(path).st_mode & 0o777)
    os.replace(temporary, path)
    print("retired: legacy plan-mode implementation model defaults")
PY

# Heeler: native uninstall (all running local sessions), marked SSH keys, then
# config/state/helper. Fail apply on errors so chezmoi retries, unlike older
# best-effort entries here. No direct edits to Herdr installations or registry.
python3 {{ joinPath .chezmoi.sourceDir "lib/retire_heeler.py" | quote }} || return 1

# Herdr-owned installs no longer need the unused compatibility links. Keep any
# real directories: those may contain local work from an older installation.
for repo in agentbox Heeler herdr-file-viewer herdr-git-status herdr-agentbox; do
    link="$HOME/.local/share/plugins/$repo"
    if [ -L "$link" ]; then
        case $(readlink "$link") in
            "$HOME"/.config/herdr/plugins/*) rm "$link"; gone "$link" ;;
        esac
    fi
done

# 2026-10-28: herdr-git-status and herdr-undo moved into justmytwospence/herdr-plugins
# (same plugin ids). Herdr will not install a plugin over the same id from another
# source, so the old installs go first; herdr-plugins' converge section installs the new.
if command -v herdr >/dev/null 2>&1; then
    plugins=$(herdr plugin list 2>/dev/null || true)
    # 2026-10-28: hold-done retired for herdr's priority sort plus focus_agent (Alt-1).
    for spec in justmytwospence/herdr-git-status justmytwospence/herdr-undo justmytwospence/herdr-plugins/hold-done; do
        grep -qF "[github:$spec@" <<<"$plugins" &&
            herdr plugin uninstall "$spec" >/dev/null && gone "herdr plugin $spec"
    done
fi
# hold-done's leftover plugin config and the state dir its manual runs used.
for d in "$HOME/.config/herdr/plugins/config/hold-done" "$HOME/.local/state/herdr-hold-done"; do
    [ -d "$d" ] && rm -rf "$d" && gone "$d"
done

# Sphinx (understanding checks on git push), tried twice on the Macs. Its own uninstall
# first: it unsets core.hooksPath only while that still points at its hooks, and removes
# its Git hooks and Pi extension (and the Claude/Codex/OpenCode entries of the first try),
# keeping anything edited. Then the package, its state, and the git wrapper that sent Pi's
# pushes to its Pi dialogs.
if command -v sphinx >/dev/null 2>&1; then
    (cd / && sphinx uninstall) && gone "sphinx integrations"
    npm uninstall -g sphinx-understand >/dev/null 2>&1 && gone "sphinx-understand (npm)"
fi
[ -d "$HOME/.config/sphinx" ] && ! command -v sphinx >/dev/null 2>&1 && rm -rf "$HOME/.config/sphinx" && gone "~/.config/sphinx"
[ -d "$HOME/.local/libexec/sphinx-pi" ] && rm -rf "$HOME/.local/libexec/sphinx-pi" && gone "~/.local/libexec/sphinx-pi"
{{- if has .host .agentDirs.hosts }}

# The dotfiles checkout moved from ~/dotfiles to ~/Projects/dotfiles on 2026-10-22. The
# per-project grants and Codex trust only ever gain entries, so the old path's stay behind.
if [ ! -e "$HOME/dotfiles" ] && grep -qsF -e "$HOME/dotfiles" -e "~/dotfiles/" "$HOME/.codex/config.toml" "$HOME"/Projects/*/.claude/settings.local.json "$HOME"/Projects/*/.opencode/opencode.jsonc; then
    python3 -B - {{ joinPath .chezmoi.sourceDir "lib" | quote }} "$HOME/dotfiles" <<'PY' || return 1
import sys
sys.path.insert(0, sys.argv[1])
import agent_dirs
for path in agent_dirs.drop_root(sys.argv[2]):
    print("retired: ~/dotfiles grants in %s" % path)
PY
fi
{{- end }}
{{- if has .host (list "nuc" "agentbox-box") }}

# OpenCode 1 (opencode-ai) owns the same `opencode` binary as OpenCode 2 (@opencode/cli).
if [ -d "$(npm root -g 2>/dev/null)/opencode-ai" ]; then
    npm uninstall -g opencode-ai >/dev/null && gone "opencode-ai (npm)"
fi
# 2026-10-30: the global CLIs moved from npm to pnpm (linux.json "pnpm"), whose exact-version
# cooldown exemptions npm lacks. linux-tools reinstalls each one with pnpm after this, into
# the same ~/.local/bin.
npm_root=$(npm root -g 2>/dev/null || true)
for pkg in pi-acp @openai/codex @opencode/cli @getpaseo/cli vercel; do
    [ -n "$npm_root" ] && [ -d "$npm_root/$pkg" ] && npm uninstall -g "$pkg" >/dev/null 2>&1 && gone "$pkg (npm, now pnpm)"
done
hash -r
# Stand-ins from the old box bootstrap; the release binaries now provide these names.
for b in bat fd; do
    [[ -L $HOME/.local/bin/$b && $(readlink "$HOME/.local/bin/$b") == /usr/bin/* ]] && rm -f "$HOME/.local/bin/$b" && gone "~/.local/bin/$b"
done
{{- end }}
{{- if eq .host "agentbox-box" }}

# 2026-10-26: no Slack in a box; sessions stay on the Macs and the NUC. AgentBox also seeds
# the Mac's ~/.agents skills into every box, so the skill is removed here on each start.
for p in .local/bin/slackcli .local/bin/slack-agent .agents/skills/slackcli; do
    [ -e "$HOME/$p" ] && rm -rf "${HOME:?}/$p" && gone "~/$p"
done
{{- end }}
return 0
}
run converge_retired
