// Tag requests to the local MTPLX provider (opencode.jsonc "mtplx") with the OpenCode session
// and turn. MTPLX keys its warm KV-cache bank on these headers, so a follow-up turn restores the
// cached prefix instead of re-reading the whole prompt. Inert for every other provider. pi's
// twin: ~/.pi/agent/extensions/mtplx-session.ts. OpenCode 2 plugin API.
const turns = new Map();

export default {
  id: "mtplx-session",
  async setup(ctx) {
    await ctx.session.hook("prompt", (event) => {
      turns.set(event.sessionID, String(event.messageID));
    });
    await ctx.session.hook(
      "model.request",
      (event) => {
        event.headers["x-mtplx-client"] = "opencode";
        event.headers["x-mtplx-session-id"] = String(event.sessionID);
        const turn = turns.get(event.sessionID);
        if (turn) event.headers["x-mtplx-client-turn-id"] = turn;
      },
      { providerID: "mtplx" },
    );
  },
};
