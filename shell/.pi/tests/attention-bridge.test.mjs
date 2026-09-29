import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { test } from "node:test";

const root = process.env.PI_PACKAGE_DIR;
assert.ok(root, "Set PI_PACKAGE_DIR to the installed @earendil-works/pi-coding-agent directory");
const entry = fileURLToPath(new URL("../agent/extensions/herdr-attention-bridge.ts", import.meta.url));
const { createJiti } = await import(pathToFileURL(path.join(root, "dist/core/extensions/jiti-loader.js")));
const jiti = createJiti(import.meta.url, { moduleCache: false });
const mod = await jiti.import(entry);

function bus() {
  const handlers = new Map();
  const emitted = [];
  return {
    emitted,
    emit(channel, data) {
      emitted.push([channel, data]);
      for (const handler of handlers.get(channel) ?? []) handler(data);
    },
    on(channel, handler) {
      handlers.set(channel, [...(handlers.get(channel) ?? []), handler]);
      return () => handlers.set(channel, (handlers.get(channel) ?? []).filter((h) => h !== handler));
    },
  };
}

function bridge(tasks = []) {
  const b = bus();
  const reports = [];
  const timers = [];
  const state = { tasks };
  const bridge = mod.createBridge({
    bus: b,
    report: (count) => { reports.push(count); },
    fetch: async () => state.tasks,
    setInterval: (fn) => { timers.push(fn); return timers.length; },
    clearInterval: (id) => { timers[id - 1] = undefined; },
  });
  return { b, bridge, reports, timers, state };
}

test("counts subagents once plus waking background tasks", () => {
  const tasks = [
    { status: "running", triggerOnCompletion: true },
    { status: "running", triggerOnCompletion: false },
    { status: "completed", triggerOnCompletion: true },
    { status: "running", triggerOnCompletion: true },
  ];
  assert.equal(mod.wakingTasks(tasks), 2);
  assert.equal(mod.bgCount(true, tasks), 3);
  assert.equal(mod.bgCount(false, []), 0);
});

test("report arguments set with a TTL and clear at zero", () => {
  assert.deepEqual(mod.reportArgs("w1:p2", 2, 7), [
    "pane", "report-metadata", "w1:p2", "--source", "user:attention-bridge", "--seq", "7",
    "--token", "bg=2", "--ttl-ms", "90000",
  ]);
  assert.deepEqual(mod.reportArgs("w1:p2", 0, 8).slice(-2), ["--clear-token", "bg"]);
});

test("reports only changes, refreshes while positive, and clears on stop", async () => {
  const { bridge: br, reports, timers, state } = bridge([]);
  await br.start();
  assert.deepEqual(reports, []);
  await br.onBusy({ active: true, label: "2 subagents" });
  state.tasks = [{ status: "running", triggerOnCompletion: true }];
  await br.recount();
  await br.recount();
  assert.deepEqual(reports, [1, 2]);
  assert.equal(timers.filter(Boolean).length, 1);
  timers[0]();
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(reports, [1, 2, 2]);
  await br.onBusy({ active: false });
  state.tasks = [];
  await br.recount();
  assert.deepEqual(reports, [1, 2, 2, 1, 0]);
  assert.equal(timers.filter(Boolean).length, 0);
  state.tasks = [{ status: "running", triggerOnCompletion: true }];
  await br.recount();
  await br.stop();
  assert.equal(reports.at(-1), 0);
});

test("nothing is reported before a TUI session starts", async () => {
  const { bridge: br, reports, b } = bridge([{ status: "running", triggerOnCompletion: true }]);
  await br.recount();
  br.promptStart("Question");
  assert.deepEqual(reports, []);
  assert.deepEqual(b.emitted, []);
});

test("dialogs become herdr:blocked pairs, and stop closes open ones", async () => {
  const { bridge: br, b } = bridge();
  await br.start();
  br.promptStart("Pick one");
  br.promptEnd();
  br.promptEnd(); // unmatched end is ignored
  br.promptStart("custom");
  await br.stop();
  assert.deepEqual(b.emitted, [
    ["herdr:blocked", { active: true, label: "Pick one" }],
    ["herdr:blocked", { active: false }],
    ["herdr:blocked", { active: true, label: "custom" }],
    ["herdr:blocked", { active: false }],
  ]);
});

test("fetchTasks talks to pi-background-tasks over the event bus", async () => {
  const b = bus();
  b.on("pi-background-tasks:request:v1", (frame) => {
    assert.equal(frame.operation, "status");
    assert.equal(frame.schema_version, "pi-background-tasks.extension-request.v1");
    b.emit("pi-background-tasks:response:v1", { request_id: "someone-else", ok: true, result: { tasks: [{ id: "x" }] } });
    b.emit("pi-background-tasks:response:v1", {
      request_id: frame.request_id, ok: true, result: { tasks: [{ id: "t1", status: "running", triggerOnCompletion: true }] },
    });
  });
  assert.deepEqual(await mod.fetchTasks(b), [{ id: "t1", status: "running", triggerOnCompletion: true }]);
});

test("fetchTasks gives up quietly without pi-background-tasks", async () => {
  assert.deepEqual(await mod.fetchTasks(bus(), 20), []);
});
