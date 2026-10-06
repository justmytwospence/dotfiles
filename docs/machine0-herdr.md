# machine0 spokes with a herdr hub

[herdr-machine0](https://github.com/justmytwospence/herdr-machine0) runs agents on
small per-project [machine0](https://machine0.io) VMs, the **spokes** (chezmoi host
`m0-spoke`), and shows them in one herdr server, the **hub** (`m0-hub`): an exe.dev
VM, `herdr-hub`, with 2 vCPU and 4 GB, which the Mac adds like any other machine.
A hub pane runs `spoke attach <spoke> <slot>`, an ssh wrapper; the agent runs on
the spoke inside `dtach` and reports its state to the hub's herdr through a
forwarded socket. The plugin README covers the design.

- **Spokes are clones** of the golden image `m0-spoke`, which `spoke image build`
  makes on a builder VM: the plugin's `setup/spoke.sh`, then this repo, wired in
  `dot_config/herdr-machine0/config.json` (written on the hub only).
  `provision_command` clones dotfiles, installs chezmoi v2.73.0 and runs
  `chezmoi init --apply --promptChoice host=m0-spoke`; `sync_command` is
  `chezmoi update --force` on every spoke creation and `spoke sync`. Then the
  builder scrubs every credential. `spoke new <name> --repo owner/repo` creates a
  spoke; usually simpler, a new space on the hub asks which repo it is for. Each
  repo gets one spoke and each worktree is a tab in its space. `prefix+N` on the
  hub (or the Mac with herdr-hub selected) opens the new-agent/new-spoke popup.
- **Idle spokes suspend themselves** after 2 hours (every slot idle or done, no
  background work, load under 0.3; `spoke keep-awake <name>` exempts one). Enter
  in a suspended spoke's pane wakes it; `prefix+Z` suspends the focused one now.
- **Logins live only on the hub.** One `claude setup-token` token, pushed to
  spokes; ChatGPT and Radius are brokered (the hub holds the only refresh token and
  hands out short-lived access tokens); Meta and TypeSafe keys are pushed with the
  token. `spoke secrets show` lists what is set.
- **Spoke state that matters is pushed**: `spoke rm` refuses while any repo has
  uncommitted or unpushed work, and archives the sessions to the hub first. The
  Snowflake tunnel is not set up on spokes.

## Provisioning the hub

```sh
ssh exe.dev new --name herdr-hub && ssh exe.dev resize herdr-hub --cpu=2 --memory=4
ssh exe.dev integrations add github --name dotfiles \
    --repository justmytwospence/dotfiles --attach vm:herdr-hub --act-as-user
ssh herdr-hub.exe.xyz 'git clone https://github.int.exe.xyz/justmytwospence/dotfiles.git ~/dotfiles \
    && sh -c "$(curl -fsLS get.chezmoi.io)" -- -b ~/.local/bin -t v2.73.0 \
    && ~/.local/bin/chezmoi init --source ~/dotfiles --apply --promptChoice host=m0-hub --promptString extras='
herdr machine add herdr-hub.exe.xyz --label herdr-hub      # from the Mac, once
```

The hub's setup runs the plugin's `spoke setup hub`; `spoke doctor` then checks
the whole hub. The first apply ends with the steps that need a person: the
machine0 API token, ssh key and `m0` profile (its GitHub integration gives spokes
`gh`), the Claude setup-token, `spoke secrets login` for the broker, the API keys,
and the first `spoke image build --fresh`. Heeler and Moshi add the hub as any
exe.dev VM.

Moving the hub to machine0 (if the exe pool turns out too contended) means a
machine0 `large` VM with the hub's setup; the `.gitconfig` and `.zshenv` branches
for `m0-hub` assume exe.dev's GitHub proxy and would need a machine0 variant.
