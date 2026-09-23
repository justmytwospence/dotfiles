// plan-to-obsidian -- save a finished pi plan to Obsidian, like Claude Code's
// ExitPlanMode hook does.
//
// @narumitw/pi-plan-mode ends planning with a plan_mode_complete tool call whose
// `plan` argument is the whole Markdown plan -- pi's equivalent of Claude Code's
// ExitPlanMode. Rather than duplicate the vault logic, this writes the plan to a
// temp file and feeds ~/.claude/hooks/save-plan-to-obsidian.sh the same JSON
// shape Claude's PostToolUse hook sends ({cwd, tool_response.filePath}), so both
// harnesses land in "Claude Code Plans/<project>/" with the same frontmatter.
//
// The hook's stdout (additionalContext for Claude) is ignored: pi's plan-mode
// review flow owns what happens next. Failures are silent -- saving a copy of the
// plan must never be the reason planning breaks.

import { execFile } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";

const HOOK = path.join(process.env.HOME ?? "", ".claude", "hooks", "save-plan-to-obsidian.sh");

export default function (pi: any) {
  pi.on("tool_result", async (event: any, ctx: any) => {
    if (event.toolName !== "plan_mode_complete" || event.isError) return;
    const plan = typeof event.input?.plan === "string" ? event.input.plan.trim() : "";
    if (!plan) return;

    let dir: string | undefined;
    try {
      dir = mkdtempSync(path.join(os.tmpdir(), "pi-plan-"));
      const file = path.join(dir, "plan.md");
      writeFileSync(file, plan + "\n");
      const input = JSON.stringify({ cwd: ctx.cwd, tool_response: { filePath: file } });
      const child = execFile("bash", [HOOK], { timeout: 30_000 }, () => {
        if (dir) rmSync(dir, { recursive: true, force: true });
      });
      child.stdin?.end(input);
    } catch {
      if (dir) rmSync(dir, { recursive: true, force: true });
    }
    // Returning nothing leaves the tool result untouched.
  });
}
