// Tells herdr (and herdr-attention-queue) two things pi's own herdr
// integration does not:
//
// 1. blocked: pi emits ui_prompt_start/ui_prompt_end around every blocking
//    extension dialog (ask_user_question, plan-mode questions and menus,
//    confirmations). They are forwarded as herdr:blocked pairs, which herdr's
//    pi integration turns into the blocked state.
// 2. waiting: the pane token `bg` counts background work that will wake the
//    agent: 1 while pi-subagents has async runs (its herdr:busy), plus every
//    running pi-background-tasks task with triggerOnCompletion. The token has a
//    90 s TTL, is refreshed every 30 s, and is cleared at 0, so a crashed pi
//    cannot leave it behind. herdr-attention-queue shows an idle agent with
//    bg > 0 as waiting.
//
// Only a TUI root session inside herdr reports. The existing symlink activates
// changes with /reload.
import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const SOURCE = "user:attention-bridge";
const TOKEN = "bg";
const TTL_MS = 90_000;
const REFRESH_MS = 30_000;
const STATUS_TIMEOUT_MS = 2_000;
const REQUEST = "pi-background-tasks:request:v1";
const RESPONSE = "pi-background-tasks:response:v1";
const TERMINAL = "pi-background-tasks:terminal:v1";
const REQUEST_SCHEMA = "pi-background-tasks.extension-request.v1";

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

/** herdr CLI arguments that set, refresh or clear the bg token. */
export function reportArgs(pane: string, count: number, seq: number): string[] {
  const base = ["pane", "report-metadata", pane, "--source", SOURCE, "--seq", String(seq)];
  return count > 0
    ? [...base, "--token", `${TOKEN}=${count}`, "--ttl-ms", String(TTL_MS)]
    : [...base, "--clear-token", TOKEN];
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
  report(count: number): Promise<void> | void;
  fetch?: (bus: Bus) => Promise<Task[]>;
  setInterval?: typeof setInterval;
  clearInterval?: typeof clearInterval;
}

/** The bridge's state machine, separate from pi for tests. */
export function createBridge(deps: BridgeDeps) {
  const fetch = deps.fetch ?? fetchTasks;
  const every = deps.setInterval ?? setInterval;
  const stopEvery = deps.clearInterval ?? clearInterval;
  let active = false;
  let busy = false;
  let blocked = 0;
  let reported = 0;
  let refresh: ReturnType<typeof setInterval> | undefined;
  let chain: Promise<void> = Promise.resolve();

  const send = (count: number) => {
    // Serialize reports; each carries the count at the time it runs.
    chain = chain.then(() => deps.report(count)).catch(() => undefined);
    return chain;
  };

  const syncTimer = () => {
    if (reported > 0 && !refresh) {
      refresh = every(() => void send(reported), REFRESH_MS);
      (refresh as { unref?: () => void }).unref?.();
    } else if (reported === 0 && refresh) {
      stopEvery(refresh);
      refresh = undefined;
    }
  };

  const recount = async () => {
    if (!active) return;
    const count = bgCount(busy, await fetch(deps.bus));
    if (!active || count === reported) return;
    reported = count;
    syncTimer();
    await send(count);
  };

  return {
    get count() {
      return reported;
    },
    get blocked() {
      return blocked;
    },
    start() {
      active = true;
      return recount();
    },
    recount,
    onBusy(data: unknown) {
      busy = Boolean((data as { active?: unknown })?.active);
      return recount();
    },
    promptStart(label: string) {
      if (!active) return;
      blocked += 1;
      deps.bus.emit("herdr:blocked", { active: true, label });
    },
    promptEnd() {
      if (!active || blocked === 0) return;
      blocked -= 1;
      deps.bus.emit("herdr:blocked", { active: false });
    },
    async stop() {
      if (!active) return;
      while (blocked > 0) this.promptEnd();
      active = false;
      if (refresh) stopEvery(refresh);
      refresh = undefined;
      if (reported > 0) {
        reported = 0;
        await send(0);
      }
    },
  };
}

export default function herdrAttentionBridge(pi: ExtensionAPI) {
  const pane = process.env.HERDR_PANE_ID;
  const bin = process.env.HERDR_BIN_PATH;
  if (process.env.HERDR_ENV !== "1" || !pane || !bin) return;

  const bus = pi.events as unknown as Bus;
  const bridge = createBridge({
    bus,
    report: (count) =>
      new Promise<void>((resolve) => {
        execFile(bin, reportArgs(pane, count, Date.now()), { timeout: 5_000 }, () => resolve());
      }),
  });

  pi.events.on("herdr:busy", (data) => void bridge.onBusy(data));
  pi.events.on(TERMINAL, () => void bridge.recount());
  pi.on("session_start", (_event, ctx) => {
    // TUI only: RPC and print modes (subagents, planners) have no pane of their own.
    if (ctx?.mode !== "tui") return;
    void bridge.start();
  });
  pi.on("tool_execution_end", () => void bridge.recount());
  pi.on("agent_settled", () => void bridge.recount());
  pi.on("ui_prompt_start", (event) => bridge.promptStart(event.title ?? event.kind));
  pi.on("ui_prompt_end", () => bridge.promptEnd());
  pi.on("session_shutdown", () => bridge.stop());
}
