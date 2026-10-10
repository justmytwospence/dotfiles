# Machine synchronization

Use after a dotfiles commit, push, or apply. Local apply only changes this machine; NUC `update` pulls published source and then applies it. Never imply an unpushed local edit reached another host.

## Sequence

This sequence is for the configured `~/dotfiles` checkout on branch `main`: verify source path and branch first. If working elsewhere, commit in that checkout and obtain authorization to merge into main before publishing/applying; never stage another checkout's work or push an unrelated main branch. `plugins pin` likewise edits and applies the configured source directly.

When commit/push is authorized, stage only this logical change; preserve unrelated drift:

```sh
git -C ~/dotfiles add <changed-paths>
git -C ~/dotfiles commit -m "<conventional commit>"
git -C ~/dotfiles push origin main
chezmoi apply
ssh -o BatchMode=yes -o ConnectTimeout=10 spencer@nuc \
  'HERDR_SESSION=homelab ~/.local/bin/chezmoi update --no-tty'
```

Run the commands separately or with success-gated chaining: do not hide an error behind a pipe or continue after a failed push/apply. Never push from another host. If only local apply is authorized, report that propagation of uncommitted/unpushed source remains pending; do not invent permission to publish it.

Verify the commit on both hosts with `git -C ~/dotfiles log -1 --oneline`. Check `chezmoi verify --exclude scripts` (or scoped changed targets), inspect residual `chezmoi status`, and check the actual deployed files/programs. Always-run scripts remain pending; classify drift rather than treating any nonzero exit as success.

The NUC is Debian, host `nuc`, using `~/.local/bin/chezmoi`; its herdr server is session `homelab`, required for herdr/plugin operations. No system-wide package install runs there: a Mac Brewfile change is not a NUC installation.

Other Mac (`mac-pro` or `mac-air`): user runs `chezmoi update` locally, never remote-managed from another host. After Brewfile changes remind them to review `brew bundle cleanup --global`.

AgentBox boxes (`agentbox-box`) are not synced remotely; each reapplies `origin/main` on startup through its repository's `agentbox.yaml` task. See `docs/agentbox.md`.

## Conflicts and failures

`chezmoi update` normally runs `git pull --autostash --rebase` then apply. An unavailable host, failed pull, script error, or unresolved drift means synchronization is incomplete.

If apply stops on changed destination contents, inspect `chezmoi diff <target>` on that host. Never force blindly. User-approved repo-wins permits scoped `apply --force <target>`; host-wins means moving the change into shared source, a host branch, or a permitted local override.

If a remote rebase conflicts, do not resolve or discard the host's work blindly. Abort the rebase if one is in progress, inspect status, report and stop:

```sh
ssh spencer@nuc 'cd ~/dotfiles && git rebase --abort && git status --short'
```

Post-quantum key-exchange and remote-port-forwarding warnings are expected SSH noise, not evidence the command failed or succeeded. Preserve the actual SSH exit status when filtering output.

## Plugins and reloads

Publish the plugin commit first, then `plugins pin <name>` locally (refuses unpushed commits), and commit the changed dotfiles pins. Follow `docs/plugins.md` for locations and testing; never edit installed copies over SSH.

After sync, `plugins list` should report each plugin at its pin. Reload running pi with `/reload`, tmux with `tmux source ~/.tmux.conf`. Installing a herdr plugin does not run its startup hook: invoke its documented reapply action or restart herdr. For herdr-agentbox on the NUC, stop the old daemon then `agentbox-space daemon --ensure` as documented. Report off-pin plugins or failed reloads rather than silently accepting them.
