// Tag requests to the local MTPLX provider (opencode.jsonc "mtplx") with the
// opencode session and turn. MTPLX keys its warm KV-cache bank on these
// headers, so a follow-up turn restores the cached prefix instead of
// re-reading the whole prompt. Trimmed from the mtplx-session-headers plugin
// `mtplx start opencode` installs (its sampler/output-cap rewriting is left
// out). Inert for every other provider. pi's twin: shell/.pi/agent/extensions/mtplx-session.ts.
export const MTPLXSession = async () => ({
  "chat.headers": async (input, output) => {
    const providerID = input?.model?.providerID || input?.provider?.id;
    if (providerID !== "mtplx") return;
    output.headers ||= {};
    output.headers["x-mtplx-client"] = "opencode";
    if (input?.sessionID) output.headers["x-mtplx-session-id"] = String(input.sessionID);
    if (input?.message?.id) output.headers["x-mtplx-client-turn-id"] = String(input.message.id);
  },
});
export default MTPLXSession;
