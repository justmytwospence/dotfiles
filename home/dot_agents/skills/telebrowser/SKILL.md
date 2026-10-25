---
name: telebrowser
description: "Use a real, headful Chromium on the NUC that the user can see and sign in to: for sites with no API, logins, captchas, 2FA or passkeys, account data exports (Google Takeout, Facebook, iCloud), and long downloads. Each project (git repository) gets its own persistent browser profile, so a sign-in in one project is never visible to another. Drive it with the telebrowser MCP tools; hand off to the user with browser_handoff."
---

# Telebrowser

Every project on the NUC has its own Chromium on a shared desktop. The project is the
main checkout's directory name (worktrees share it); outside a git repository it is
`scratch`, which is wiped when it stops, so never sign in to anything there.

- **Agent side:** the `telebrowser` MCP server (`telebrowser mcp`: chrome-devtools-mcp
  plus three tools of its own) drives this project's browser and nothing else. It starts
  the browser on first use.
- **Human side:** the user sees every project's window at the view URL from
  `browser_info`, behind WireGuard and Authelia. `browser_handoff` brings this project's window to the front.
- **State:** the profile (cookies, logins) persists across restarts. The browser stops after
  an hour without agent activity and comes back signed in on the next tool call.

## Signing in and other human steps

1. Check first: open the site and snapshot. The profile may already be signed in.
2. If a human is needed (login, captcha, 2FA, passkey, consent), call
   `browser_handoff` with the task. It raises the window, keeps the browser alive, and
   returns the message to give the user.
3. Give the user that message, end your turn, and wait. Do not drive the page while they
   work in it, and do not ask for passwords or codes in chat.
4. When they confirm, snapshot again and carry on.

Never sign out, clear site data, or change account settings unless the task needs it. The
session is the user's.

## Downloads

Files land in the project's downloads directory on the host, at the path `browser_info`
reports (also `telebrowser downloads`). `browser_downloads` lists them newest first.
`*.crdownload` means a download is still in progress. Move what you keep into the project
and delete what you don't.

## Long-running work from scripts

For watchers that outlive a tool call (multi-GB exports, polling a page, waiting on a
download), write a Node script and run it in the background (`bg_run` in pi, or the
harness's equivalent):

```js
// node watcher.mjs '<cdp.webSocket from browser_info>'
const ws = new WebSocket(process.argv[2]); // Node 22+ has a global WebSocket
// Browser-level CDP: Target.*, Browser.*, Storage.*; attach to a page with
// Target.attachToTarget {targetId, flatten: true} and pass the sessionId.
```

Pass the script `cdp.webSocket` from `browser_info`: it is scoped to your session, so the
script sees your tabs and the tabs it opens are yours. `telebrowser ws` in a shell prints
the unscoped URL, which sees every tab in the project (use it only to find a tab you did not
open). Both contain this project's token: never commit or log them.
Downloads already go to the downloads directory, so `Browser.setDownloadBehavior` is only
needed for `downloadProgress` events (use `behavior: "allowAndName"` or `"allow"` with
`downloadPath` set to the directory from `browser_info`, and `eventsEnabled: true`).

## Tabs

Your MCP session has tabs of its own: you start on a blank one, and `list_pages` shows
only the tabs you opened (and popups they opened). Other agents in the project share the
profile and logins but not tabs, and neither of you can see the other's. New tabs open in
the background; the user may be watching any tab. Close tabs you no longer need
(`close_page`); whatever is left closes about 30 s after your session ends.

## When it fails

- `telebrowser status` shows the project, paths and whether the browser is running.
- `telebrowser stop` then retry restarts a wedged browser. The profile is kept.
- A 401 from the gateway means a wrong secret (`~/.config/telebrowser/secret`). Tell the
  user; don't work around it.
- There is no other browser to fall back on. Never start a private Chromium or reuse
  another project's browser to get past a problem.
