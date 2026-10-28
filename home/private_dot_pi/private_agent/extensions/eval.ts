// /eval for pi: the paid Jev evals of the pi-plugins checkout (~/Projects/pi-plugins) through its one
// runner (`npm run -s eval -- ...`), behind a free dry run and a confirmation. The targets are not
// listed here: the picker is built from `--list --json`, so a target added to the checkout shows up
// at once. The dry run (`--dry <ids> --json`) samples real sessions and counts the calls without
// calling Jev; only "Run it" starts the live run (`EVAL_COMPARE=1 EVAL_SEED=<confirmed> npm run -s eval
// -- <ids> --json`, in the background, the runner's own report in a temp log). When it ends, the report
// and the change against the previous recorded run (`--last --json`) are posted to the session. Live
// runs bill the TypeSafe account (TYPESAFE_API_KEY), not the Claude or Codex subscriptions. Inert where
// the checkout does not exist (the NUC): the command says so and does nothing. Self-contained: node
// builtins only.
import { execFile, spawn, type ChildProcess } from "node:child_process";
import { closeSync, existsSync, mkdtempSync, openSync, readFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const REPO = path.join(os.homedir(), "Projects", "pi-plugins");
const MAX_POST = 8_000; // characters of log posted into the session; the rest stays in the file
const MAX_LABEL = 42; // picker option labels stay short enough for a narrow pane

type Listed = { id: string; title: string; package: string; kind: "cases" | "replay" };

// For the change summary: which direction is an improvement. A metric whose name contains one of these
// (case-insensitive) is better lower; so are the older exact names below. Everything else is better
// higher, except the neutral ones (a count of calls or of sessions per level says nothing about quality).
const LOWER_PARTS = ["fail", "wrong", "extra", "miss", "refused", "cleared", "spend", "p95", "p50", "above"];
const LOWER_NAMES = new Set(["below", "overrides", "levelchangespersession", "levelchangesmax"]);
const isNeutral = (key: string) => key === "calls" || key.startsWith("level_");
const lowerIsBetter = (key: string) => LOWER_PARTS.some((p) => key.toLowerCase().includes(p)) || LOWER_NAMES.has(key.toLowerCase());

type Rec = { at: string; commit: string; dirty: boolean; seed: number | null; spend: number; calls: number; metrics: Record<string, number>; compare?: Record<string, number> };
type LastOne = { runs: number; last: Rec | null; previous: Rec | null; diff: Record<string, any> | null };
type Dry = {
  seed: number | null;
  sessions: unknown[];
  targets: Record<string, { kind: string; calls?: number; notes?: string; error?: string }>;
  totalCalls: number;
  estimate: { usd: { low: number; high: number }; note: string };
};
type Outcome = { kind: string; pass: boolean; failures?: number; spend: number; calls: number; error?: string };
type Live = { seed: number | null; pass?: boolean; spend?: number; calls?: number; skipped?: boolean; reason?: string; targets: Record<string, Outcome> };

const usd = (n: number) => `$${n.toFixed(4)}`;
const stripAnsi = (s: string) => s.replace(/\x1b\[[0-9;?]*[A-Za-z]/g, "");
const tail = (s: string, n: number) => (s.length > n ? `... (cut; full log in the file below)\n${s.slice(-n)}` : s);
const short = (pkg: string) => pkg.replace(/^pi-/u, "");
const clip = (s: string, n = MAX_LABEL) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

/** `<id> (<package>)`, at most MAX_LABEL characters: the id is shortened first. */
function labelOf(t: Listed): string {
  const suffix = ` (${short(t.package)})`;
  if (t.id.length + suffix.length <= MAX_LABEL) return `${t.id}${suffix}`;
  return clip(`${clip(t.id, Math.max(8, MAX_LABEL - suffix.length))}${suffix}`);
}

function npm(args: string[], env: NodeJS.ProcessEnv = process.env, cwd = REPO): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve) => {
    // execFile, no shell: the arguments are ids from the runner's own list, never interpolated into a command line.
    execFile("npm", args, { cwd, env, timeout: 180_000, maxBuffer: 16 * 1024 * 1024 }, (error, stdout, stderr) => {
      resolve({ code: error ? ((error as any).code as number) || 1 : 0, stdout, stderr });
    });
  });
}

const runner = (args: string[], env?: NodeJS.ProcessEnv) => npm(["run", "-s", "eval", "--", ...args], env);

async function listTargets(): Promise<Listed[] | undefined> {
  const res = await runner(["--list", "--json"]);
  try {
    const parsed = JSON.parse(res.stdout);
    return Array.isArray(parsed) ? (parsed as Listed[]) : undefined;
  } catch {
    return undefined;
  }
}

async function lastOf(ids: string[]): Promise<Record<string, LastOne> | undefined> {
  const res = await runner(["--last", "--json", ...ids]);
  try {
    return (JSON.parse(res.stdout) as { targets: Record<string, LastOne> }).targets;
  } catch {
    return undefined;
  }
}

/** What got better, worse or just moved between the two newest records, in plain words. */
function summarize(id: string, l: LastOne): string {
  if (!l.last) return `${id}: no recorded runs yet.`;
  const head = `${id}: last run ${l.last.at} at ${l.last.commit}${l.last.dirty ? " (dirty tree)" : ""}, seed ${l.last.seed ?? "-"}, ${usd(l.last.spend)} over ${l.last.calls} calls.`;
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
      const good = isNeutral(key) ? undefined : lowerIsBetter(key) ? d < 0 : d > 0;
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
  let known: Listed[] = []; // the last list read, for argument completion

  pi.registerCommand("eval", {
    description: "Paid Jev evals of pi-plugins (the unified runner): pick, dry run, confirm, run in background, diff (/eval last for stored results)",
    getArgumentCompletions: async (prefix) => {
      if (!existsSync(path.join(REPO, "package.json"))) return null;
      if (!known.length) known = (await listTargets()) ?? [];
      const words = [...known.map((t) => ({ value: t.id, label: labelOf(t) })), ...[...new Set(known.map((t) => short(t.package)))].map((p) => ({ value: p, label: `${p} (package)` })), { value: "all", label: "all targets" }, { value: "last", label: "last results" }];
      const hits = words.filter((w) => w.value.startsWith(prefix.trim().toLowerCase()));
      return hits.length ? hits : null;
    },
    handler: async (args, ctx) => {
      const say = (msg: string, level: "info" | "warning" | "error" = "info") => ctx.ui.notify(msg, level);
      if (!existsSync(path.join(REPO, "package.json"))) return say("no pi-plugins checkout here");
      const post = (text: string, details?: unknown) => pi.sendMessage({ customType: "eval", content: text, display: true, details });

      const targets = await listTargets();
      if (!targets?.length) return say(`could not list the eval targets (npm run -s eval -- --list --json failed in ${REPO})`, "error");
      known = targets;
      const ids = targets.map((t) => t.id);
      const packages = new Set(targets.flatMap((t) => [t.package, short(t.package)]));
      const usage = `usage: /eval [last] [${["all", "replays", "hand-written", "<package>", "<id>"].join("|")}]... (ids: ${ids.join(", ")})`;

      // What to do: from the arguments, else from the picker.
      let mode: "run" | "last" = "run";
      let selected: string[] = [];
      let label = "";
      const words = args.trim().toLowerCase().split(/\s+/u).filter(Boolean);
      if (words.length) {
        const chosen = new Set<string>();
        for (const word of words) {
          if (word === "last") mode = "last";
          else if (word === "all") ids.forEach((i) => chosen.add(i));
          else if (word === "replays" || word === "hand-written") targets.filter((t) => t.kind === (word === "replays" ? "replay" : "cases")).forEach((t) => chosen.add(t.id));
          else if (ids.includes(word)) chosen.add(word);
          else if (packages.has(word) || packages.has(`pi-${word}`)) targets.filter((t) => short(t.package) === short(word)).forEach((t) => chosen.add(t.id));
          else return say(`unknown eval target or package: ${word}\n${usage}`, "error");
        }
        selected = [...chosen];
        label = words.join(" ");
      } else {
        const ordered = [...targets].sort((a, b) => a.package.localeCompare(b.package) || a.id.localeCompare(b.id));
        const options = new Map<string, () => void>();
        for (const t of ordered) options.set(labelOf(t), () => ((selected = [t.id]), (label = t.id)));
        options.set("all replays", () => ((selected = targets.filter((t) => t.kind === "replay").map((t) => t.id)), (label = "all replays")));
        options.set("all hand-written", () => ((selected = targets.filter((t) => t.kind === "cases").map((t) => t.id)), (label = "all hand-written")));
        options.set("last results", () => ((mode = "last"), (selected = ids), (label = "last results")));
        const picked = await ctx.ui.select("Eval", [...options.keys()]);
        if (!picked || !options.has(picked)) return;
        options.get(picked)!();
      }

      if (mode === "last") {
        const wanted = selected.length ? selected : ids;
        const found = await lastOf(wanted);
        if (!found) return post(`could not read results (npm run -s eval -- --last --json failed in ${REPO}).`);
        const recorded = wanted.filter((id) => found[id]?.last);
        const empty = wanted.filter((id) => !found[id]?.last);
        const parts = recorded.map((id) => summarize(id, found[id]!));
        if (empty.length) parts.push(`No recorded runs yet: ${empty.join(", ")}.`);
        return post(parts.join("\n\n"));
      }

      if (!selected.length) return say(`nothing to run for ${label || "that selection"}`, "warning");
      if (running) return say(`an eval is already running (${running.target}, ${Math.round((Date.now() - running.started) / 1000)}s); wait for it`, "warning");

      // Dry run: free. EVAL_COMPARE=1 so the estimate counts what the live run will do.
      say(`/eval: dry run for ${label} (no Jev calls)...`);
      const env = { ...process.env, EVAL_COMPARE: "1" };
      const dry = await runner(["--dry", ...selected, "--json"], env);
      let plan: Dry;
      try {
        plan = JSON.parse(dry.stdout) as Dry;
      } catch {
        return say(`dry run failed (exit ${dry.code}): ${stripAnsi(dry.stderr || dry.stdout).trim().slice(-600) || "no output"}`, "error");
      }
      const broken = Object.entries(plan.targets).filter(([, t]) => t.error);
      if (broken.length) return say(`dry run failed for ${broken.map(([id, t]) => `${id}: ${t.error}`).join("; ")}`, "error");
      const keyMissing = !process.env.TYPESAFE_API_KEY?.trim();
      const question = [
        `Eval ${label}: ${selected.length} target${selected.length === 1 ? "" : "s"}, seed ${plan.seed ?? "none (no sessions sampled)"}, ${plan.sessions.length} sessions, ${plan.totalCalls} paid Jev calls in total.`,
        ...Object.entries(plan.targets).map(([id, t]) => `  ${id} (${t.kind}): ${t.calls ?? 0} calls${t.notes ? `, ${t.notes}` : ""}`),
        `Estimated spend (an estimate; ${plan.estimate.note}): ${usd(plan.estimate.usd.low)} to ${usd(plan.estimate.usd.high)}.`,
        "This bills the TypeSafe account (TYPESAFE_API_KEY), not the Claude or Codex subscriptions.",
        keyMissing ? "TYPESAFE_API_KEY is NOT set in pi's environment, so the evals would skip themselves." : "TYPESAFE_API_KEY is set.",
        "The run is in the background; ending this pi session may kill it.",
      ].join("\n");

      if (keyMissing) return say(`${question}\nSet TYPESAFE_API_KEY and restart pi to run it.`, "warning");
      if (!ctx.hasUI) return say(`${question}\nNeeds an interactive session to confirm.`, "warning");
      const answer = await ctx.ui.select(question, ["Run it", "Cancel"]);
      if (answer !== "Run it") return say("/eval: cancelled, nothing was spent");

      // Live run, the runner takes the targets one after the other, in the background.
      const liveEnv: NodeJS.ProcessEnv = { ...env, ...(plan.seed === null ? {} : { EVAL_SEED: String(plan.seed) }) }; // the sample that was confirmed
      const logDir = mkdtempSync(path.join(os.tmpdir(), "pi-eval-"));
      const logFile = path.join(logDir, "run.log"); // the runner's report (stderr under --json)
      const jsonFile = path.join(logDir, "result.json"); // the one JSON object (stdout)
      running = { target: label, started: Date.now() };
      say(`/eval: started ${label} in the background (${plan.totalCalls} calls, ${usd(plan.estimate.usd.low)} to ${usd(plan.estimate.usd.high)} estimated). Logs in ${logDir}. Ending this session may kill it.`);
      const tick = setInterval(() => ctx.ui.setStatus("eval", `eval ${running?.target}: ${Math.round((Date.now() - (running?.started ?? Date.now())) / 1000)}s`), 5_000);
      tick.unref?.();

      void (async () => {
        try {
          const before = await lastOf(selected);
          const out = openSync(jsonFile, "a");
          const err = openSync(logFile, "a");
          const code = await new Promise<number | null>((resolve) => {
            // No shell: argv only. The runner prints its own tables; --json sends them to stderr.
            const child = spawn("npm", ["run", "-s", "eval", "--", ...selected, "--json"], { cwd: REPO, env: liveEnv, stdio: ["ignore", out, err] });
            running = { ...running!, child };
            child.on("error", () => resolve(null));
            child.on("close", (c) => resolve(c));
          });
          closeSync(out);
          closeSync(err);
          const read = (file: string) => {
            try {
              return stripAnsi(readFileSync(file, "utf8")).trim();
            } catch {
              return "";
            }
          };
          let result: Live | undefined;
          try {
            result = JSON.parse(read(jsonFile)) as Live;
          } catch {}
          const after = await lastOf(selected);
          const parts: string[] = [];
          if (result?.skipped) parts.push(`Skipped: ${result.reason}`);
          for (const id of selected) {
            const o = result?.targets?.[id];
            const l = after?.[id];
            const fresh = l?.last && l.last.at !== before?.[id]?.last?.at;
            const status = o ? `${o.pass ? "PASS" : "FAIL"}${o.error ? ` (${o.error})` : ""}, ${usd(o.spend)} over ${o.calls} calls` : "no outcome";
            const diff = !l ? "Could not read the results history." : fresh ? summarize(id, l) : `No new result was recorded (the eval skipped, failed, or does not record); showing what is stored:\n${summarize(id, l)}`;
            parts.push(`${id}: ${status}\n${diff}`);
          }
          const total = result && result.spend !== undefined ? `\n\nTotal ${usd(result.spend)} over ${result.calls} calls, seed ${result.seed ?? "-"}.` : "";
          post(`/eval ${label} finished (exit ${code ?? "spawn error"}), full log: ${logFile}\n\n${tail(read(logFile), MAX_POST)}\n\n${parts.join("\n\n")}${total}`, { targets: selected, code, logFile, jsonFile });
          say(`/eval ${label} finished (exit ${code ?? "spawn error"})`, code === 0 ? "info" : "error");
        } finally {
          clearInterval(tick);
          ctx.ui.setStatus("eval", undefined);
          running = undefined;
        }
      })();
    },
  });
}
