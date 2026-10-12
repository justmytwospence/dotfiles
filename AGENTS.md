# Dotfiles project

Before changing this repo or applying its configuration, read `.agents/skills/chezmoi/SKILL.md`. It owns the source/target workflow, host policy, settings merges, provisioning, secrets, and machine synchronization. Follow its sync reference after commit, push, or apply.

This file and the project skill are repo metadata, not files deployed into `$HOME`.

Pi suite migration and rollback: `lib/pi_suite_migration.py check|apply|rollback` edits only managed sources after the providing revision is pinned; see `docs/plugins.md`. Tests: `python3 -B -m unittest lib/test_agent_settings.py`.
