// agent-status -- surface opencode's state where the other agents already show
// theirs: the herdr sidebar, and the tmux window tabs.
//
// herdr: its sidebar needs no TUI plugin -- herdr-agent-status reports a $usage
// token for this pane, so the gauges appear beside every agent, in the same
// shape pi and Claude Code show.
//
// tmux: tmux-agent-state writes this pane's @cc_state, the same per-pane option
// the Claude Code hooks set, which tmux-claude-agg folds into the window tab.
// Without it an opencode pane is the one dark tab in the window list.
//
// Auto-discovered from ~/.config/opencode/plugins/ -- no config entry needed.

const TMUX_STATE = `${process.env.HOME}/.local/bin/tmux-agent-state`;

// opencode's state, in the vocabulary the tmux tabs use. Everything else is a
// event we have no opinion about, and returning null leaves the tab alone.
function classify(event) {
  switch (event?.type) {
    // A permission request appeared: this pane wants a decision.
    case "permission.updated":
      return "waiting";
    case "permission.replied":
      return "running";
    case "session.idle":
      return "done";
    // The authoritative busy/idle signal, and the one that catches a turn that
    // ended without a session.idle (interrupted, or failed).
    case "session.status":
      return event.properties?.status?.type === "idle" ? "done" : "running";
    case "session.created":
      return "clear";
    default:
      return null;
  }
}

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

  // opencode emits events continuously, so shell out only when the
  // classification actually changes -- otherwise this forks on every token.
  let lastState = null;
  const setState = async (state) => {
    if (state === lastState) return;
    lastState = state;
    try {
      await $`${TMUX_STATE} ${state}`.quiet().nothrow();
    } catch {
      // ignore
    }
  };

  return {
    event: async ({ event }) => {
      await push();
      if (!process.env.TMUX) return;
      const state = classify(event);
      if (state) await setState(state);
    },
  };
};
