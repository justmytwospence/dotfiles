// Tells herdr (and herdr-attention-queue) what pi's own herdr integration does
// not:
//
// 1. blocked: pi emits ui_prompt_start/ui_prompt_end around every blocking
//    extension dialog (ask_user_question, plan-mode questions and menus,
//    confirmations). They are forwarded as herdr:blocked pairs, which herdr's
//    pi integration turns into the blocked state. A dialog that opens while an
//    extension holds `herdr:working` is a progress view (plan-mode's live
//    planner traces), not a question: it is not forwarded until the work ends.
// 2. activity: the pane token `activity` is `blocked` while a forwarded dialog
//    or another extension's herdr:blocked hold is open, and `working` while an
//    extension holds herdr:working. herdr-attention-queue prefers it to herdr's
//    status, so a planner run started by a command shows working, and a
//    question shows blocked even when herdr reads the pane's screen.
// 3. waiting: the pane token `bg` counts background work that will wake the
//    agent: 1 while pi-subagents has async runs (its herdr:busy), plus every
//    running pi-background-tasks task with triggerOnCompletion.
//    herdr-attention-queue shows an idle agent with bg > 0 as waiting.
//
// Tokens have a 90 s TTL, are refreshed every 30 s while set, and are cleared
// when their state ends, so a crashed pi cannot leave them behind. After each
// change the bridge asks herdr-attention-queue to refresh, since token changes
// emit no plugin event.
//
// Extensions hold herdr:working with {active: true, label} and release it with
// {active: false}, like herdr:blocked.
//
// Only a TUI root session inside herdr reports. The existing symlink activates
// changes with /reload.
import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const SOURCE = "user:attention-bridge";
const BG_TOKEN = "bg";
const ACTIVITY_TOKEN = "activity";
const TTL_MS = 90_000;
const REFRESH_MS = 30_000;
const STATUS_TIMEOUT_MS = 2_000;
const REQUEST = "pi-background-tasks:request:v1";
const RESPONSE = "pi-background-tasks:response:v1";
const TERMINAL = "pi-background-tasks:terminal:v1";
const REQUEST_SCHEMA = "pi-background-tasks.extension-request.v1";
export const BLOCKED = "herdr:blocked";
export const WORKING = "herdr:working";
const REFRESH_ACTION = "attention-queue.refresh";
// A dialog is forwarded as blocked only after this grace period, so a progress
// view whose herdr:working hold starts just after it opens, or one that closes
// right as its work ends, never flashes blocked.
const GRACE_MS = 150;

export type Activity = "blocked" | "working";

export interface Report {
  bg: number;
  activity?: Activity;
}

export interface Bus {
  emit(channel: string, data: unknown): void;
  on(channel: string, handler: (data: unknown) => void): (() => void) | void;
}

export interface Task {
  id?: string;
  status?: string;
  triggerOnCompletion?: boolean;
}

/** Background tasks that will start a new turn when they finish. */
export function wakingTasks(tasks: readonly Task[]): number {
  return tasks.filter((task) => task?.status === "running" && task.triggerOnCompletion === true).length;
}

export function bgCount(subagentsBusy: boolean, tasks: readonly Task[]): number {
  return (subagentsBusy ? 1 : 0) + wakingTasks(tasks);
}

/** herdr CLI arguments that set, refresh or clear both tokens. */
export function reportArgs(pane: string, report: Report, seq: number): string[] {
  const args = ["pane", "report-metadata", pane, "--source", SOURCE, "--seq", String(seq)];
  let set = false;
  if (report.bg > 0) {
    args.push("--token", `${BG_TOKEN}=${report.bg}`);
    set = true;
  } else {
    args.push("--clear-token", BG_TOKEN);
  }
  if (report.activity) {
    args.push("--token", `${ACTIVITY_TOKEN}=${report.activity}`);
    set = true;
  } else {
    args.push("--clear-token", ACTIVITY_TOKEN);
  }
  if (set) args.push("--ttl-ms", String(TTL_MS));
  return args;
}

/** Ask pi-background-tasks for its tasks over the event bus; [] when it is absent. */
export function fetchTasks(bus: Bus, timeoutMs = STATUS_TIMEOUT_MS): Promise<Task[]> {
  return new Promise((resolve) => {
    const requestId = `attention-bridge:${randomUUID()}`;
    let off: (() => void) | void;
    const finish = (tasks: Task[]) => {
      clearTimeout(timer);
      if (typeof off === "function") off();
      resolve(tasks);
    };
    const timer = setTimeout(() => finish([]), timeoutMs);
    timer.unref?.();
    off = bus.on(RESPONSE, (frame) => {
      const response = frame as { request_id?: string; ok?: boolean; result?: { tasks?: Task[] } };
      if (response?.request_id !== requestId) return;
      finish(response.ok && Array.isArray(response.result?.tasks) ? response.result.tasks : []);
    });
    try {
      bus.emit(REQUEST, { schema_version: REQUEST_SCHEMA, request_id: requestId, operation: "status", payload: {} });
    } catch {
      finish([]);
    }
  });
}

export interface BridgeDeps {
  bus: Bus;
  report(report: Report): Promise<void> | void;
  /** Ask herdr-attention-queue to pick up a changed token now. */
  refresh?(): Promise<void> | void;
  fetch?: (bus: Bus) => Promise<Task[]>;
  /** Run fn after the grace period. */
  defer?: (fn: () => void) => void;
  setInterval?: typeof setInterval;
  clearInterval?: typeof clearInterval;
}

const OWN = "attention-bridge";

function isActive(data: unknown): boolean {
  return Boolean((data as { active?: unknown })?.active);
}

/** The bridge's state machine, separate from pi for tests. */
export function createBridge(deps: BridgeDeps) {
  const fetch = deps.fetch ?? fetchTasks;
  const defer =
    deps.defer ??
    ((fn: () => void) => {
      const timer = setTimeout(fn, GRACE_MS);
      (timer as { unref?: () => void }).unref?.();
    });
  const every = deps.setInterval ?? setInterval;
  const stopEvery = deps.clearInterval ?? clearInterval;
  let active = false;
  let busy = false;
  let bg = 0;
  // The open dialog (pi reports only the outermost one), and whether it was
  // forwarded as herdr:blocked.
  let prompt: string | undefined;
  let forwarded = false;
  let deferred = false;
  // herdr:working holds, and other extensions' herdr:blocked holds.
  let working = 0;
  let external = 0;
  let reported: Report = { bg: 0 };
  let refresh: ReturnType<typeof setInterval> | undefined;
  let chain: Promise<void> = Promise.resolve();

  const send = (report: Report, changed: boolean) => {
    // Serialize reports; each carries the state at the time it was made.
    chain = chain
      .then(async () => {
        await deps.report(report);
        if (changed) await deps.refresh?.();
      })
      .catch(() => undefined);
    return chain;
  };

  const desired = (): Report => {
    let activity: Activity | undefined = forwarded || external > 0 ? "blocked" : working > 0 ? "working" : undefined;
    // While a dialog waits out its grace period, hold the last activity.
    if (activity === undefined && deferred && prompt !== undefined) activity = reported.activity;
    return activity ? { bg, activity } : { bg };
  };

  const syncTimer = () => {
    const holding = reported.bg > 0 || reported.activity !== undefined;
    if (holding && !refresh) {
      refresh = every(() => void send(reported, false), REFRESH_MS);
      (refresh as { unref?: () => void }).unref?.();
    } else if (!holding && refresh) {
      stopEvery(refresh);
      refresh = undefined;
    }
  };

  const publish = () => {
    if (!active) return chain;
    const next = desired();
    if (next.bg === reported.bg && next.activity === reported.activity) return chain;
    reported = next;
    syncTimer();
    return send(next, true);
  };

  const emitBlocked = (data: Record<string, unknown>) => {
    try {
      deps.bus.emit(BLOCKED, { ...data, source: OWN });
    } catch {
      // A failing listener must not break the bridge.
    }
  };

  const shouldForward = () => active && prompt !== undefined && working === 0;

  /** Forward the open dialog as blocked, after the grace period, unless an extension is working. */
  const sync = () => {
    if (!shouldForward() && forwarded) {
      forwarded = false;
      emitBlocked({ active: false });
    } else if (shouldForward() && !forwarded && !deferred) {
      deferred = true;
      defer(() => {
        deferred = false;
        if (!shouldForward() || forwarded) return;
        forwarded = true;
        emitBlocked({ active: true, label: prompt });
        void publish();
      });
    }
    return publish();
  };

  const recount = async () => {
    if (!active) return;
    const count = bgCount(busy, await fetch(deps.bus));
    if (!active) return;
    bg = count;
    await publish();
  };

  return {
    get count() {
      return reported.bg;
    },
    get activity() {
      return reported.activity;
    },
    start() {
      active = true;
      return recount();
    },
    recount,
    onBusy(data: unknown) {
      busy = isActive(data);
      return recount();
    },
    onWorking(data: unknown) {
      if (isActive(data)) working += 1;
      else working = Math.max(0, working - 1);
      return sync();
    },
    /** Another extension's herdr:blocked hold; the bridge's own are tagged and skipped. */
    onBlocked(data: unknown) {
      if ((data as { source?: unknown })?.source === OWN) return chain;
      if (isActive(data)) external += 1;
      else external = Math.max(0, external - 1);
      return publish();
    },
    promptStart(label: string) {
      if (!active) return chain;
      prompt = label;
      return sync();
    },
    promptEnd() {
      if (!active || prompt === undefined) return chain;
      prompt = undefined;
      return sync();
    },
    async stop() {
      if (!active) return;
      prompt = undefined;
      working = 0;
      external = 0;
      bg = 0;
      sync();
      await publish();
      active = false;
      if (refresh) stopEvery(refresh);
      refresh = undefined;
      await chain;
    },
  };
}

export default function herdrAttentionBridge(pi: ExtensionAPI) {
  const pane = process.env.HERDR_PANE_ID;
  const bin = process.env.HERDR_BIN_PATH;
  if (process.env.HERDR_ENV !== "1" || !pane || !bin) return;

  const run = (args: string[]) =>
    new Promise<void>((resolve) => {
      execFile(bin, args, { timeout: 5_000 }, () => resolve());
    });
  const bus = pi.events as unknown as Bus;
  const bridge = createBridge({
    bus,
    report: (report) => run(reportArgs(pane, report, Date.now())),
    // Fails quietly when herdr-attention-queue is not installed.
    refresh: () => run(["plugin", "action", "invoke", REFRESH_ACTION]),
  });

  pi.events.on("herdr:busy", (data) => void bridge.onBusy(data));
  pi.events.on(WORKING, (data) => void bridge.onWorking(data));
  pi.events.on(BLOCKED, (data) => void bridge.onBlocked(data));
  pi.events.on(TERMINAL, () => void bridge.recount());
  pi.on("session_start", (_event, ctx) => {
    // TUI only: RPC and print modes (subagents, planners) have no pane of their own.
    if (ctx?.mode !== "tui") return;
    void bridge.start();
  });
  pi.on("tool_execution_end", () => void bridge.recount());
  pi.on("agent_settled", () => void bridge.recount());
  pi.on("ui_prompt_start", (event) => void bridge.promptStart(event.title ?? event.kind));
  pi.on("ui_prompt_end", () => void bridge.promptEnd());
  pi.on("session_shutdown", () => bridge.stop());
}
