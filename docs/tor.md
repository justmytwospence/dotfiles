# Tor for the wallet apps

The homelab crypto nodes (`~/Projects/homelab/crypto-nodes`) each have an onion service
protected by Tor v3 client authorization. The Macs run a local Tor client that holds the
authorization key, so Sparrow and Feather reach the nodes from anywhere without the VPN.
The HTTPS LAN/VPN routes still exist as a fallback.

## Pieces

| Piece | Source | Deployed to |
|---|---|---|
| Tor client LaunchAgent `com.spencerboucher.tor` | `private_Library/private_LaunchAgents/com.spencerboucher.tor.plist.tmpl` | `~/Library/LaunchAgents` |
| torrc (SOCKS `127.0.0.1:9050`) | `dot_config/private_tor/torrc.tmpl` | `~/.config/tor/torrc` |
| Client-auth keys, age-encrypted | `dot_config/private_tor/private_onion-auth/encrypted_private_homelab-*.auth_private.age` | `~/.config/tor/onion-auth/` (only where the age key exists) |
| `tor-client` converge section | `.chezmoitemplates/converge/tor-client.sh` | reloads the agent when plist, torrc or keys change |

Tor is the Homebrew `tor` (Brewfile). The three onions (Bitcoin RPC 8332, Monero restricted
RPC 18089, Ethereum RPC 80) share one x25519 client key. Onion hostnames are read on the NUC
from the hidden service `hostname` files and live only in the encrypted auth files and the
apps' local configs, never in git.

## Rotating the client key

1. Generate a keypair (`/opt/homebrew/opt/openssl@3/bin/openssl genpkey -algorithm x25519`;
   the raw 32 bytes of the DER private/public keys, base32 without padding).
2. On the NUC put `descriptor:x25519:<PUBLIC>` in each hidden service's
   `authorized_clients/macs.auth` and restart `payments-tor`.
3. Each encrypted file holds `<onion host without .onion>:descriptor:x25519:<PRIVATE>`;
   recreate them with `chezmoi encrypt`, commit, land.

## App settings (machine-local, not managed)

- **Sparrow** (`~/.sparrow/config`, quit the app first): `coreServer` `http://<bitcoin>.onion:8332`,
  `useProxy` true, `proxyServer` `127.0.0.1:9050`, `autoSwitchProxy` false; keep `coreAuthType`
  `USERPASS` and `coreAuth` `wallet:<password>`. The file holds the Core password: mode 600.
- **Feather** (`~/Library/Application Support/FeatherWallet/settings.json`, quit first):
  `nodeSource` 1, `nodes` `{"0":{"custom":["<monero>.onion:18089"],"ws":[]}}`, `proxy` 1,
  `useLocalTor` true, `socks5Host` `127.0.0.1`, `socks5Port` `9050`, `torPrivacyLevel` 2,
  `torOnlyAllowOnion` true.
- **Trezor Suite**: its own bundled Tor on (Settings, Application). Its custom Ethereum RPC is
  broken while Tor is on (viem `e.body.getReader is not a function`), so Ethereum uses Trezor's
  servers; Bitcoin is off in Suite (use Sparrow); Solana on.
- **Ledger Wallet** has no proxy support and Ledger blocks Tor: use the Ledger device through
  Sparrow (Bitcoin) and Feather (Monero), and open Ledger Wallet only for firmware and apps.
