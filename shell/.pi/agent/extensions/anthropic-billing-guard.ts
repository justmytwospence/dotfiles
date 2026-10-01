/**
 * Warn the moment an Anthropic request is billed to extra usage instead of the Claude plan.
 *
 * Pi's own "anthropicExtraUsage" warning is a static startup notice. This one reads what Anthropic
 * actually did: every subscription (OAuth) response carries
 * `anthropic-ratelimit-unified-representative-claim`, which is `five_hour`/`seven_day` when the
 * plan paid and `overage` when extra usage did (`anthropic-ratelimit-unified-overage-in-use: true`).
 * That happens when a request is not shaped as Claude Code (a pi-anthropic-auth gap) or when the
 * plan's limits are exhausted. Either way you are paying per token, so say so.
 */
import { appendFileSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const CLAIM = "anthropic-ratelimit-unified-representative-claim";
const OVERAGE_IN_USE = "anthropic-ratelimit-unified-overage-in-use";
const STATUS_KEY = "anthropic-billing";
/** Repeat the warning at most this often while requests keep landing on extra usage. */
const REPEAT_MS = 10 * 60 * 1000;
/** Shared with the opencode plugin: one line per request billed to extra usage. */
const LOG = join(process.env.XDG_STATE_HOME || join(homedir(), ".local", "state"), "anthropic-extra-usage.log");

function record(model: string) {
  try {
    mkdirSync(dirname(LOG), { recursive: true });
    appendFileSync(LOG, `${new Date().toISOString()}\tpi\t${process.cwd()}\t${model}\n`);
  } catch {
    // A warning must never break a request.
  }
}

export function billedToExtraUsage(headers: Record<string, string | undefined>): boolean {
  const get = (name: string) => headers[name] ?? headers[name.toLowerCase()];
  return get(CLAIM) === "overage" || get(OVERAGE_IN_USE) === "true";
}

export default function anthropicBillingGuard(pi: ExtensionAPI) {
  let lastWarnedAt = 0;
  let overageCount = 0;

  pi.on("after_provider_response", (event, ctx) => {
    const headers = event.headers ?? {};
    if (!(CLAIM in headers) && !(OVERAGE_IN_USE in headers)) return; // not an Anthropic plan response
    if (!billedToExtraUsage(headers)) {
      if (overageCount > 0) ctx.ui.setStatus(STATUS_KEY, undefined);
      overageCount = 0;
      return;
    }
    overageCount += 1;
    record(ctx.model ? `${ctx.model.provider}/${ctx.model.id}` : "unknown");
    ctx.ui.setStatus(STATUS_KEY, `extra usage x${overageCount}`);
    const now = Date.now();
    if (now - lastWarnedAt < REPEAT_MS) return;
    lastWarnedAt = now;
    ctx.ui.notify(
      "Anthropic billed this request to EXTRA USAGE (pay per token), not your Claude plan. " +
        "Either the plan limit is used up or the request was not shaped as Claude Code " +
        "(check /anthropic-auth:status). Manage at https://claude.ai/settings/usage",
      "warning",
    );
  });
}
