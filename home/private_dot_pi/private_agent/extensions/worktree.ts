// /worktree for pi: git worktrees in <repo>/.worktrees/<branch> (slashes as
// dashes), the one location every harness here shares (docs/agents.md
// "Worktrees"). Inside herdr, new/open/rm go through herdr's own worktree API,
// so a checkout opens as a grouped worktree space; elsewhere plain git, and the
// path is shown to cd into. Self-contained: needs only git (and herdr in herdr).
// The existing symlink activates changes with /reload.
import path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const SUBCOMMANDS = [
  { value: "new", label: "new <branch> -- create <repo>/.worktrees/<branch> (opens a herdr space)" },
  { value: "open", label: "open <branch> -- open an existing worktree in herdr" },
  { value: "rm", label: "rm <branch> [--force] -- remove a checkout (branch kept)" },
  { value: "ls", label: "ls -- list this repo's worktrees" },
];

type Linked = { path: string; branch?: string };

export default function (pi: ExtensionAPI) {
  const git = (cwd: string, args: string[]) => pi.exec("git", ["-C", cwd, ...args], { cwd, timeout: 60_000 });
  const inHerdr = () => process.env.HERDR_ENV === "1";

  // Main checkout first, then linked worktrees.
  async function worktrees(cwd: string): Promise<Linked[] | undefined> {
    const res = await git(cwd, ["worktree", "list", "--porcelain"]);
    if (res.code !== 0) return undefined;
    return res.stdout.trim().split("\n\n").map((block) => ({
      path: /^worktree (.+)$/m.exec(block)?.[1] ?? "",
      branch: /^branch refs\/heads\/(.+)$/m.exec(block)?.[1],
    }));
  }

  const find = (linked: Linked[], want: string) =>
    linked.find((w) => w.branch === want || path.basename(w.path) === want || w.path === path.resolve(want));

  pi.registerCommand("worktree", {
    description: "Git worktrees in <repo>/.worktrees (herdr space or path)",
    getArgumentCompletions: async (prefix) => {
      const text = prefix.trimStart();
      const m = /^(\S+)\s+(\S*)$/.exec(text);
      if (!m) {
        const hits = SUBCOMMANDS.filter((s) => s.value.startsWith(text));
        return hits.length ? hits : null;
      }
      const [, sub, arg] = m;
      if (!["open", "rm"].includes(sub)) return null;
      const hits = ((await worktrees(process.cwd())) ?? [])
        .slice(1)
        .flatMap((w) => (w.branch?.startsWith(arg) ? [{ value: `${sub} ${w.branch}`, label: w.branch }] : []));
      return hits.length ? hits : null;
    },
    handler: async (args, ctx) => {
      const [sub = "ls", target, ...rest] = args.trim().split(/\s+/).filter(Boolean);
      const done = (msg: string, ok = true) => ctx.ui.notify(msg, ok ? "info" : "error");
      const run = async (cmd: string, argv: string[]) => {
        const res = await pi.exec(cmd, argv, { cwd: ctx.cwd, timeout: 120_000 });
        return { ok: res.code === 0, out: (res.stderr.trim() || res.stdout.trim()) };
      };

      const linked = await worktrees(ctx.cwd);
      if (!linked) return done(`not in a git repository: ${ctx.cwd}`, false);
      const root = linked[0].path;

      if (sub === "ls") {
        const lines = linked.slice(1).map((w) => `${w.branch ?? "(detached)"}  ${w.path}`);
        return done(lines.length ? lines.join("\n") : `no worktrees in ${root}/.worktrees`);
      }
      if (!target) return done(`usage: /worktree ${sub} <branch>`, false);

      if (sub === "new") {
        const dest = path.join(root, ".worktrees", target.replaceAll("/", "-"));
        if (inHerdr()) {
          const r = await run("herdr", ["worktree", "create", "--cwd", root, "--branch", target, "--path", dest, "--focus"]);
          return r.ok ? done(`worktree ${target}: ${dest}`) : done(r.out, false);
        }
        // Existing branch: check it out; otherwise branch from this checkout's HEAD.
        const exists = (await git(root, ["rev-parse", "--verify", "--quiet", `refs/heads/${target}`])).code === 0;
        const r = await run("git", ["-C", ctx.cwd, "worktree", "add", ...(exists ? [dest, target] : ["-b", target, dest, "HEAD"])]);
        return r.ok ? done(`worktree ${target}: cd ${dest}`) : done(r.out, false);
      }

      const wt = find(linked.slice(1), target);
      if (!wt) return done(`no worktree matching '${target}'`, false);

      if (sub === "open") {
        if (!inHerdr()) return done(`cd ${wt.path}`);
        const r = await run("herdr", ["worktree", "open", "--cwd", root, "--path", wt.path, "--focus"]);
        return r.ok ? done(`opened ${wt.path}`) : done(r.out, false);
      }
      if (sub === "rm") {
        const force = rest.includes("--force") ? ["--force"] : [];
        // An open herdr space goes with its checkout.
        if (inHerdr()) {
          const res = await pi.exec("herdr", ["worktree", "list", "--cwd", root], { cwd: ctx.cwd, timeout: 10_000 });
          let ws: string | undefined;
          try {
            ws = JSON.parse(res.stdout).result.worktrees.find((w: { path: string }) => w.path === wt.path)?.open_workspace_id;
          } catch {}
          if (ws) {
            const r = await run("herdr", ["worktree", "remove", "--workspace", ws, ...force]);
            return r.ok ? done(`removed ${wt.path} (branch ${wt.branch ?? "-"} kept)`) : done(r.out, false);
          }
        }
        const r = await run("git", ["-C", root, "worktree", "remove", ...force, wt.path]);
        return r.ok ? done(`removed ${wt.path} (branch ${wt.branch ?? "-"} kept)`) : done(r.out, false);
      }
      done(`unknown subcommand: ${sub}`, false);
    },
  });
}
