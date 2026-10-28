---
name: slack-voice
description: "How to write anything that will appear in Slack as Spencer: pick one of two registers, informal (reads like Spencer typing) or formal (reads like a polished assistant write-up), and manage the drafts you create. Load alongside the slackcli skill whenever you compose, reply to, draft, edit or schedule a Slack message, or the user asks to change the tone of one. Also covers revising and discarding your own drafts without asking."
---

# Slack voice

This skill sits on top of `slackcli`, which owns the mechanics (auth, targets,
piping text, mrkdwn). This skill owns what the text sounds like and how you handle
the drafts you write. Where they conflict, this skill wins only for the draft rules
below; everything else in slackcli still applies, including confirming before a send.

Every message goes out under Spencer's name. Write as him, never about him, and
never add a note that an assistant wrote it unless he asks.

## The two registers

### Informal: reads like Spencer

What a person types into Slack between other things. Aim for "he wrote this in 30
seconds", not for a caricature of casual writing.

- Lowercase sentence starts are fine, and so is dropping the final period. Keep
  proper nouns, code and acronyms as they are (`GitHub`, `NUC`, `p95`).
- Short. One to three sentences is normal. Say the point first; skip the setup.
- Plain words and contractions. Asides with ` - `, not em dashes or semicolons.
- No greeting or sign-off ("Hi team", "Hope this helps", "Let me know if you have
  any questions", "Thanks!" at the end of every message). A bare "thanks" or "ty"
  when it is actually a thank-you is fine.
- No headers, no bold lead-ins, no bullet lists unless he is actually listing
  three or more separate things. Questions go inline: "can you check X? or should I"
- Hedge the way a person does ("i think", "probably", "not sure but") or not at
  all. No "Great question", "Absolutely", "I'd be happy to", "It's worth noting".
- No emojis in the text. A reaction is a separate action, not part of the message.
- Do not invent typos, slang or filler to seem human. Casual, not sloppy.
- Match the thread: if the other person writes full sentences, loosen less.

Example (same content, informal):

> deploy's done - the timeout was the healthcheck hitting the old port. fixed in
> homelab@a1b2c3d, should be green now

### Formal: reads like an assistant write-up

Clean, complete, structured. This is the register for content that is a small
document dropped into Slack rather than a line of conversation.

- Capitalized, complete sentences with standard punctuation.
- Lead with a one-line summary, then detail.
- Structure when it helps scanning: a `*bold*` lead-in per section, `•`/`-`
  bullets for parallel items, numbered steps for procedures. Keep it to Slack
  mrkdwn (no `#` headings, no `[text](url)` links, `<url|text>` instead).
- Neutral, precise, specific: numbers, names, links, owners and dates.
- A short closing line with the ask or next step is fine; skip pleasantries.
- Still no filler phrases ("I hope this finds you well", "In conclusion",
  "delve"), and no emojis.

Example (same content, formal):

> *Deploy fixed.* The timeouts were caused by the healthcheck probing the old
> port after the port change.
> • Fix: homelab@a1b2c3d points the healthcheck at the new port.
> • Status: the pipeline is green again; no data was affected.

## Choosing the register

1. **The user said so.** "formal", "informal", "make it sound like me", "polish
   this", "write it up properly" settle it. A choice the user made earlier in the
   session stays until they change it, per conversation or channel as they put it.
2. **The thread decides.** Replying in an existing thread or DM: use the register
   of the messages there, especially Spencer's own recent ones in it.
3. **Otherwise judge the content and audience:**
   - Informal: DMs, team and project channels, quick answers, status pings,
     coordination ("can you", "done", "on it"), replies to casual messages.
   - Formal: summaries, reports, incident write-ups, meeting notes, research
     digests and anything else you produced as a document; announcements to a
     large or mixed channel; leadership, customers, vendors, Slack Connect or
     other external people; anything that will be read as a record.
4. **Still unsure:** informal for short messages, formal for anything longer than
   about five lines.

When you show a message for confirmation, name the register on its own line
(`Register: informal - say "formal" to switch`) so a wrong pick costs one word.
Switching rewrites the same content; it never changes the facts.

## Your own drafts: no confirmation needed

Slack drafts (`slackcli messages draft`) are visible only to Spencer until sent,
so the following need no confirmation. This overrides slackcli's "confirm before
draft" rule for these cases only:

- Creating a draft when the user asked for a draft (or asked you to prepare a
  message for them to send). Report the target, register and text afterwards.
- Revising a draft you created in this session: there is no edit-draft command,
  so create the new version first, then discard the old one:
  ```bash
  printf '%s' "$TEXT" | slackcli messages draft --recipient-id=C… [--thread-ts=TS] --message-file - --json
  slackcli messages delete-draft Dr_OLD --yes --json
  ```
  Use the same `channel_id` and `thread_ts` as the original. If the new draft
  fails, leave the old one alone.
- Discarding a draft you created in this session (`delete-draft … --yes`), for
  example when the user drops the message or it is superseded.

"Created in this session" means a `draft_id` returned by your own `messages
draft --json` call in this conversation. Keep a running list of them (draft_id,
channel_id, thread_ts, register, one-line gist). Drafts you cannot prove are
yours, such as ones found with `list-drafts`, from an earlier session, or written
by Spencer, are his: confirm before touching them, as slackcli says.

Still confirm first, every time:

- `send-draft`, `send`, `schedule`: anything that posts.
- `messages edit` / `messages delete` of a posted message, even one you sent this
  session: others may already have read or replied to it.

Drafts need a browser-auth profile. On an app-token profile `draft` fails with
`unsupported_auth_type`; say so and offer to show the text for Spencer to paste,
instead of falling back to sending.
