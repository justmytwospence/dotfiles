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

In herdr: every box has its own space under the NUC machine in the sidebar (below),
with its agent's live state. On the Mac, `prefix a` also opens AgentBox's own read-only
list of boxes, and `prefix shift a` makes a new box in the current project.

A `git push` in a box goes to the hub, which pushes with its own GitHub token. A push to
the box's `agentbox/*` branch is approved automatically; anything else asks (ntfy, then
the web UI or `agentbox hub approvals`).

## Every box in herdr (herdr-agentbox)

The NUC's herdr server (`homelab` session, which the Macs show as the machine `NUC`)
runs [herdr-agentbox](https://github.com/justmytwospence/herdr-agentbox), pinned for
host `nuc` in `.config/plugins/pins`. It keeps one space per box the hub owns, NUC or
Daytona, named after the box:

- **Running:** the pane is the agent (`agentbox <agent> attach`), with its state in the
  sidebar.
- **Paused:** Enter resumes it. A box resumed from the web UI or the phone attaches on
  its own, and an idle pause drops the pane back to the paused screen.
- **Detached** (`Ctrl-a d`): Enter reattaches, `s` opens a shell in the box, and `q`
  leaves a plain shell (`agentbox-space box` there comes back).
- **New boxes:** opening a new space on the NUC asks for repo, agent and NUC or Daytona,
  then creates the box. Esc keeps a plain shell.
- **Destroyed boxes:** their spaces close.
- **Actions** (herdr's action menu): pause, resume or destroy (twice) the focused box;
  sync; status. `agentbox-space status` on the NUC lists boxes and their spaces.

What it needs on the NUC, set up by hand once (not chezmoi: nothing installs system-wide
there):

```sh
# the CLI, at the hub's version, with its native pty module (without it, attach reports
# no agent state): npm on the NUC is 10.x, so no --allow-scripts needed there
npm install -g @madarco/agentbox@<version>
# the hub: the same two values as ~/homelab/agentbox/.env, then
agentbox hub set-url https://agentbox.spencerboucher.com
# its engine is this machine, reached over ssh like any docker engine: a localhost-only
# key (~/.ssh/agentbox_local, `Host agentbox-local` in ~/.ssh/config)
agentbox remote-docker add hub agentbox-local --no-share --no-bake
# Daytona boxes: attaching talks to Daytona directly, so this CLI needs the key the hub
# holds (DAYTONA_API_KEY in ~/homelab/agentbox/data/secrets.env), in ~/.agentbox/secrets.env
# skip the first-run wizard
echo '{"version":1,"completedAt":"2026-10-08T00:00:00.000Z","provider":"remote-docker"}' > ~/.agentbox/setup-complete.json
```

The pty module on the Mac: npm skips it because it declares Node <25 (the Mac runs 26),
so a plain `npm -g install` leaves `agentbox attach` without the footer, approvals and
herdr state. Until AgentBox ships a newer one, install it beside the CLI after every
upgrade:

```sh
d=$(mktemp -d) && cd "$d" && npm init -y >/dev/null \
  && python3 -c "import json;p=json.load(open('package.json'));p['allowScripts']={'@homebridge/node-pty-prebuilt-multiarch':True};json.dump(p,open('package.json','w'))" \
  && npm install --no-fund --no-audit '@homebridge/node-pty-prebuilt-multiarch@^0.13.1' \
  && cp -R node_modules/@homebridge node_modules/node-addon-api "$(npm root -g)/@madarco/agentbox/node_modules/"
```

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
      # From GitHub, not get.chezmoi.io: Daytona sandboxes reach only an allowlist (github is on it)
      test -x ~/.local/bin/chezmoi || { mkdir -p ~/.local/bin && curl -fsSL "https://github.com/twpayne/chezmoi/releases/download/v2.73.0/chezmoi_2.73.0_linux_$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/').tar.gz" | tar xz -C ~/.local/bin chezmoi; }
      ~/.local/bin/chezmoi init --source ~/dotfiles --apply --force --no-tty \
          --promptChoice host=agentbox-box --promptString extras=
```

The supervisor runs it as `vscode` on every box start, beside the agent rather than
before it. The first run installs the tools (a few minutes); later starts only re-apply
the files (seconds). The box's dotfiles checkout is disposable, so it is reset to
`origin/main` each time. A repo without the task still gets
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
   agentbox config set --global box.sizeDaytona 4-8-10   # the Daytona plan caps disk at 10 GB
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

   Two traps, both from the login containers writing only to Docker volumes:
   - Codex, pi and OpenCode keep the new login in their `agentbox-<agent>-config`
     volume only; `hub credentials push` reads `~/.agentbox/<agent>-credentials.json`.
     Copy the volume's `auth.json` there before pushing, or the push falls back to the
     Mac's own login.
   - `agentbox pi login` first copies the Mac's `~/.pi/agent` (logins included) into its
     volume, so a provider you did not sign in to again there is the Mac's live session.
     Push only the providers you signed in to; boxes refreshing the Mac's session log
     the Mac out.

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
