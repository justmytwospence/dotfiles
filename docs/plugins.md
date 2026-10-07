# Plugins

Every plugin maintained here (the pi extensions, the herdr plugins, tmux-agents,
anthropic-billing-guard, the Claude Code mods, paseo-machine0) lives in its own
public repo and is developed in `~/Projects/<plugin>`. Repos are named
`<host>-<feature>` (`pi-`, `herdr-`), or by feature when they serve several
harnesses; the repo name and the `~/Projects` directory match. On a new Mac, clone
each repo into `~/Projects` (with the `upstream` remote for the pi-plan-mode fork).
The pi extensions typecheck and test with `npm ci && npm run check`.

## Pins

Dotfiles vendors no plugin code: it holds the commit each plugin is pinned to, and
each host program installs the plugin itself. `plugins` (`~/.local/bin/plugins`)
reads the pins and makes every install match them.

- **pi extensions** are git packages in
  `private_dot_pi/private_agent/settings.managed.json`, e.g.
  `git:github.com/justmytwospence/pi-tool-gate@<commit>`. pi clones each into
  `~/.pi/agent/git/github.com/<owner>/<plugin>` the first time it starts but does
  not move an existing clone when the pin changes; `plugins sync` does.
- **opencode plugins** are git specs in `dot_config/opencode/opencode.jsonc.tmpl`'s
  `plugin` list, `"<name>@github:justmytwospence/<plugin>#<commit>"` (a plugin with a
  TUI half is listed in `tui.jsonc.tmpl` too, at the same commit). opencode
  installs each pin into `~/.cache/opencode/packages/` at startup (no build step;
  the npm cooldown does not apply to git), so `plugins sync` has nothing to do for
  them. `plugins try` prints an `OPENCODE_CONFIG` that loads the checkout as
  `<name>@file:<path>`, which replaces the pin (opencode keeps one plugin per
  package name).
- **everything else** is one line in `~/.config/plugins/pins`, rendered from
  `dot_config/plugins/pins.tmpl`, whose host-specific lines are template branches
  (herdr-machine0 on the m0 hosts, paseo-machine0 on the Paseo hosts, Heeler where
  a herdr server runs). A line is `<kind> <owner>/<repo>[/<subdir>] <commit>`:
  - `herdr`: `herdr plugin install <owner>/<repo> --ref <commit>`, which runs the
    plugin's build step and registers it. On a host without herdr, a plain
    checkout, so hooks that call into the plugin still work.
  - `tmux`: a checkout under `~/.tmux/plugins/`, where `.tmux.conf` lists it as a
    TPM `@plugin`.
  - `git`: a plain checkout.

  Each is reachable at `~/.local/share/plugins/<repo>`; hooks, LaunchAgents, the
  opencode plugin links and the `spoke`/`paseo-machine0` links use that path.

`chezmoi apply` runs `plugins sync` whenever the rendered pins or the managed pi
settings change (`.chezmoiscripts/run_onchange_after_40-plugins.sh.tmpl`).

```sh
plugins list              # every pin on this host and what is checked out
plugins sync              # install or move every plugin to its pin
cd ~/Projects/<plugin>    # edit, test, commit here
plugins try <plugin>      # check this commit out in every installed copy (Mac), then
                          # /reload pi, `tmux source ~/.tmux.conf`, or herdr's reapply action
git push                  # publish the plugin first: other hosts fetch the pinned commit
plugins pin <plugin>      # pin it in pins.tmpl, settings.managed.json or
                          # opencode.jsonc.tmpl, tui.jsonc.tmpl (refuses unpushed commits),
                          # chezmoi apply, sync
cd ~/dotfiles && git commit -am "chore(plugins): bump <plugin>" && git push
```

Installing a herdr plugin does not run its startup hook: after a bump run its
reapply action, if it has one, or restart herdr. Third-party herdr plugins can be
pinned the same way (Heeler is); the marketplace is public repos tagged
`herdr-plugin`.

## The plugins

pi extensions (pinned in `settings.managed.json`; `/reload` after a bump):

- [pi-status-footer](https://github.com/justmytwospence/pi-status-footer): the footer, with model, context, cost and plan limits (`/status`).
- [pi-rewind](https://github.com/justmytwospence/pi-rewind): restores files alongside `/tree` and `/fork`.
- [pi-clear-screen](https://github.com/justmytwospence/pi-clear-screen): `ctrl+l` clears the fullscreen transcript (model selector moved to `alt+m` in `keybindings.json`).
- [pi-select-nav](https://github.com/justmytwospence/pi-select-nav): `ctrl+j`/`ctrl+k` (and `j`/`k`) in every picker.
- [pi-herdr-scrollbar-width](https://github.com/justmytwospence/pi-herdr-scrollbar-width): no wrapped exit transcript in herdr panes.
- [anthropic-billing-guard](https://github.com/justmytwospence/anthropic-billing-guard): warns when a subscription request bills to extra usage (pi, and opencode through a link); see [agents.md](agents.md).
- [pi-brokered-auth](https://github.com/justmytwospence/pi-brokered-auth): OAuth credentials from a file a hub keeps fresh; used on the Paseo fleet.
- [pi-subagents](https://github.com/justmytwospence/pi-subagents): the `subagent` tool (single, parallel, chain; Jev picks agent, tier and effort).
- [pi-ask-user-question](https://github.com/justmytwospence/pi-ask-user-question): the `ask_user_question` tool (Claude Code-style dialog, reports blocked to herdr).
- [pi-plan-mode](https://github.com/justmytwospence/pi-plan-mode): `/plan`; see [agents.md](agents.md#planning).
- Jev plugins, each calling TypeSafe's Jev through pi's classifier models with `TYPESAFE_API_KEY`:
  [pi-tool-gate](https://github.com/justmytwospence/pi-tool-gate) (auto-approves tool calls),
  [pi-lean-context](https://github.com/justmytwospence/pi-lean-context) (trims tool output, `/compact-jev`),
  [pi-auto-effort](https://github.com/justmytwospence/pi-auto-effort) (thinking level per message),
  [pi-copy](https://github.com/justmytwospence/pi-copy) (`/yank`).
- [pi-marimo](https://github.com/justmytwospence/pi-marimo): follows the live marimo notebook open under the cwd: what is running in the footer (its own row in pi-status-footer), the notebook's current state appended to each model request and never stored (`/marimo`).
- `~/.pi/agent/extensions/worktree.ts` and `mtplx-session.ts` stay in this repo: a
  front end to `~/.local/bin/worktree`, and request tagging for the local MTPLX server.

opencode plugins (git pins in `opencode.jsonc.tmpl`), ports of the pi plugins. The Jev
ones call Jev over its HTTP API with `TYPESAFE_API_KEY` and take options as the
second element of their `plugin` entry (`npm run check` in the checkout):

- [opencode-auto-effort](https://github.com/justmytwospence/opencode-auto-effort): the variant per prompt for the `build` agent.
- [opencode-lean-context](https://github.com/justmytwospence/opencode-lean-context): Jev trims large tool output in `tool.execute.after`.
- [opencode-tool-gate](https://github.com/justmytwospence/opencode-tool-gate): read-only calls run, dangerous ones and confident Jev holds are pushed back; project rules in `.opencode/tool-gate-rules.md`.
- [opencode-marimo](https://github.com/justmytwospence/opencode-marimo): the port of pi-marimo. Its TUI half (the status beside the prompt) is pinned in `tui.jsonc.tmpl` at the same commit; `plugins pin` bumps both.

Others (pinned in `pins.tmpl`):

- [tmux-agents](https://github.com/justmytwospence/tmux-agents) (`tmux`, every host): agent state on tmux window tabs and notifications outside herdr; Claude Code and Codex call it from their hooks, pi loads it as a package, opencode through a link.
- [claude-auto-effort](https://github.com/justmytwospence/claude-auto-effort), [claude-marimo](https://github.com/justmytwospence/claude-marimo) (the port of pi-marimo) and Anthropic's [token-weather](https://github.com/anthropics/claude-code-playground/tree/main/claude-code/mods/token-weather) (`git`, every host): Claude Code mods, loaded through `CLAUDE_CODE_PLUGIN_DIRS` in `.zshenv`. token-weather is third-party; bump it by hand.
- [herdr-machine0](https://github.com/justmytwospence/herdr-machine0) (`herdr`, m0 hosts): the hub's Spokes plugin and the `spoke` CLI; see [machine0-herdr.md](machine0-herdr.md).
- [paseo-machine0](https://github.com/justmytwospence/paseo-machine0) (`git`, Paseo hosts): the CLI, hubd and the Spokes Paseo plugin; see [machine0-paseo.md](machine0-paseo.md).
- [Heeler](https://github.com/ZingerLittleBee/Heeler) (`herdr`, hosts running a herdr server): the Heeler iOS app's host plugin; see [phone-access.md](phone-access.md).

Built into Claude Code and enabled in `settings.managed.json`:
`cc-plugin-you-should-know`; `cc-plugin-agents-md` (on by default) loads a
project's `AGENTS.md` when it has no `CLAUDE.md`.
