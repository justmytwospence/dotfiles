---
name: paseo-machine0
description: "Run and steer coding agents on paseo-machine0 spokes (per-project machine0 VMs, each with its own Paseo daemon) from the hub. Use only when PASEO_MACHINE0_ROLE=hub and the user asks to work on a spoke, start or check agents on one, or create or wake a spoke. Not for herdr-machine0 spokes."
---

# paseo-machine0 spokes (hub only)

First check you are on the hub:

```bash
test "${PASEO_MACHINE0_ROLE:-}" = hub
```

If it fails, say this skill only works on the paseo-machine0 hub and stop.

Each spoke is a machine0 VM `paseo-<name>` running its own Paseo daemon; its
projects live in `~/Projects/<repo>` on the spoke. The hub reaches a spoke's
daemon over ssh through the managed aliases in `~/.ssh/config.d/paseo-machine0`.

## Find and prepare a spoke

```bash
paseo-machine0 ls                      # state, size, agents, idle time
paseo-machine0 wake <name>             # if it is SUSPENDED; takes a few minutes
paseo-machine0 new <name> --repo owner/repo   # only when the user asks for a new spoke
```

A spoke must be RUNNING before anything below. Never `suspend`, `rm` or
`keep-awake` a spoke unless the user asked; never pass `rm --force`.

## Run work on a spoke

Use the Paseo CLI with the spoke as the host (the daemon is on the spoke's
127.0.0.1:6767; paths are the spoke's own):

```bash
H=ssh://paseo-<name>
paseo --host "$H" ls -g
id=$(paseo --host "$H" run --background --quiet --cwd /home/ubuntu/Projects/<repo> \
      --provider claude --title <short-title> "<task>")
paseo --host "$H" wait "$id" --timeout 1800
paseo --host "$H" logs "$id" --tail 20
paseo --host "$H" send "$id" "<follow-up>"
paseo --host "$H" permit ls        # pending permission requests; ask the user before allowing
```

Pick the provider the user asked for (`claude`, `codex`, `pi`, `opencode`).
Workers started this way appear in the user's Paseo apps under that spoke's
host, so name them clearly with `--title`. For an isolated change, add
`--new-workspace worktree --worktree-mode branch-off --new-branch <branch> --base origin/main`.

Report results from `logs`, not from guesses. If `wait` times out, say so and
leave the agent running.
