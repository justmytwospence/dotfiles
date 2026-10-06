# exe.dev

[exe.dev](https://exe.dev) sells Linux VMs managed over SSH. One is kept beside
the Mac and the NUC as a disposable sandbox where an agent can work without
touching either real machine (chezmoi host `exe`). The plan's vCPU and RAM are one
pool shared by all your VMs.

`ssh exe.dev <command>` is the lobby (VM lifecycle, integrations, billing; no
shell), `ssh <vm>.exe.xyz` the VM itself. `~/.ssh/config` pins the key for both and
gives the VMs the same reverse-forward pair as the NUC, so Claude Code there can
reach the Mac's notifier.

## Provisioning

```sh
ssh exe.dev new --name <vm>                       # 5-52 chars; names are global
ssh exe.dev integrations add github --name <repo> \
    --repository justmytwospence/<repo> --attach vm:<vm> --act-as-user
ssh <vm>.exe.xyz 'git clone https://github.int.exe.xyz/justmytwospence/dotfiles.git ~/dotfiles \
    && sh -c "$(curl -fsLS get.chezmoi.io)" -- -b ~/.local/bin -t v2.73.0 \
    && ~/.local/bin/chezmoi init --source ~/dotfiles --apply --promptChoice host=exe --promptString extras='
scp ~/.config/chezmoi/key.txt <vm>.exe.xyz:.config/chezmoi/key.txt && ssh <vm>.exe.xyz chezmoi apply
herdr machine add <vm>.exe.xyz --label <vm>       # from the Mac, interactive, once
ssh nuc 'docker exec wireguard cat /config/peer_exe/peer_exe.conf' \
  | ssh <vm>.exe.xyz '~/.local/bin/homelab-vpn install'   # Snowflake tunnel
```

The first apply ends with the steps that need a person: `/login` in claude, codex
and pi, `atuin login` if wanted, phone pairing ([phone-access.md](phone-access.md)).

## Notes

- **GitHub without a key**: the VM has no GitHub SSH key. The exe.dev GitHub
  integration proxies `github.int.exe.xyz`, serving public repos and private ones
  with an integration attached, with no token on the VM. `.gitconfig` (a template)
  cancels the shared `https -> ssh` rewrite on exe hosts and routes your repos
  through the proxy, so every machine keeps the same `git@github.com:` remotes;
  `.zshenv` sets `GH_HOST=github.int.exe.xyz` for `gh`.
- **The image already has agents**: exeuntu ships `claude`, `codex` and `pi` in
  `/usr/local/bin`. The setup installs the native Claude Code into `~/.local/bin`
  (where it can update itself) and refreshes Codex and pi with `exeuntu update`;
  `pi update` refuses to replace the image's build. pi's first start asks "Use
  exe.dev LLM integrations?" (saved in `~/.pi/agent/exe-dev-llm-integration.json`):
  "I'll configure pi myself" keeps the subscriptions, but pi has no models until
  `/login`. Anthropic's `/login` has a "Copy code login" method for a browser on
  another machine.
- **Snowflake leaves from home**: a Snowflake network policy allowlists only the
  home WAN IP, so the VM is peer `exe` (10.13.13.4) on the NUC's WireGuard server.
  The tunnel is split (`172.16.0.0/12` plus a `/32` per Snowflake account IP);
  `homelab-vpn` resolves the account hosts from `~/.snowflake/config.toml` at start
  and every 15 minutes. The peer config holds a private key, so it stays on the
  NUC and is piped across; re-running the command is safe. `homelab-vpn status`
  shows which uplink each host takes.
- **Out of memory**: the image has no swap, and exe.dev's sshd gives every session
  `oom_score_adj -1000`, so a job that fills memory livelocks the VM until
  `ssh exe.dev restart <vm>`. `.zshenv` resets the score to 0 per shell, and
  `exe-memory-guard` (run once by the setup) adds a 4 GB swap file and earlyoom,
  which spares sshd, init and the herdr server. `ssh exe.dev stat <vm> --json`
  shows memory and CPU from outside a hung VM.
