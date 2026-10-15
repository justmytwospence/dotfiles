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
  `browser_info`, behind WireGuard and Authelia. Each window is titled `[<project>]`.
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
// node watcher.mjs "$(telebrowser ws)"
const ws = new WebSocket(process.argv[2]); // Node 22+ has a global WebSocket
// Browser-level CDP: Target.*, Browser.*, Storage.*; attach to a page with
// Target.attachToTarget {targetId, flatten: true} and pass the sessionId.
```

`telebrowser ws` prints the browser WebSocket URL and `telebrowser http` the HTTP base
(`<http>/json/list`). Both contain this project's token: never commit or log them.
Downloads already go to the downloads directory, so `Browser.setDownloadBehavior` is only
needed for `downloadProgress` events (use `behavior: "allowAndName"` or `"allow"` with
`downloadPath` set to the directory from `browser_info`, and `eventsEnabled: true`).

## Tabs

Open your own tab (`new_page`) instead of taking over the user's or an earlier session's.
Close the tabs you opened when you are done (`close_page`); leave the last tab open, since
closing it closes the window. Other sessions in the same project share the browser, so
pages you didn't open may appear in `list_pages`. Leave them alone.

## When it fails

- `telebrowser status` shows the project, paths and whether the browser is running.
- `telebrowser stop` then retry restarts a wedged browser. The profile is kept.
- A 401 from the gateway means a wrong secret (`~/.config/telebrowser/secret`). Tell the
  user; don't work around it.
- There is no other browser to fall back on. Never start a private Chromium or reuse
  another project's browser to get past a problem.
