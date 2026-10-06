# From GNU Stow to chezmoi

Until October 2026 this repo was eleven stow packages (`shell`, `osx`, `nuc`, `exe`,
`m0`, `paseo-machine0`, `emacs`, `jupyter`, `desktop`, `i3`, `gnome`) linked into
`$HOME`. The tag `pre-chezmoi` is the last stow layout; it stays.

## Moving a host

Run `stow -D` **before** pulling: after the pull the package directories it needs
are gone. The packages each host had stowed:

| host | packages | chezmoi host |
|---|---|---|
| desk Mac | `shell osx desktop emacs` | `mac-pro` (extras `emacs`) |
| travel Mac | `shell osx` (plus whatever else is stowed there) | `mac-air` |
| NUC | `shell nuc` | `nuc` |
| exe VM | `shell exe` | `exe` |
| m0 hub, spokes | `shell m0` | `m0-hub`, `m0-spoke` |
| Paseo hub, spokes | `shell paseo-machine0` | `paseo-hub`, `paseo-spoke` |

```sh
cd ~/dotfiles                     # still on the stow layout
# A program's own additions to a modify_ target (pi's deviceId, hooks Orca or
# agent-deck added to ~/.claude/settings.json) live only in the repo file behind
# the link; keep them as real files and chezmoi merges into them:
for f in .claude/settings.json .codex/hooks.json .pi/agent/settings.json; do
    cp "shell/$f" ~/"$f.keep"; done
stow -D <packages>                # removes only stow's own links
for f in .claude/settings.json .codex/hooks.json .pi/agent/settings.json; do
    mv ~/"$f.keep" ~/"$f"; done
git checkout -- . && git pull     # drop the uncommitted program writes, take main
# install chezmoi: brew install chezmoi (Mac), or
#   sh -c "$(curl -fsLS get.chezmoi.io)" -- -b ~/.local/bin -t v2.73.0
chezmoi init --source ~/dotfiles --apply --promptChoice host=<host> --promptString extras=<extras>
scp mac:.config/chezmoi/key.txt ~/.config/chezmoi/key.txt && chezmoi apply   # Macs, NUC, exe
chezmoi apply          # a second pass folds the herdr installer's hook entries in
chezmoi verify && chezmoi doctor
```

On the exe VM and the fleet hosts the first apply also deletes the
`~/.gitconfig.local`, `~/.zshenv.local` and `~/.zshrc.local` a bootstrap script
wrote (marked "written by bootstrap-"): their contents are template branches now.
Hand-written ones stay. Remove the API key lines from `~/.zshrc.local` once the age
key is in place. The fleets: update the plugin's provision and sync commands
(herdr-machine0 reads `dot_config/herdr-machine0/config.json`; paseo-machine0 has
them in `paseo_machine0/lifecycle.py`), then rebuild the golden image with
`--fresh` and prove it on one scratch spoke.

Done on 2026-10-06 for the desk Mac, the NUC, the exe VM and both hubs; machine0
spokes migrate themselves on their next sync or wake (the fleet sync commands
unstow a pre-chezmoi spoke first). Left: the travel Mac, by hand as above (stow is
still installed there; `brew bundle cleanup` removes it afterwards).

## Rolling back

```sh
chezmoi managed --include=files,symlinks | sed "s|^|$HOME/|" | xargs rm -f
git -C ~/dotfiles checkout pre-chezmoi
stow -d ~/dotfiles -t ~ <packages>
```

Rolling back needs stow again (`brew install stow`). Never `chezmoi purge`: it deletes the source directory, `~/dotfiles`.
