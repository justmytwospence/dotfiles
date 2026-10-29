---
name: fastmail-mcp
description: "How to send or draft email through the official Fastmail MCP (api.fastmail.com/mcp) with Spencer's *@spencerboucher.com catch-all aliases. Use whenever you reply to, forward or compose email with a Fastmail tool: replies must go out from the address the thread was sent to, never a default or Gmail address, and a catch-all address may need adding as a sending identity first."
---

# Fastmail MCP: sending from catch-all aliases

Spencer's Fastmail account has a `*@spencerboucher.com` catch-all, and he uses a different address per correspondent (for example `davidsdetailing@spencerboucher.com`). Replying from any other address leaks the account's real address and breaks the thread's identity.

## The limitation

The official connector validates the sender against explicit sending identities. A catch-all wildcard does not count, so a concrete address with no identity of its own is rejected, and the tools expose no setting to change that. The connector is not configurable around this. Do not retry with a different sender to get past the error.

## Rules

1. For every reply or forward, find the address the original message was sent to (its `To`/`Cc` entry at spencerboucher.com, from the message or thread you read) and pass it explicitly as the sender. Never omit the sender: the composer then falls back to a default, which may be the Gmail address.
2. Check the sender with the identities listing before sending. State the sender address when you show the draft.
3. If that address is rejected or absent from the identities, stop. Do not send from a default or substitute address and do not send from a different alias. Tell Spencer which address is needed.
4. Fix: Spencer adds the specific address once in Fastmail, Settings > My email addresses > Add address > Create an alias (or confirms it exists as an explicit alias). It is saved from then on and is not needed again for that address. After he confirms, retry with the explicit sender.
5. A reply that Fastmail composes itself may already default to the original recipient address. Still confirm it before sending; do not assume.
6. If the user told you to send, send once the sender is verified. If the sender cannot be verified, leave a saved draft and say so; never send as a fallback.
