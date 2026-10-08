# AgentBox

[AgentBox](https://github.com/madarco/agentbox) runs one coding agent (Claude Code,
Codex, pi, OpenCode) per task in a "box". Its hub runs on the NUC as a control box
(`~/homelab/agentbox`, whose README is the server side), so boxes keep running and can
be started from the phone while the Mac is off.

- **Boxes:** `docker:hub`, a container on the NUC's engine (the default, free, paused
  after 30 min of agent idle), or `--provider daytona` (billed while running, archived
  after 25 min idle).
- **Web UI:** `https://agentbox.spencerboucher.com` over WireGuard (Authelia, then the
  hub's own login, which is in Bitwarden as "AgentBox hub"). From there you can create a
  box from a prompt, watch it, answer approvals, pause, resume or destroy it, and open a
  Daytona box's screen. Nothing on the phone gives a terminal or a chat into a running
  agent; that is `agentbox attach` from the Mac.
- **Notifications:** ntfy topic `agentbox`, for approvals, an agent waiting, asking or
  failing, a box ready or failed, and idle pauses.
- **Logins:** subscriptions only, each a separate box-side session made with
  `agentbox <agent> login`, so a box refreshing a token never rotates the Mac's own.
  The hub shares refreshed tokens across boxes.

## Daily use

```sh
agentbox claude                         # in a repo: a NUC box, attached in a herdr tab
agentbox codex --provider daytona       # a cloud box
agentbox pi -n fix-login -i "..."       # detached: runs with nothing on the Mac
agentbox attach fix-login               # reconnect (resumes a paused box)
agentbox ls -g                          # every box the hub owns
agentbox shell fix-login                # a zsh in the box
```

In herdr: `prefix a` opens the boxes overlay, `prefix shift a` makes a new box in the
current project. Box agents show their state on the pane like local ones.

A `git push` in a box goes to the hub, which pushes with its own GitHub token. A push to
the box's `agentbox/*` branch is approved automatically; anything else asks (ntfy, then
the web UI or `agentbox hub approvals`).

## Dotfiles in a box

AgentBox seeds every box from the Mac by itself: `~/.claude`, `~/.codex`, `~/.pi/agent`
(settings and packages; not sessions, `bin`, `models-store.json` or `trust.json`), the
OpenCode config and the `~/.agents` skills, plus the agent logins and git identity.

The rest (zsh, tmux, git, vim, the CLI tools, plugins) comes from chezmoi as host
`agentbox-box`, run by a task in the repo's `agentbox.yaml`:

```yaml
# yaml-language-server: $schema=https://agent-box.sh/schema/agentbox.schema.json
tasks:
  # The dotfiles (~/dotfiles/docs/agentbox.md): chezmoi as host agentbox-box. /usr/bin/git
  # because `git` in a box is AgentBox's shim, which relays clones to the hub and refuses
  # -q; the dotfiles repo is public.
  dotfiles:
    command: |
      set -e
      test -d ~/dotfiles || /usr/bin/git clone -q https://github.com/justmytwospence/dotfiles.git ~/dotfiles
      /usr/bin/git -C ~/dotfiles fetch -q origin
      /usr/bin/git -C ~/dotfiles reset -q --hard origin/main
      /usr/bin/git -C ~/dotfiles clean -ffdq
      test -x ~/.local/bin/chezmoi || sh -c "$(curl -fsLS get.chezmoi.io)" -- -b ~/.local/bin -t v2.73.0
      ~/.local/bin/chezmoi init --source ~/dotfiles --apply --force --no-tty \
          --promptChoice host=agentbox-box --promptString extras=
```

The supervisor runs it as `vscode` on every box start, beside the agent rather than
before it. The first run installs the tools (a few minutes); later starts only re-apply
the files (seconds). The box's dotfiles checkout is disposable, so it is reset to
`origin/main` each time, as on the machine0 spokes. A repo without the task still gets
the agent config, skills and logins; it lacks only the shell, tmux and git config.

What `agentbox-box` does differently from the other Linux hosts:

- node is the image's (NodeSource), not nvm; no harness installs (the box has its agent)
  and no memory guard (the container is capped by AgentBox).
- Setup scripts use `/usr/bin/git` for their public clones (plugins, skills, vim plugins);
  the agent keeps the shim (`.chezmoitemplates/script-path.sh`).
- `.gitconfig` cancels the https-to-ssh rewrite and sets no credential helper: the shim
  hands every network git operation to the hub.
- No herdr config; the Claude hook herdr would own is a stand-in.

## Setup (once, on the Mac)

The hub side is `~/homelab/agentbox/README.md`. Then, with Docker Desktop running:

1. CLI: `npm -g install @madarco/agentbox@<version>`, the version the hub runs
   (`AGENTBOX_SPEC` in the homelab compose file). Then `agentbox install` (the wizard;
   skip the local docker box) and `agentbox doctor`.
2. Hub credentials: `~/.agentbox/control-plane/control-plane.env` (0600) holds
   `AGENTBOX_RELAY_ADMIN_TOKEN` and `AGENTBOX_HUB_API_KEY`, the same two values as the
   hub's `.env`. Written by hand rather than by `agentbox hub setup --deploy none`, which
   would also copy the Mac's `gh` token; the hub pushes with its own fine-grained PAT.
3. Point the CLI at the hub, and register the NUC's engine here under the same name so
   `attach`/`shell` reach NUC boxes over the `nuc` ssh alias:

   ```sh
   agentbox hub set-url https://agentbox.spencerboucher.com   # also makes docker:hub the default
   agentbox remote-docker add hub spencer@nuc --no-share --no-bake
   agentbox daytona login                                     # stored here and on the hub
   agentbox config set --global box.sizeRemoteDocker 4-8
   agentbox config set --global box.sizeDaytona 4-8-20
   agentbox config set --global box.daytonaRegion us
   agentbox hub status                                        # remote (reachable), build <version>
   ```

4. Logins, each its own session (never the Mac's live tokens), then hand them to the hub:

   ```sh
   agentbox claude login      # Claude Max
   agentbox codex login       # ChatGPT, device auth
   agentbox pi login          # pi's TUI: /login Anthropic (the pi-anthropic-auth package),
                              # then openai-codex, then /exit
   agentbox opencode login    # Anthropic through its auth plugin; OpenAI if offered,
                              # else create OpenCode boxes with --model-auth codex
   agentbox hub credentials push
   ```

5. Bases, built on the hub: `agentbox prepare --provider docker:hub` and
   `agentbox prepare --provider daytona`.
6. herdr: the plugin is pinned for the Macs in `.config/plugins/pins`; `plugins sync`
   installs it and its build step writes the key block `.config/herdr/config.toml`
   already has.

pi and OpenCode reach Claude through the auth plugins, which Anthropic bills as extra
usage on a subscription since 2026-04-04 unless the request looks like Claude Code's;
`anthropic-billing-guard` logs any overage to `~/.local/state/anthropic-extra-usage.log`
in the box, which should stay empty.

## Upgrades

The Mac CLI and the hub move together: `agentbox self-update --skip-hub` here (npm's
cooldown applies), then bump `AGENTBOX_SPEC` on the NUC (`~/homelab/agentbox/README.md`
"Version bumps"), and the herdr pin to the release tag's commit.
