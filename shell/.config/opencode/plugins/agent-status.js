// agent-status -- surface the Claude usage gauges for opencode panes in herdr.
//
// opencode's TUI can be extended (plugins render into named slots like
// app_bottom), but only through a compiled Solid/JSX plugin. herdr's sidebar
// needs neither: herdr-agent-status reports a $usage token for this pane, so the
// gauges appear beside every agent, in the same shape pi and Claude Code show.
//
// Auto-discovered from ~/.config/opencode/plugins/ -- no config entry needed.
// It throttles itself, so hooking a chatty event is fine.

export default async ({ $ }) => {
  const push = async () => {
    // Never let a status push surface as an opencode error: no herdr, no pane,
    // no script all exit quietly.
    try {
      await $`herdr-agent-status`.quiet().nothrow();
    } catch {
      // ignore
    }
  };

  return {
    event: async () => {
      await push();
    },
  };
};
