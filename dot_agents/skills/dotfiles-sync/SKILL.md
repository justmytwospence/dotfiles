---
name: dotfiles-sync
description: "Propagate dotfiles changes to the other machines. Use whenever you commit, push, or chezmoi apply in ~/dotfiles -- after the local commit/push/apply, run chezmoi update on spencer@nuc so every machine matches. Trigger on 'commit and push', 'chezmoi apply', 'apply the dotfiles', or any change to ~/dotfiles that lands on main. Do not use for repos other than ~/dotfiles."
---

# Dotfiles sync

`~/dotfiles` is the chezmoi source directory on the Macs and the NUC.
chezmoi writes real files into `$HOME`, so a commit on the Mac reaches another host
only when that host runs `chezmoi update` (git pull, then apply; the plugin and skill
syncs run when their inputs changed). AgentBox boxes (host `agentbox-box`) are not
synced: each re-applies `origin/main` when it starts (docs/agentbox.md).

| | Mac (primary) | NUC |
|---|---|---|
| Host | local | `spencer@nuc` (Debian, x86_64) |
| chezmoi host | `mac-pro` | `nuc` |
| chezmoi | Homebrew | `~/.local/bin`, v2.73.0 |

There are two Macs: the Pro (`mac-pro`, primary) and the Air (`mac-air`, travel).
Each is synced by hand on that machine, never from another host. After a Brewfile
change, `chezmoi update` on the other Mac runs `brew bundle install`; tell the user
to review `brew bundle cleanup --global` there.

## Sequence

Do the local half first, then the remote halves. Never push from another host.

```sh
# Mac
cd ~/dotfiles
git add <only the files for this change>   # atomic; leave unrelated drift alone
git commit
git push origin main
chezmoi apply
```

```sh
# NUC (its herdr server is the named session `homelab`)
ssh -o BatchMode=yes -o ConnectTimeout=10 spencer@nuc \
  'HERDR_SESSION=homelab ~/.local/bin/chezmoi update --no-tty'
```


Then verify the change landed: `git -C ~/dotfiles log -1 --oneline` and
`chezmoi verify` (exit 0) on each host, plus a `grep` of the changed file at its
target path (`~/.zshrc`, not `~/dotfiles/dot_zshrc.tmpl`).

## When apply stops on a changed file

chezmoi refuses to overwrite a target that changed since it last wrote it (a
program or a person edited the copy in `$HOME`) and, without a terminal, exits with
an error naming the file. Do not `--force` it blind. Show the difference and hand
the decision to the user:

```sh
ssh <host> '~/.local/bin/chezmoi diff <target>'
```

- **Repo wins:** `chezmoi apply --force <target>` on that host.
- **Host wins:** the change belongs in the repo: make it in `~/dotfiles` on the Mac
  and commit, or, if it is genuinely host-specific, a template branch or
  `~/.zshrc.local` / `~/.zshenv.local` / `~/.gitconfig.local`.

The files programs rewrite (`~/.claude/settings.json`, `~/.codex/hooks.json`,
`~/.pi/agent/settings.json`, `~/.claude.json`, `~/.codex/config.toml`) never stop
an apply: they are `modify_` merges, and the program's
own keys survive. A setting someone wants on every host goes in the matching
`*.managed.json`.

## Plugins

Dotfiles vendors no plugin code. pi packages are pinned in
`private_dot_pi/private_agent/settings.managed.json`
(`git:github.com/justmytwospence/<name>@<commit>`), everything else in
`dot_config/plugins/pins.tmpl` (`<kind> <owner>/<repo> <commit>`, host lines as
template branches). `chezmoi update` runs `plugins sync` when either changes; check
with `plugins list` (every row "at pin"). A plugin change reaches dotfiles as a pin
bump: push the plugin, then `plugins pin <name>` on the Mac and commit the two
files.

- On the NUC, herdr commands (and `plugins sync`) need `HERDR_SESSION=homelab`.
- Installing a herdr plugin does not run its startup hook: restart herdr or run the
  plugin's reapply action (`herdr plugin action invoke <id>.<action>`).
- Running pi sessions pick up a bumped package with `/reload`; tmux with
  `tmux source ~/.tmux.conf`. herdr-agentbox on the NUC: `agentbox-space daemon --ensure`
  after killing the running daemon (its startup hook only runs when herdr starts).
- Push the plugin before dotfiles, or the other hosts cannot fetch the commit;
  `plugins pin` refuses unpushed commits.
- Never edit an installed copy over SSH; report a plugin that is off its pin.

## Pull failures

`chezmoi update` pulls with `--rebase --autostash`. If the rebase conflicts (only
possible if someone committed on that host), the checkout is left mid-rebase. Do not
resolve it blind over SSH:

```sh
ssh <host> 'cd ~/dotfiles && git rebase --abort 2>/dev/null; git status --short'
```

Report the state and stop. If a host is unreachable, say so and report the sync as
incomplete. Never let a failed SSH read as success.

## SSH noise

The connection prints a post-quantum key-exchange warning and `remote port forwarding
failed` lines on stderr. Both are expected:

```sh
... 2>&1 | grep -v '^\*\*\|^Warning: remote'
```
