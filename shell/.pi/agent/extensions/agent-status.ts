// agent-status -- put the Claude usage gauges in pi's footer.
//
// pi's built-in footer already carries the model, cost, context usage, git branch
// and elapsed time, so this adds only what it cannot know: the plan limits and the
// extra-usage pool, rendered by ~/.local/bin/agent-status so the numbers read the
// same here, in Claude Code's statusline, and in herdr.
//
// ctx.ui.setStatus() contributes a keyed segment to the built-in footer rather
// than replacing it (ctx.ui.setFooter would). That keeps pi's own layout intact.
//
// Text is plain by default: the renderer's ANSI threshold colors would have to
// survive pi's footer styling, and a garbled footer is worse than a monochrome
// one. Drop "--plain" below to try colors; add a width to get the bars back.

import { execFile } from "node:child_process";
import path from "node:path";

const SCRIPT = path.join(process.env.HOME ?? "", ".local", "bin", "agent-status");
const HERDR_SCRIPT = path.join(process.env.HOME ?? "", ".local", "bin", "herdr-agent-status");
const ARGS = ["--plain", "--width", "0"];
const REFRESH_MS = 60_000;

export default function (pi: any) {
  let ui: any;
  let timer: ReturnType<typeof setInterval> | undefined;

  const render = () => {
    if (!ui) return;
    execFile(SCRIPT, ARGS, { timeout: 5_000 }, (err: unknown, stdout: string) => {
      // A status line must never be the reason pi breaks: no cache, no network,
      // no script (a machine that has not stowed it yet) all just render nothing.
      if (err) return;
      const text = String(stdout).trim();
      ui.setStatus("usage", text.length > 0 ? text : undefined);
    });
    // Same numbers into herdr's sidebar, so a pi pane reads like every other
    // agent there. No-op outside herdr, and throttled on its own.
    execFile(HERDR_SCRIPT, [], { timeout: 5_000 }, () => {});
  };

  const attach = (ctx: any) => {
    if (ctx?.mode !== "tui") return; // print and RPC modes have no footer
    ui = ctx.ui;
    if (!timer) {
      timer = setInterval(render, REFRESH_MS);
      timer.unref?.();
    }
    render();
  };

  pi.on("session_start", (_event: unknown, ctx: any) => attach(ctx));
  // A turn just spent tokens, so the gauges have moved.
  pi.on("agent_settled", (_event: unknown, ctx: any) => {
    attach(ctx);
    render();
  });
}
