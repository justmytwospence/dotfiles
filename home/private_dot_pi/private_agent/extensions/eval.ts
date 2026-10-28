// /eval for pi: the paid Jev replay evals of the pi-plugins checkout (~/Projects/pi-plugins),
// auto-effort and tool-gate, behind a free dry run and a confirmation. The dry run
// (`npm run -s eval:dry`) samples real sessions and counts the calls without calling Jev; only
// "Run it" starts the live run (`EVAL_COMPARE=1 npm run eval`, in the background, output to a
// temp log). When it ends, the tables and the change against the previous recorded run
// (`npm run -s eval:last`) are posted to the session. Live runs bill the TypeSafe account
// (TYPESAFE_API_KEY), not the Claude or Codex subscriptions. Inert where the checkout does not
// exist (the NUC): the command says so and does nothing. Self-contained: node builtins only.
import { execFile, spawn, type ChildProcess } from "node:child_process";
import { closeSync, existsSync, mkdtempSync, openSync, readFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const REPO = path.join(os.homedir(), "Projects", "pi-plugins");
const MAX_POST = 8_000; // characters of log posted into the session; the rest stays in the file

type Target = "auto-effort" | "tool-gate";
const PACKAGES: Record<Target, { dir: string; file: string }> = {
  "auto-effort": { dir: "packages/pi-auto-effort", file: "eval/replay.eval.ts" },
  "tool-gate": { dir: "packages/pi-tool-gate", file: "eval/sessions.eval.ts" },
};
const CHOICES = [
  { label: "auto-effort replay", arg: "auto-effort" },
  { label: "tool-gate replay", arg: "tool-gate" },
  { label: "both replays", arg: "both" },
  { label: "last results", arg: "last" },
];

// For the change summary: which direction is an improvement. Unlisted metrics are reported neutrally.
const LOWER_IS_BETTER = new Set(["spend", "jevFailures", "p50", "p95", "above", "below", "overrides", "levelChangesPerSession", "levelChangesMax", "failed", "misses", "extraPrompts"]);
const HIGHER_IS_BETTER = new Set(["exact", "withinOne", "sameLevelAsLive"]);

type Dry = { seed: number; targets: Record<string, { sessions: unknown[]; estimatedCalls: number; notes: string }>; estimate: { calls: number; costPerCall: number; usd: { low: number; expected: number; high: number }; note: string } };
type Rec = { at: string; commit: string; dirty: boolean; seed: number | null; spend: number; calls: number; metrics: Record<string, number>; compare?: Record<string, number> };
type Last = { target: string; runs: number; last: Rec | null; previous: Rec | null; diff: Record<string, any> | null };

const usd = (n: number) => `$${n.toFixed(4)}`;
const stripAnsi = (s: string) => s.replace(/\x1b\[[0-9;?]*[A-Za-z]/g, "");
const tail = (s: string, n: number) => (s.length > n ? `... (cut; full log in the file below)\n${s.slice(-n)}` : s);

function npm(args: string[], env: NodeJS.ProcessEnv = process.env, cwd = REPO): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve) => {
    // execFile, no shell: the arguments are fixed strings, never interpolated into a command line.
    execFile("npm", args, { cwd, env, timeout: 180_000, maxBuffer: 16 * 1024 * 1024 }, (error, stdout, stderr) => {
      resolve({ code: error ? ((error as any).code as number) || 1 : 0, stdout, stderr });
    });
  });
}

async function lastOf(target: Target): Promise<Last | undefined> {
  const res = await npm(["run", "-s", "eval:last", "--", target]);
  try {
    return JSON.parse(res.stdout) as Last;
  } catch {
    return undefined;
  }
}

/** What got better, worse or just moved between the two newest records, in plain words. */
function summarize(l: Last): string {
  if (!l.last) return `${l.target}: no recorded runs yet.`;
  const head = `${l.target}: last run ${l.last.at} at ${l.last.commit}${l.last.dirty ? " (dirty tree)" : ""}, seed ${l.last.seed ?? "-"}, ${usd(l.last.spend)} over ${l.last.calls} calls.`;
  if (!l.previous || !l.diff) return `${head}\nNo earlier run to compare with.`;
  const better: string[] = [];
  const worse: string[] = [];
  const moved: string[] = [];
  const walk = (delta: Record<string, any>, before: any, after: any, prefix: string) => {
    for (const [key, d] of Object.entries(delta)) {
      if (d && typeof d === "object") {
        walk(d, before?.[key], after?.[key], `${key}.`);
        continue;
      }
      if (!d) continue;
      const name = key.replace(/^level_/, "level ");
      const line = `${prefix === "compare." ? "old behaviour " : ""}${name} ${before?.[key]} -> ${after?.[key]} (${d > 0 ? "+" : ""}${Math.round(d * 1e4) / 1e4})`;
      const good = HIGHER_IS_BETTER.has(key) ? d > 0 : LOWER_IS_BETTER.has(key) ? d < 0 : undefined;
      (good === undefined ? moved : good ? better : worse).push(line);
    }
  };
  walk(l.diff, { spend: l.previous.spend, calls: l.previous.calls, metrics: l.previous.metrics, compare: l.previous.compare }, { spend: l.last.spend, calls: l.last.calls, metrics: l.last.metrics, compare: l.last.compare }, "");
  const section = (title: string, lines: string[]) => (lines.length ? `${title}:\n${lines.map((x) => `  ${x}`).join("\n")}` : "");
  const body = [section("Better", better), section("Worse", worse), section("Changed (no better or worse)", moved)].filter(Boolean).join("\n");
  return `${head}\nAgainst the run before (${l.previous.at}, ${l.previous.commit}):\n${body || "  no numbers changed."}`;
}

export default function (pi: ExtensionAPI) {
  let running: { target: string; child?: ChildProcess; started: number } | undefined;

  pi.registerCommand("eval", {
    description: "Paid Jev replay evals of pi-plugins: dry run, confirm, run in background, diff (/eval last for stored results)",
    getArgumentCompletions: (prefix) => {
      const hits = CHOICES.filter((c) => c.arg.startsWith(prefix.trim())).map((c) => ({ value: c.arg, label: c.label }));
      return hits.length ? hits : null;
    },
    handler: async (args, ctx) => {
      const say = (msg: string, level: "info" | "warning" | "error" = "info") => ctx.ui.notify(msg, level);
      if (!existsSync(path.join(REPO, "package.json"))) return say("no pi-plugins checkout here");

      let choice = args.trim().toLowerCase();
      if (!choice) {
        const picked = await ctx.ui.select("Eval", CHOICES.map((c) => c.label));
        choice = CHOICES.find((c) => c.label === picked)?.arg ?? "";
        if (!choice) return;
      }
      if (!CHOICES.some((c) => c.arg === choice)) return say(`usage: /eval [${CHOICES.map((c) => c.arg).join("|")}]`, "error");
      const targets: Target[] = choice === "both" ? ["auto-effort", "tool-gate"] : choice === "last" ? [] : [choice as Target];

      const post = (text: string, details?: unknown) => pi.sendMessage({ customType: "eval", content: text, display: true, details });

      if (choice === "last") {
        const parts = await Promise.all((["auto-effort", "tool-gate"] as Target[]).map(async (t) => {
          const l = await lastOf(t);
          return l ? summarize(l) : `${t}: could not read results (npm run -s eval:last failed in ${REPO}).`;
        }));
        return post(parts.join("\n\n"));
      }

      if (running) return say(`an eval is already running (${running.target}, ${Math.round((Date.now() - running.started) / 1000)}s); wait for it`, "warning");

      // Dry run: free. EVAL_COMPARE=1 so the estimate counts what the live run will do.
      say(`/eval: dry run for ${choice} (no Jev calls)...`);
      const env = { ...process.env, EVAL_COMPARE: "1" };
      const dry = await npm(["run", "-s", "eval:dry", "--", choice === "both" ? "all" : choice], env);
      let plan: Dry;
      try {
        plan = JSON.parse(dry.stdout) as Dry;
      } catch {
        return say(`dry run failed (exit ${dry.code}): ${stripAnsi(dry.stderr || dry.stdout).trim().slice(-600) || "no output"}`, "error");
      }
      const sessions = new Set(Object.values(plan.targets).flatMap((t) => t.sessions.map((s: any) => s.file))).size;
      const calls = plan.estimate.calls;
      const keyMissing = !process.env.TYPESAFE_API_KEY?.trim();
      const question = [
        `Eval ${choice}: seed ${plan.seed}, ${sessions} sessions, about ${calls} paid Jev calls.`,
        `Estimated spend (an estimate, ${plan.estimate.costPerCall} per call): ${usd(plan.estimate.usd.expected)}, range ${usd(plan.estimate.usd.low)} to ${usd(plan.estimate.usd.high)}.`,
        "This bills the TypeSafe account (TYPESAFE_API_KEY), not the Claude or Codex subscriptions.",
        keyMissing ? "TYPESAFE_API_KEY is NOT set in pi's environment, so the evals would skip themselves." : "TYPESAFE_API_KEY is set.",
        "The run is in the background; ending this pi session may kill it.",
      ].join("\n");

      if (keyMissing) return say(`${question}\nSet TYPESAFE_API_KEY and restart pi to run it.`, "warning");
      if (!ctx.hasUI) return say(`${question}\nNeeds an interactive session to confirm.`, "warning");
      const answer = await ctx.ui.select(question, ["Run it", "Cancel"]);
      if (answer !== "Run it") return say("/eval: cancelled, nothing was spent");

      // Live run, one target after the other, in the background.
      const liveEnv = { ...env, EVAL_SEED: String(plan.seed) }; // the sample that was confirmed
      const logDir = mkdtempSync(path.join(os.tmpdir(), "pi-eval-"));
      running = { target: choice, started: Date.now() };
      say(`/eval: started ${choice} in the background (about ${calls} calls, ${usd(plan.estimate.usd.expected)} estimated). Logs in ${logDir}. Ending this session may kill it.`);
      const tick = setInterval(() => ctx.ui.setStatus("eval", `eval ${running?.target}: ${Math.round((Date.now() - (running?.started ?? Date.now())) / 1000)}s`), 5_000);
      tick.unref?.();

      void (async () => {
        try {
          for (const target of targets) {
            const pkg = PACKAGES[target];
            const before = (await lastOf(target))?.last?.at ?? null;
            const logFile = path.join(logDir, `${target}.log`);
            const fd = openSync(logFile, "a");
            const code = await new Promise<number | null>((resolve) => {
              // No shell: argv only. --disableConsoleIntercept makes vitest print the eval's console tables.
              const child = spawn("npm", ["run", "eval", "--", pkg.file, "--reporter=verbose", "--disableConsoleIntercept"], { cwd: path.join(REPO, pkg.dir), env: liveEnv, stdio: ["ignore", fd, fd] });
              running = { ...running!, target, child };
              child.on("error", () => resolve(null));
              child.on("close", (c) => resolve(c));
            });
            closeSync(fd);
            let log = "";
            try {
              log = stripAnsi(readFileSync(logFile, "utf8")).trim();
            } catch {}
            const after = await lastOf(target);
            const fresh = after?.last && after.last.at !== before;
            const diffText = !after ? "Could not read the results history." : fresh ? summarize(after) : `No new result was recorded (the eval skipped, failed, or does not record); showing what is stored:\n${summarize(after)}`;
            post(`/eval ${target} finished (exit ${code ?? "spawn error"}), full log: ${logFile}\n\n${tail(log, MAX_POST)}\n\n${diffText}`, { target, code, logFile });
            say(`/eval ${target} finished (exit ${code ?? "spawn error"})`, code === 0 ? "info" : "error");
          }
        } finally {
          clearInterval(tick);
          ctx.ui.setStatus("eval", undefined);
          running = undefined;
        }
      })();
    },
  });
}
