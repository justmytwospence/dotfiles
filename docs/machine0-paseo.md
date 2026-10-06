# Paseo spokes on machine0

[paseo-machine0](https://github.com/justmytwospence/paseo-machine0) is the Paseo
counterpart of [machine0-herdr.md](machine0-herdr.md), fully separate from it: its
own hub, image, profile, key, VMs and logins. Every project gets a machine0 VM
`paseo-<name>` (chezmoi host `paseo-spoke`) running its own Paseo daemon, reached by
the Paseo apps through Paseo's relay. A dedicated exe.dev VM, `paseo-hub`
(chezmoi host `paseo-hub`; 2 vCPU, 4 GB), creates, wakes, suspends and removes spokes, holds
every login, pushes credentials, and adds a **Spokes** screen to the Paseo app. The
hub is never between you and an agent. The plugin README covers the design.

- **Spokes are clones** of the golden image `paseo-machine0-spoke`, built by
  `paseo-machine0 image build`. The image build and `paseo-machine0 sync` run
  the same idempotent step: reset the spoke's disposable dotfiles checkout to
  origin/main, install chezmoi if missing,
  `chezmoi init --apply --force` as `paseo-spoke` (no herdr, Moshi or Heeler),
  then `paseo-setup`. New spoke on the Spokes screen (or `paseo-machine0 new
  <name> --repo owner/repo`) names the host, pushes credentials, updates Paseo,
  clones the repos as Paseo projects and stores the pairing link.
- **Adding a spoke to the apps**: on the phone, Connect on its Spokes row opens the
  pairing link. On the desktop, Copy link, then Settings, Add host, Paste pairing
  link. Once per spoke per device; it survives suspend and resume.
- **Idle spokes suspend** after 2 hours with no agent running, no schedule, load
  under 0.3 and no permission request younger than a day; Wake on the Spokes screen
  brings one back. Keep awake exempts one.
- **Logins live only on the hub**, in `~/.config/paseo-machine0/secrets.env`
  (Claude setup-token, Meta and TypeSafe keys, the machine0 token) and the broker
  store (openai-codex and Radius). hubd pushes them to spokes; pi reads the
  brokered ones through pi-brokered-auth (`.zshenv` sets the variables on Paseo
  hosts). `paseo-machine0 secrets show` lists what is set.
- **Orchestrators** run on the hub's own Paseo daemon; the `paseo-machine0` skill
  tells them how to start and follow work on a spoke with
  `paseo --host ssh://paseo-<name> ...`.

## Provisioning the hub

```sh
ssh exe.dev new --name=paseo-hub --cpu=2 --memory=4GB
ssh exe.dev integrations attach dotfiles vm:paseo-hub   # takes a minute to apply
ssh paseo-hub.exe.xyz 'git clone https://github.int.exe.xyz/justmytwospence/dotfiles.git ~/dotfiles \
    && sh -c "$(curl -fsLS get.chezmoi.io)" -- -b ~/.local/bin -t v2.73.0 \
    && ~/.local/bin/chezmoi init --source ~/dotfiles --apply --promptChoice host=paseo-hub --promptString extras='
```

The hub's setup registers the Spokes plugin with its Paseo daemon, installs the
machine0 CLI and the broker's private pi SDK, makes the hub's ssh key and starts
hubd. The first apply ends with the steps that need a person: the machine0 token,
key and `paseo-machine0` profile (GitHub integration only; its env sets
`MACHINE0_API_KEY` and `MACHINE0_MCP_URL` to dummies so spokes never receive a key
that can manage the fleet), the Claude setup-token, `paseo-machine0 secrets login`,
the API keys, pairing the hub in the apps, and the first
`paseo-machine0 image build --fresh`.
