// opencode plugin: warn the moment an Anthropic request is billed to extra usage instead of the
// Claude plan. Every subscription (OAuth) response carries
// `anthropic-ratelimit-unified-representative-claim`: `five_hour`/`seven_day` when the plan paid,
// `overage` when extra usage did (`anthropic-ratelimit-unified-overage-in-use: true`). That happens
// when a request is not shaped as Claude Code (an opencode-anthropic-auth gap) or when the plan's
// limits are exhausted. opencode has no built-in extra-usage warning, so this is it.
//
// It watches responses by wrapping the global fetch, which opencode-anthropic-auth calls for every
// Anthropic request.

import { appendFileSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const CLAIM = "anthropic-ratelimit-unified-representative-claim";
const OVERAGE_IN_USE = "anthropic-ratelimit-unified-overage-in-use";
const REPEAT_MS = 10 * 60 * 1000;
const WRAPPED = Symbol.for("dotfiles.anthropic-billing-guard");
// Shared with the pi extension: one line per request billed to extra usage.
const LOG = join(process.env.XDG_STATE_HOME || join(homedir(), ".local", "state"), "anthropic-extra-usage.log");

function record(url) {
  try {
    mkdirSync(join(LOG, ".."), { recursive: true });
    appendFileSync(LOG, `${new Date().toISOString()}\topencode\t${process.cwd()}\t${url}\n`);
  } catch {}
}

// Not exported: opencode treats every exported function as a plugin.
function billedToExtraUsage(headers) {
  return headers.get(CLAIM) === "overage" || headers.get(OVERAGE_IN_USE) === "true";
}

export const AnthropicBillingGuard = async ({ client }) => {
  if (globalThis.fetch?.[WRAPPED]) return {};
  const original = globalThis.fetch;
  let lastWarnedAt = 0;

  const guarded = async (input, init) => {
    const response = await original(input, init);
    try {
      if (response.headers.has(CLAIM) && billedToExtraUsage(response.headers)) {
        record(typeof input === "string" ? input : (input?.url ?? String(input)));
        const now = Date.now();
        if (now - lastWarnedAt >= REPEAT_MS) {
          lastWarnedAt = now;
          await client.tui.showToast({
            body: {
              title: "Anthropic extra usage",
              message:
                "This request was billed to EXTRA USAGE (pay per token), not your Claude plan. The plan limit is used up or the request was not shaped as Claude Code. claude.ai/settings/usage",
              variant: "warning",
              duration: 15000,
            },
          });
        }
      }
    } catch {
      // A warning must never break a request.
    }
    return response;
  };
  guarded[WRAPPED] = true;
  globalThis.fetch = Object.assign(guarded, original);
  return {};
};
