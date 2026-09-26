// A display-only footer. No model requests, editor replacement, or prompt
// modifications. The only credential it touches is Pi's own Codex OAuth token,
// obtained from Pi's model registry and sent solely to ChatGPT's usage endpoint
// (the one Codex CLI's /status uses). The existing symlink activates changes
// with /reload.
import { execFile, type ChildProcess } from "node:child_process";
import { readFile, stat } from "node:fs/promises";
import { homedir } from "node:os";
import path from "node:path";
import { stripVTControlCharacters } from "node:util";
import type { ExtensionAPI, ExtensionContext, Theme } from "@earendil-works/pi-coding-agent";
import { truncateToWidth, visibleWidth, wrapTextWithAnsi } from "@earendil-works/pi-tui";

const STATE_KEY = "personal-status-footer";
const QUOTA_STALE_MS = 10 * 60_000;
const GIT_TTL_MS = 3_000;
const TICK_MS = 15_000;
// Codex CLI's own /status source. Hardcoded so the token never follows a custom
// provider baseUrl anywhere else.
const CODEX_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage";
const CODEX_TTL_MS = 5 * 60_000;
const CODEX_ACTIVE_TTL_MS = 60_000;
const CODEX_JWT_CLAIM = "https://api.openai.com/auth";

type RecordValue = Record<string, unknown>;
export type Paint = Pick<Theme, "fg" | "bold">;
export interface Totals {
  input: number; output: number; cacheRead: number; cacheWrite: number;
  cost: number; compactions: number; started: number;
}
export interface QuotaWindow { label: string; used: number; reset?: number }
export interface Quota {
  source: string; updated: number; windows: QuotaWindow[];
  extra?: { enabled: boolean; used?: number; limit?: number; currency?: string };
}
export interface GitInfo {
  branch?: string; project?: string; worktree?: boolean;
  staged: number; changed: number; untracked: number; conflicts: number;
  ahead: number; behind: number; added: number; removed: number;
  unavailable?: boolean;
}
export interface Snapshot {
  cwd: string; model: string; provider: string; thinking?: string; oauth: boolean;
  sessionName?: string; phase?: string; queued: boolean;
  context: { tokens: number | null; contextWindow: number; percent: number | null };
  totals: Totals; cacheHit?: number; git: GitInfo;
  quotas: Quota[]; unavailableQuota?: string; statuses: string[]; now: number;
}

const record = (value: unknown): RecordValue =>
  value !== null && typeof value === "object" && !Array.isArray(value) ? value as RecordValue : {};
const number = (value: unknown): number | undefined =>
  typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : undefined;
export const clean = (value: string): string => stripVTControlCharacters(value).replace(/[\x00-\x1f\x7f-\x9f]/g, " ").trim();
const timestamp = (value: unknown): number | undefined => {
  const result = typeof value === "string" ? Date.parse(value) : number(value);
  return result !== undefined && Number.isFinite(result) ? result : undefined;
};
export function tokens(n: number): string {
  if (n >= 1e6) return `${+(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${+(n / 1e3).toFixed(1)}k`;
  return `${Math.round(n)}`;
}
export const duration = (ms: number): string => {
  const mins = Math.max(0, Math.ceil(ms / 60_000));
  if (mins >= 1440) return `${Math.floor(mins / 1440)}d${Math.floor(mins % 1440 / 60)}h`;
  if (mins >= 60) return `${Math.floor(mins / 60)}h${mins % 60}m`;
  return `${mins}m`;
};
const money = (n: number): string => `$${n.toFixed(n > 0 && n < 0.01 ? 3 : 2)}`;
function heat(pct: number): "accent" | "warning" | "error" {
  if (pct >= 90) return "error";
  if (pct >= 70) return "warning";
  return "accent";
}
const emptyGit = (): GitInfo => ({ staged: 0, changed: 0, untracked: 0, conflicts: 0, ahead: 0, behind: 0, added: 0, removed: 0 });

// Match Pi's whole-session accounting, including abandoned branches and usage
// that never becomes a message (warming), plus tool and summary usage.
export function collectTotals(entries: readonly unknown[], now: number): Totals {
  const totals: Totals = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0, compactions: 0, started: now };
  for (const raw of entries) {
    const entry = record(raw);
    const message = record(entry.message);
    const at = timestamp(entry.timestamp) ?? timestamp(message.timestamp);
    if (at !== undefined) totals.started = Math.min(totals.started, at);
    if (entry.type === "compaction") totals.compactions++;
    let rawUsage: unknown;
    if (entry.type === "usage" || entry.type === "compaction" || entry.type === "branch_summary") rawUsage = entry.usage;
    else if (message.role === "assistant" || message.role === "toolResult") rawUsage = message.usage;
    const usage = record(rawUsage);
    for (const key of ["input", "output", "cacheRead", "cacheWrite"] as const) totals[key] += number(usage[key]) ?? 0;
    totals.cost += number(record(usage.cost).total) ?? 0;
  }
  return totals;
}

export function latestCacheHit(entries: readonly unknown[], provider: string, model: string): number | undefined {
  for (let i = entries.length - 1; i >= 0; i--) {
    const message = record(record(entries[i]).message);
    if (message.role !== "assistant") continue;
    // Never carry a cache reading across a model/provider change.
    if (message.provider !== provider || message.model !== model) return undefined;
    const usage = record(message.usage);
    const read = number(usage.cacheRead) ?? 0;
    const prompt = (number(usage.input) ?? 0) + read + (number(usage.cacheWrite) ?? 0);
    if (prompt > 0) return 100 * read / prompt;
  }
  return undefined;
}

export function parseClaudeQuota(raw: unknown, updated: number): Quota {
  const data = record(raw);
  const windows: QuotaWindow[] = [];
  const add = (label: string, used: unknown, reset: unknown) => {
    const pct = number(used);
    if (pct !== undefined) windows.push({ label: clean(label), used: pct, reset: timestamp(reset) });
  };
  const limits = Array.isArray(data.limits) ? data.limits.map(record) : [];
  for (const [key, kind, label] of [["five_hour", "session", "5h"], ["seven_day", "weekly_all", "week"]]) {
    const flat = record(data[key]);
    const limit = limits.find((item) => item.kind === kind);
    add(label, flat.utilization ?? limit?.percent, flat.resets_at ?? limit?.resets_at);
  }
  for (const limit of limits) {
    if (limit.kind !== "weekly_scoped") continue;
    const scope = record(record(limit.scope).model);
    if (typeof scope.display_name === "string") add(scope.display_name, limit.percent, limit.resets_at);
  }
  // These API fields are percentage points. 0.5 means 0.5%, never guess 50%.
  const extra = record(data.extra_usage);
  const spend = record(data.spend);
  const used = record(spend.used), cap = record(spend.limit);
  const exponent = number(used.exponent) ?? number(extra.decimal_places) ?? 2;
  const capExponent = number(cap.exponent) ?? exponent;
  const usedMinor = number(used.amount_minor) ?? number(extra.used_credits);
  const capMinor = number(cap.amount_minor) ?? number(extra.monthly_limit);
  const enabled = typeof spend.enabled === "boolean" ? spend.enabled : extra.is_enabled;
  const currency = used.currency ?? extra.currency;
  const quota: Quota = { source: "Claude acct", updated, windows };
  if (typeof enabled === "boolean") quota.extra = {
    enabled,
    used: usedMinor === undefined ? undefined : usedMinor / 10 ** exponent,
    limit: capMinor === undefined ? undefined : capMinor / 10 ** capExponent,
    currency: typeof currency === "string" ? clean(currency) : undefined,
  };
  return quota;
}

export function codexWindowLabel(seconds: number | undefined, fallback: string): string {
  if (!seconds) return fallback;
  if (seconds === 604_800) return "week";
  const mins = Math.round(seconds / 60);
  if (mins % 1440 === 0) return `${mins / 1440}d`;
  return mins % 60 === 0 ? `${mins / 60}h` : `${mins}m`;
}

// ChatGPT-plan usage (`GET /backend-api/wham/usage`). used_percent is already
// percentage points; reset_at is epoch seconds. Additional limits (named pools
// such as a reserve model) keep their API names, not a hardcoded list.
export function parseCodexUsage(raw: unknown, now: number): Quota {
  const data = record(raw);
  const windows: QuotaWindow[] = [];
  const addLimit = (limit: unknown, name?: string) => {
    const rl = record(limit);
    const found = ["primary", "secondary"]
      .map((key) => [key, record(rl[`${key}_window`])] as const)
      .filter(([, w]) => number(w.used_percent) !== undefined);
    for (const [key, w] of found) {
      const label = codexWindowLabel(number(w.limit_window_seconds), key);
      const at = number(w.reset_at), after = number(w.reset_after_seconds);
      let reset: number | undefined;
      if (at !== undefined) reset = at * 1000;
      else if (after !== undefined) reset = now + after * 1000;
      let shown = label;
      if (name) shown = found.length > 1 ? `${name} ${label}` : name;
      windows.push({ label: clean(shown), used: number(w.used_percent) ?? 0, reset });
    }
  };
  addLimit(data.rate_limit);
  const extras = Array.isArray(data.additional_rate_limits) ? data.additional_rate_limits.map(record) : [];
  for (const item of extras) if (typeof item.limit_name === "string") addLimit(item.rate_limit, item.limit_name);
  return { source: "Codex acct", updated: now, windows };
}

// The ChatGPT account id Pi itself sends with Codex requests lives in the token.
export function codexAccountId(token: string): string | undefined {
  try {
    const payload = JSON.parse(Buffer.from(token.split(".")[1] ?? "", "base64url").toString("utf8"));
    const id = record(record(payload)[CODEX_JWT_CLAIM]).chatgpt_account_id;
    return typeof id === "string" && id ? id : undefined;
  } catch { return undefined; }
}

// Header snapshots cover only the main limit; keep named pools from the last
// usage fetch rather than dropping them whenever a response arrives.
export function mergeQuota(base: Quota | undefined, update: Quota): Quota {
  if (!base) return update;
  const fresh = new Map(update.windows.map((w) => [w.label, w]));
  const windows = base.windows.map((w) => fresh.get(w.label) ?? w);
  for (const w of update.windows) if (!base.windows.some((old) => old.label === w.label)) windows.push(w);
  return { ...base, updated: Math.max(base.updated, update.updated), windows };
}

// Passive, tied to the actual Pi request. Only the SSE transport exposes these
// headers; Pi's default WebSocket transport does not, hence the usage fetch.
export function parseCodexHeaders(headers: Record<string, string>, now: number): Quota | undefined {
  const values = Object.fromEntries(Object.entries(headers).map(([k, v]) => [k.toLowerCase(), v]));
  const windows: QuotaWindow[] = [];
  for (const key of ["primary", "secondary"]) {
    const raw = values[`x-codex-${key}-used-percent`];
    if (raw === undefined || raw.trim() === "") continue;
    const used = number(Number(raw));
    if (used === undefined) continue;
    const minsRaw = values[`x-codex-${key}-window-minutes`];
    const mins = minsRaw ? number(Number(minsRaw)) : undefined;
    const label = codexWindowLabel(mins === undefined ? undefined : mins * 60, key);
    const resetRaw = values[`x-codex-${key}-reset-at`];
    const afterRaw = values[`x-codex-${key}-reset-after-seconds`];
    const at = resetRaw ? number(Number(resetRaw)) : undefined;
    const after = afterRaw ? number(Number(afterRaw)) : undefined;
    let reset: number | undefined;
    if (after !== undefined) reset = now + after * 1000;
    if (at !== undefined) reset = at * 1000;
    windows.push({ label, used, reset });
  }
  return windows.length ? { source: "Codex acct", updated: now, windows } : undefined;
}

export function parseGitStatus(output: string): GitInfo {
  const git = emptyGit();
  const fields = output.split("\0");
  for (let i = 0; i < fields.length; i++) {
    const line = fields[i];
    if (line.startsWith("# branch.head ")) git.branch = line.slice(14);
    else if (line.startsWith("# branch.oid ") && !git.branch) git.branch = line.slice(13, 20);
    else if (line.startsWith("# branch.ab ")) {
      const match = /\+(\d+) -(\d+)/.exec(line);
      if (match) { git.ahead = +match[1]; git.behind = +match[2]; }
    } else if (line.startsWith("? ")) git.untracked++;
    else if (/^[12u] /.test(line)) {
      const xy = line.split(" ")[1];
      if (line[0] === "u") git.conflicts++;
      else { if (xy[0] !== ".") git.staged++; if (xy[1] !== ".") git.changed++; }
      if (line[0] === "2") i++; // A rename includes an extra NUL-delimited path.
    }
  }
  if (git.branch === "(detached)") {
    const oid = fields.find((line) => line.startsWith("# branch.oid "))?.slice(13, 20);
    git.branch = `detached:${oid ?? "HEAD"}`;
  }
  return git;
}

interface Segment { text: string; short?: string; priority: number; align?: boolean }
// Drop secondary statistics before shrinking the important gauges. Ordering
// remains stable; every final line is cell-bounded.
export function fitSegments(segments: Segment[], width: number, theme: Paint): string {
  const items = segments.filter((s) => s.text).map((s) => ({ ...s }));
  const separator = theme.fg("dim", " · ");
  const join = () => items.map((s) => s.text).join(separator);
  for (const item of [...items].sort((a, b) => a.priority - b.priority)) {
    if (visibleWidth(join()) <= width || item.priority >= 50) break;
    if (items.length > 1) items.splice(items.indexOf(item), 1);
  }
  for (const item of [...items].sort((a, b) => a.priority - b.priority)) {
    if (visibleWidth(join()) <= width) break;
    if (item.short !== undefined) item.text = item.short;
  }
  while (visibleWidth(join()) > width && items.length > 1) {
    const least = Math.min(...items.map((s) => s.priority));
    items.splice(items.findIndex((s) => s.priority === least), 1);
  }
  const split = items.findIndex((item) => item.align);
  if (split > 0 && visibleWidth(join()) <= width) {
    const left = items.slice(0, split).map((s) => s.text).join(separator);
    const right = items.slice(split).map((s) => s.text).join(separator);
    return left + " ".repeat(Math.max(1, width - visibleWidth(left) - visibleWidth(right))) + right;
  }
  return truncateToWidth(join(), Math.max(0, width), "…");
}

function gauge(theme: Paint, used: number, cells = 8): string {
  const filled = Math.round(Math.min(100, Math.max(0, used)) * cells / 100);
  return theme.fg(heat(used), "━".repeat(filled)) + theme.fg("dim", "─".repeat(cells - filled));
}
const percent = (value: number): string => `${+value.toFixed(1)}%`;
export function shortModel(value: string): string {
  return clean(value).replace(/^claude-/, "").replace(/-20\d{6}$/, "").replace(/(\d)-(\d)/g, "$1.$2");
}

export function renderFooter(snapshot: Snapshot, width: number, theme: Paint): string[] {
  if (width <= 0) return [];
  const s = snapshot, g = s.git;
  const rows: string[] = [];
  const sep = theme.fg("dim", " · ");
  const marks = [g.conflicts ? theme.fg("error", `${g.conflicts} conflicts`) : "",
    g.staged + g.changed + g.untracked ? theme.fg("warning", "modified") : "",
    g.ahead ? `${g.ahead} ahead` : "", g.behind ? `${g.behind} behind` : ""].filter(Boolean).join(", ");
  const project = theme.fg("accent", clean(g.project ?? (path.basename(s.cwd) || s.cwd)));
  let branch = g.unavailable ? "Git unavailable" : "";
  if (g.branch) branch = `${g.worktree ? "worktree" : "branch"} ${clean(g.branch)}${marks ? ` (${marks})` : ""}`;
  const branchShort = branch ? `${truncateToWidth(clean(g.branch ?? "Git unavailable"), 14)}${marks ? ` (${marks})` : ""}` : "";
  const phaseText = s.phase ? theme.fg(s.phase === "error" ? "error" : "warning", s.phase) : "";
  const model = theme.bold(theme.fg("accent", shortModel(s.model)));
  const identity = `${model}${s.thinking ? ` · ${theme.fg("muted", `reasoning ${s.thinking}`)}` : ""}`;
  rows.push(fitSegments([
    { text: project, priority: 60 },
    { text: branch, short: branchShort, priority: g.conflicts ? 110 : 70 },
    { text: s.sessionName ? theme.fg("dim", clean(s.sessionName)) : "", priority: 10 },
    { text: identity, short: model, priority: 100, align: true },
    { text: phaseText, priority: 120 },
    { text: s.queued ? theme.fg("warning", "queued") : "", priority: 115 },
  ], width, theme));

  const context = s.context.percent;
  const ctxShort = `Context ${context === null ? "unknown" : theme.fg(heat(context), percent(context))}`;
  const ctxLong = `${ctxShort}${context === null ? "" : ` used ${gauge(theme, context)}`}`;
  rows.push(fitSegments([
    { text: ctxLong, short: ctxShort, priority: 100 },
    { text: `Est. session cost ${money(s.totals.cost)}`, short: `Est. cost ${money(s.totals.cost)}`, priority: 80, align: true },
  ], width, theme));

  for (const quota of s.quotas) {
    const age = Math.max(0, s.now - quota.updated);
    const expired = quota.windows.some((w) => w.reset !== undefined && w.reset <= s.now);
    const stale = age >= QUOTA_STALE_MS || expired;
    const windows = quota.windows.map((w): Segment => {
      let reset = "";
      if (w.reset !== undefined) reset = w.reset <= s.now ? " reset due" : ` (resets in ${duration(w.reset - s.now)})`;
      const val = `${clean(w.label)} ${theme.fg(stale ? "muted" : heat(w.used), percent(w.used))} used`;
      return { text: `${val}${reset}`, short: val,
        priority: 50 + Math.min(100, w.used) };
    });
    const extra = quota.extra;
    // An exhausted historical extra-usage pool is not an alert if extra is off.
    let extraText = "";
    if (extra?.enabled) {
      extraText = "extra usage on";
      if (extra.enabled && extra.used !== undefined) {
        const amount = extra.currency === "USD" ? money(extra.used) : `${extra.used.toFixed(2)} ${extra.currency ?? "?"}`;
        extraText += ` ${amount}${extra.limit === undefined ? "" : `/${extra.limit.toFixed(0)}`}`;
      }
    }
    const extraColor = extra?.enabled ? "warning" : "dim";
    const staleText = `stale ${duration(age)}${expired ? " / reset due" : ""}`;
    const segments: Segment[] = [
      { text: theme.fg("muted", quota.source), priority: 200 },
      { text: stale ? theme.fg("warning", staleText) : "", short: stale ? theme.fg("warning", "stale") : "", priority: 210 },
      ...windows,
      { text: extraText ? theme.fg(extraColor, extraText) : "", short: extra?.enabled ? "extra on" : "", priority: extra?.enabled ? 75 : 5 },
    ];
    rows.push(fitSegments(segments, width, theme));
  }
  if (s.unavailableQuota) rows.push(truncateToWidth(theme.fg("dim", `${s.unavailableQuota} · limits unavailable`), width));
  // Statuses remain owned by their publishers. Wrap instead of silently dropping
  // plan mode, background failures, or other extension notices at the right edge.
  if (s.statuses.length) {
    const text = s.statuses.map((status) => status.replace(/[\r\n\t]/g, " ")).join(sep);
    rows.push(...wrapTextWithAnsi(text, width));
  }
  return rows.map((row) => truncateToWidth(row, width));
}

export default function statusFooter(pi: ExtensionAPI): void {
  let ctx: ExtensionContext | undefined;
  let active = false, enabled = true, showAll = false, generation = 0;
  let timer: ReturnType<typeof setInterval> | undefined;
  let requestRender: (() => void) | undefined;
  let git = emptyGit(), gitBusy = false, gitChecked = 0;
  let quotaBusy = false, quotaChecked = 0;
  let codexBusy = false, codexChecked = 0, codexAbort: AbortController | undefined;
  let claude: Quota | undefined, codex: Quota | undefined;
  let phase: string | undefined;
  let totals = collectTotals([], Date.now()), cacheHit: number | undefined;
  let lastTmuxState: string | undefined;
  const children = new Set<ChildProcess>();
  const home = homedir();
  const bin = path.join(home, ".local", "bin");
  const cacheFile = path.join(process.env.CLAUDE_STATUSLINE_CACHE_DIR ?? path.join(process.env.XDG_CACHE_HOME ?? path.join(home, ".cache"), "claude-statusline"), "oauth-usage.json");

  const exec = (file: string, args: string[], cwd?: string): Promise<string | undefined> => new Promise((resolve) => {
    const child = execFile(file, args, { cwd, timeout: 4_000, maxBuffer: 2 * 1024 * 1024, env: { ...process.env, GIT_OPTIONAL_LOCKS: "0" } }, (error, stdout) => {
      children.delete(child);
      resolve(error ? undefined : stdout);
    });
    children.add(child);
  });
  const setTmux = (state: string) => {
    if (!process.env.TMUX || lastTmuxState === state) return;
    lastTmuxState = state;
    void exec(path.join(bin, "tmux-agent-state"), [state]);
  };
  const account = () => {
    if (!ctx) return;
    totals = collectTotals(ctx.sessionManager.getEntries(), Date.now());
    cacheHit = latestCacheHit(ctx.sessionManager.getBranch(), ctx.model?.provider ?? "", ctx.model?.id ?? "");
  };
  const updateGit = async (force = false) => {
    if (!active || !ctx || gitBusy || (!force && Date.now() - gitChecked < GIT_TTL_MS)) return;
    gitBusy = true; gitChecked = Date.now();
    const epoch = generation, cwd = ctx.cwd;
    try {
      const [status, roots, diff] = await Promise.all([
        exec("git", ["status", "--porcelain=v2", "--branch", "-z"], cwd),
        exec("git", ["rev-parse", "--show-toplevel", "--absolute-git-dir", "--git-common-dir"], cwd),
        exec("git", ["diff", "--shortstat", "HEAD", "--"], cwd),
      ]);
      if (!active || epoch !== generation) return;
      git = status === undefined ? { ...emptyGit(), unavailable: roots !== undefined } : parseGitStatus(status);
      if (roots) {
        const [root, gitDir, commonDir] = roots.trim().split("\n");
        git.worktree = path.resolve(cwd, commonDir) !== path.resolve(cwd, gitDir);
        git.project = git.worktree ? path.basename(path.dirname(path.resolve(cwd, commonDir))) : path.basename(root);
        const sub = path.relative(root, cwd);
        if (sub) git.project += `/${sub}`;
      }
      git.added = +(diff?.match(/(\d+) insertion/)?.[1] ?? 0);
      git.removed = +(diff?.match(/(\d+) deletion/)?.[1] ?? 0);
      requestRender?.();
    } catch {
      if (active && epoch === generation) { git = { ...emptyGit(), unavailable: true }; requestRender?.(); }
    } finally { if (epoch === generation) gitBusy = false; }
  };
  const updateQuota = async (force = false) => {
    if (!active || !ctx || quotaBusy || (!force && Date.now() - quotaChecked < 60_000)) return;
    quotaBusy = true; quotaChecked = Date.now();
    const epoch = generation;
    try {
      // Keep the existing shared refresher/lock; it fetches asynchronously and
      // stores no credentials in this extension. Never parse its rendered text.
      if (ctx.model?.provider === "anthropic" || showAll) await exec(path.join(bin, "agent-status"), ["--plain", "--width", "0"]);
      try {
        const [text, meta] = await Promise.all([readFile(cacheFile, "utf8"), stat(cacheFile)]);
        const parsed = parseClaudeQuota(JSON.parse(text), meta.mtimeMs);
        if (active && epoch === generation) claude = parsed.windows.length ? parsed : undefined;
      } catch { /* Keep last good snapshot; its timestamp makes staleness visible. */ }
      if (active && epoch === generation) requestRender?.();
      if (active && epoch === generation && process.env.HERDR_ENV === "1") await exec(path.join(bin, "herdr-agent-status"), []);
    } finally { if (epoch === generation) quotaBusy = false; }
  };
  // Same OAuth token and account Pi sends with each Codex request; Pi's registry
  // refreshes it. A non-JWT key (no ChatGPT account) simply yields no reading.
  const updateCodex = async (maxAge = CODEX_TTL_MS) => {
    if (!active || !ctx || codexBusy || Date.now() - codexChecked < maxAge) return;
    if (ctx.model?.provider !== "openai-codex" && !showAll) return;
    codexBusy = true; codexChecked = Date.now();
    const epoch = generation, controller = new AbortController();
    codexAbort = controller;
    const timeout = setTimeout(() => controller.abort(), 5_000);
    try {
      const token = await ctx.modelRegistry.getApiKeyForProvider("openai-codex");
      const account = token ? codexAccountId(token) : undefined;
      if (!token || !account || !active || epoch !== generation) return;
      const response = await fetch(CODEX_USAGE_URL, {
        headers: { Authorization: `Bearer ${token}`, "chatgpt-account-id": account, originator: "pi", accept: "application/json" },
        signal: controller.signal,
      });
      if (!response.ok) return;
      const parsed = parseCodexUsage(await response.json(), Date.now());
      if (active && epoch === generation && parsed.windows.length) { codex = parsed; requestRender?.(); }
    } catch { /* Keep last good snapshot; its timestamp makes staleness visible. */ } finally {
      clearTimeout(timeout);
      if (codexAbort === controller) codexAbort = undefined;
      if (epoch === generation) codexBusy = false;
    }
  };
  const snapshot = (branch: string | null, statuses: ReadonlyMap<string, string>): Snapshot => {
    if (!ctx) throw new Error("Footer rendered outside its session lifecycle");
    const current = ctx;
    const provider = current.model?.provider ?? "no provider";
    const quotas: Quota[] = [];
    let unavailableQuota: string | undefined;
    if (provider === "anthropic" || showAll) {
      if (claude) quotas.push(claude); else unavailableQuota = "Claude acct";
    }
    if (provider === "openai-codex") {
      if (codex) quotas.unshift(codex);
      else unavailableQuota = unavailableQuota ? `${unavailableQuota} / Codex acct` : "Codex acct";
    } else if (showAll && codex) quotas.push(codex);
    return {
      cwd: current.cwd, provider, model: current.model?.id ?? "no model",
      thinking: current.model?.reasoning ? pi.getThinkingLevel() : undefined,
      oauth: current.model ? current.modelRegistry.isUsingOAuth(current.model) : false,
      sessionName: pi.getSessionName(), phase, queued: current.hasPendingMessages(),
      context: current.getContextUsage() ?? { tokens: null, contextWindow: current.model?.contextWindow ?? 0, percent: null },
      totals, cacheHit, git: { ...git, branch: git.branch ?? branch ?? undefined },
      quotas, unavailableQuota,
      // Use the flat Nerd Font plug for MCP; preserve its theme color and text.
      statuses: [...statuses.entries()].sort(([a], [b]) => a.localeCompare(b))
        .map(([key, text]) => key === "mcp" ? text.replace(/\u{1f50c}[\ufe0e\ufe0f]?/u, "\uf1e6") : text),
      now: Date.now(),
    };
  };
  const attach = () => {
    if (!active || !ctx) return;
    // Retire the previous version's plain Anthropic-only status segment.
    ctx.ui.setStatus("usage", undefined);
    if (!enabled) { ctx.ui.setFooter(undefined); return; }
    ctx.ui.setFooter((tui, theme, footerData) => {
      const render = () => tui.requestRender();
      requestRender = render;
      const unsubscribe = footerData.onBranchChange(() => { void updateGit(true); render(); });
      return {
        render(width: number) { return renderFooter(snapshot(footerData.getGitBranch(), footerData.getExtensionStatuses()), width, theme); },
        invalidate() {}, // Colors are evaluated on every render, never cached.
        dispose() { unsubscribe(); if (requestRender === render) requestRender = undefined; },
      };
    });
  };
  const stop = () => {
    active = false; generation++;
    if (timer) clearInterval(timer);
    timer = undefined;
    codexAbort?.abort(); codexAbort = undefined;
    for (const child of children) child.kill();
    children.clear();
    requestRender = undefined;
    ctx = undefined;
  };
  pi.on("session_start", (_event, context) => {
    stop();
    if (context.mode !== "tui") return;
    ctx = context; active = true;
    git = emptyGit(); claude = undefined; codex = undefined;
    gitBusy = quotaBusy = codexBusy = false; gitChecked = quotaChecked = codexChecked = 0;
    enabled = true; showAll = false; phase = undefined;
    for (const raw of context.sessionManager.getBranch()) {
      const entry = record(raw);
      if (entry.type === "custom" && entry.customType === STATE_KEY) {
        const data = record(entry.data);
        enabled = data.enabled !== false; showAll = data.showAll === true;
      }
    }
    account(); attach(); setTmux("clear");
    void updateGit(true); void updateQuota(true); void updateCodex(0);
    timer = setInterval(() => { account(); void updateGit(); void updateQuota(); void updateCodex(); requestRender?.(); }, TICK_MS);
    timer.unref();
  });
  pi.on("session_shutdown", () => { if (active) ctx?.ui.setFooter(undefined); stop(); });
  pi.on("model_select", (_event, context) => {
    if (!active) return;
    // Codex limits are per account, not per model; keep them across switches.
    ctx = context; phase = undefined;
    account(); void updateQuota(true); void updateCodex(CODEX_ACTIVE_TTL_MS); requestRender?.();
  });
  pi.on("thinking_level_select", () => requestRender?.());
  pi.on("session_info_changed", () => requestRender?.());
  pi.on("session_tree", (_event, context) => { if (active) { ctx = context; account(); requestRender?.(); } });
  pi.on("message_end", (event, context) => {
    if (!active) return;
    ctx = context; account();
    if (event.message.role === "assistant") phase = event.message.stopReason === "error" ? "error" : undefined;
    requestRender?.();
  });
  pi.on("turn_start", () => { if (active) { phase = undefined; setTmux("running"); } });
  pi.on("agent_settled", (_event, context) => {
    if (!active) return;
    ctx = context; account(); void updateGit(true); void updateQuota(); void updateCodex(CODEX_ACTIVE_TTL_MS);
    setTmux("done"); requestRender?.();
  });
  pi.on("ui_prompt_start", () => { if (active) { phase = "waiting"; setTmux("waiting"); requestRender?.(); } });
  pi.on("ui_prompt_end", () => { if (active) { phase = undefined; setTmux(ctx?.isIdle() ? "done" : "running"); requestRender?.(); } });
  pi.on("session_before_compact", () => { if (active) { phase = "compacting"; requestRender?.(); } });
  pi.on("session_compact", () => { if (active) { phase = undefined; account(); requestRender?.(); } });
  pi.on("session_compact_failed", () => { if (active) { phase = "compact failed"; requestRender?.(); } });
  pi.on("after_provider_response", (event, context) => {
    if (!active || context.model?.provider !== "openai-codex") return;
    const quota = parseCodexHeaders(event.headers, Date.now());
    if (quota) { codex = mergeQuota(codex, quota); requestRender?.(); }
  });
  pi.registerCommand("status", {
    description: "Personal footer: on, native, all (also show the other subscription account), details",
    getArgumentCompletions: (prefix) => ["on", "native", "all", "details"].filter((value) => value.startsWith(prefix)).map((value) => ({ value, label: value })),
    handler: async (args, context) => {
      if (context.mode !== "tui") return;
      const command = args.trim() || "details";
      if (command === "details") {
        const usage = context.getContextUsage();
        context.ui.notify([
          `Model: ${context.model?.provider ?? "unknown"}/${context.model?.id ?? "unknown"}; reasoning: ${pi.getThinkingLevel()}.`,
          `Context: ${usage?.tokens == null ? "unknown" : tokens(usage.tokens)} of ${tokens(usage?.contextWindow ?? context.model?.contextWindow ?? 0)} tokens; ${usage?.percent == null ? "usage unknown" : `${percent(usage.percent)} used`}. This is Pi's estimate.`,
          `Cache reuse: ${cacheHit === undefined ? "not measured" : percent(cacheHit)} of the latest measured prompt on this branch/model.`,
          `Estimated session cost: ${money(totals.cost)} across recorded assistant, tool, summary and warming usage on all branches. This is not an invoice.`,
          `Recorded tokens: ${tokens(totals.input)} input, ${tokens(totals.output)} output, ${tokens(totals.cacheRead)} cache reads, ${tokens(totals.cacheWrite)} cache writes.`,
          `Tracked Git changes: ${git.added} lines added, ${git.removed} removed. Session age: ${duration(Date.now() - totals.started)}; compactions: ${totals.compactions}.`,
          "OAuth identifies the authentication method, not guaranteed subscription billing. Git diff covers all uncommitted tracked changes, not just this agent.",
          "Claude acct comes from the shared Claude Code account cache (which can differ from Pi's account). Values are percent used; stale means >10m old or reset due.",
          "Codex acct comes from ChatGPT's usage endpoint (as Codex CLI /status), using Pi's own Codex login; polled every 5m, or 1m around turns. SSE response headers refresh it in between.",
          "/status on: active provider only; /status all: also show the other subscription account; /status native: restore Pi footer. Choice survives reload/resume in this session.",
        ].join("\n"), "info");
        return;
      }
      if (!["on", "native", "all"].includes(command)) { context.ui.notify("Usage: /status on|native|all|details", "warning"); return; }
      ctx = context; enabled = command !== "native"; showAll = command === "all";
      pi.appendEntry(STATE_KEY, { enabled, showAll });
      attach(); if (enabled) { void updateGit(true); void updateQuota(true); void updateCodex(0); }
      context.ui.notify(enabled ? "Custom footer enabled" : "Native footer restored", "info");
    },
  });
}
