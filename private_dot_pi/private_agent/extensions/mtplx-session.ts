// Tag requests to the local MTPLX server with the pi session and leaf entry.
// MTPLX keys its warm KV-cache bank on these headers, so a follow-up turn in
// the same session restores the cached prefix instead of re-reading the whole
// prompt. Trimmed from the `mtplx-request-policy.ts` that `mtplx start pi`
// writes (its max_tokens stripping is moot: models.json sets maxTokens).
// Inert unless the provider sends `x-mtplx-client: pi` (~/.pi/agent/models.json).
export default function (pi: any) {
  pi.on("before_provider_headers", (event: any, ctx: any) => {
    const headers = event?.headers;
    if (!headers || typeof headers !== "object") return;
    const client = Object.entries(headers).find(
      ([key]) => key.toLowerCase() === "x-mtplx-client",
    )?.[1];
    if (client !== "pi") return;
    headers["x-mtplx-session-id"] = String(ctx.sessionManager.getSessionId());
    const leaf = ctx.sessionManager.getLeafId();
    if (leaf) headers["x-mtplx-client-entry-id"] = String(leaf);
  });
}
