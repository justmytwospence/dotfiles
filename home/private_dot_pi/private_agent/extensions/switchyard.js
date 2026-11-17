// Switchyard enrolment: an interactive Pi started on this machine appears as a live session in
// Switchyard when a host agent runs here (see Switchyard's docs/terminal-sessions.md, "Sessions
// you start yourself"). It loads the extension from the installed Switchyard CLI, and does
// nothing where Switchyard is not installed. SWITCHYARD_ENROLL=0 opts a single Pi out.
import { existsSync } from "node:fs";
import { pathToFileURL } from "node:url";

const CANDIDATES = [
  "/opt/homebrew/lib/node_modules/@spencerboucher/switchyard/dist/bridge/switchyard-terminal.js",
  "/usr/local/lib/node_modules/@spencerboucher/switchyard/dist/bridge/switchyard-terminal.js",
  `${process.env.HOME}/.local/lib/node_modules/@spencerboucher/switchyard/dist/bridge/switchyard-terminal.js`,
];

export default async function switchyard(pi) {
  const path = CANDIDATES.find((p) => existsSync(p));
  if (!path) return;
  try {
    const mod = await import(pathToFileURL(path).href);
    await mod.default?.(pi);
  } catch {
    // An incompatible or broken install must never break Pi.
  }
}
