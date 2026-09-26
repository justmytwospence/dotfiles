// Uses the installed Pi's types/modules; no npm install, credentials or model calls.
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const packageName = "@earendil-works/pi-coding-agent";
const candidates = [process.env.PI_PACKAGE_DIR];
try { candidates.push(path.join(execFileSync("npm", ["root", "-g"], { encoding: "utf8" }).trim(), packageName)); } catch { /* optional */ }
if (process.platform === "darwin") {
  try { candidates.push(path.join(execFileSync("brew", ["--prefix", "pi-coding-agent"], { encoding: "utf8" }).trim(), "libexec/lib/node_modules", packageName)); } catch { /* optional */ }
}
const root = candidates.find((p) => p && existsSync(path.join(p, "dist/core/extensions/loader.js")));
if (!root) throw new Error("Cannot locate Pi. Set PI_PACKAGE_DIR to its installed package directory.");
const dir = await mkdtemp(path.join(os.tmpdir(), "pi-footer-check-"));
try {
  await writeFile(path.join(dir, "tsconfig.json"), JSON.stringify({
    compilerOptions: {
      target: "ES2022", module: "ESNext", moduleResolution: "Bundler", strict: true,
      noEmit: true, skipLibCheck: true, allowImportingTsExtensions: true,
      typeRoots: [path.join(root, "node_modules/@types")], types: ["node"],
      paths: {
        "@earendil-works/pi-coding-agent": [path.join(root, "dist/index.d.ts")],
        "@earendil-works/pi-tui": [path.join(root, "node_modules/@earendil-works/pi-tui/dist/index.d.ts")],
      },
    },
    files: [fileURLToPath(new URL("../agent/extensions/agent-status.ts", import.meta.url))],
  }, null, 2));
  execFileSync("tsc", ["-p", path.join(dir, "tsconfig.json")], { stdio: "inherit" });
  execFileSync(process.execPath, ["--test", fileURLToPath(new URL("status-footer.test.mjs", import.meta.url))], {
    stdio: "inherit", env: { ...process.env, PI_PACKAGE_DIR: root },
  });
} finally { await rm(dir, { recursive: true, force: true }); }
