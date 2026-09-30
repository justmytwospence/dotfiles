// /worktree for pi: a thin front end to ~/.local/bin/worktree, the one script
// every harness here uses for git worktrees (checkouts in <project>/.worktrees).
// Inside herdr a new checkout opens as a child space, inside tmux as a window,
// and either way pi starts in it; elsewhere the path is shown to cd into.
// Replaces @zenobius/pi-worktrees, which kept its own layout and knew nothing
// of herdr. The existing symlink activates changes with /reload.
import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const SCRIPT = path.join(homedir(), ".local/bin/worktree");
const bin = () => (existsSync(SCRIPT) ? SCRIPT : "worktree");

const SUBCOMMANDS = [
  { value: "new", label: "new <branch> -- create, open and start pi in it" },
  { value: "open", label: "open <branch> -- open an existing worktree" },
  { value: "rm", label: "rm <branch> [--force] [--delete-branch] -- remove a checkout" },
  { value: "ls", label: "ls -- list this repo's worktrees" },
  { value: "path", label: "path <branch> -- print a worktree's path" },
];

// Branches of the repo's linked worktrees, for completing open/rm/path.
function linkedBranches(cwd: string): Promise<string[]> {
  return new Promise((resolve) => {
    execFile("git", ["-C", cwd, "worktree", "list", "--porcelain"], { timeout: 2000 }, (err, out) => {
      if (err) return resolve([]);
      const blocks = out.split("\n\n").slice(1);
      resolve(blocks.map((b) => /^branch refs\/heads\/(.+)$/m.exec(b)?.[1]).filter((b): b is string => !!b));
    });
  });
}

export default function (pi: ExtensionAPI) {
  pi.registerCommand("worktree", {
    description: "Git worktrees in <project>/.worktrees (herdr space / tmux window / path)",
    getArgumentCompletions: async (prefix) => {
      const text = prefix.trimStart();
      const m = /^(\S+)\s+(\S*)$/.exec(text);
      if (!m) {
        const hits = SUBCOMMANDS.filter((s) => s.value.startsWith(text));
        return hits.length ? hits : null;
      }
      const [, sub, arg] = m;
      if (!["open", "rm", "path"].includes(sub)) return null;
      const hits = (await linkedBranches(process.cwd()))
        .filter((b) => b.startsWith(arg))
        .map((b) => ({ value: `${sub} ${b}`, label: b }));
      return hits.length ? hits : null;
    },
    handler: async (args, ctx) => {
      const argv = args.trim().split(/\s+/).filter(Boolean);
      if (argv.length === 0) argv.push("ls");
      // Typed by a person, so go where the new checkout opened, unless told not to.
      if ((argv[0] === "new" || argv[0] === "open") && !argv.includes("--no-focus")) argv.push("--focus");
      const res = await pi.exec(bin(), argv, { cwd: ctx.cwd, timeout: 120_000 });
      const out = [res.stderr.trim(), res.stdout.trim()].filter(Boolean).join("\n");
      ctx.ui.notify(out || `worktree ${argv[0]}: exit ${res.code}`, res.code === 0 ? "info" : "error");
    },
  });
}
