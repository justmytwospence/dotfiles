# Local models on the pro Mac

The five-choice lineup uses the existing MTPLX, LM Studio, llama.cpp and
llama-swap installations. Model weights are installed explicitly and validated
locally; normal chezmoi apply does not download them. The existing cloud default
stays unchanged. Other hosts may see the global client catalog but do not run these Mac
inference services.

| Provider / model ID | Choice | When to try it |
|---|---|---|
| `mtplx/mtplx-qwen38-27b-optimized-speed` | Qwen3.8 27B Speed, MTP | Existing fast general-purpose and image baseline |
| `lmstudio/qwen3.8-27b` | Qwen3.8 27B Q4, MTP | Existing LM Studio baseline; saved 128K load settings matter |
| `mtplx/mtplx-qwen38-27b-optimized-quality` | Qwen3.8 27B Quality, Q8 / MTP | Higher-fidelity alternative, text and images |
| `mtplx/mtplx-qwen36-35b-a3b-optimized-speed` | Qwen3.6 35B-A3B Speed, MoE / MTP | Fast sparse alternative, text and tested image input |
| `local-gguf/nemotron35-bolt-metal` | Nemotron 3.5 Bolt 74B-A9B Metal | Different model family, text and images; Metal conversion |

The Quality pack's fidelity claims are not a guarantee of BF16-identical output;
speculative decoding and sampling need their own validation. Bolt's Metal
conversion is not mathematically lossless and has not had a complete task-quality
evaluation. On this M5 Pro, all three additions passed streaming, thinking on/off,
tool round trips and image tests. Quality passed 32K; MoE and Bolt also passed
near-64K prompts and rejected oversized requests. Revalidate after runtime changes;
short throughput measurements are not guarantees for every workload.

llama-swap on `127.0.0.1:8000` loads a model on demand and unloads it after 15
idle minutes. The intended configuration allows one resident model and one
inference request at a time; competing requests receive 429. Switching models
requires unloading and loading weights, so the first request can take much longer
than subsequent turns. Loading a model directly in the LM Studio app bypasses
this coordination. See [the UI](http://127.0.0.1:8000/ui); to release the current
model when no request is active:

```sh
curl --fail --show-error -X POST http://127.0.0.1:8000/api/models/unload
```

The two existing choices retain their 131,072-token context and 32,768-token
maximum output declarations. Quality uses a tested 32,768-token context: a
near-64K prefill hit the memory guard with other apps open, so the user chose the
reliable 32K limit. MoE and Bolt use 65,536 total context. All three cap output at
16,384 tokens, not the native 262K window. Context must fit
input, history, tools, reasoning **and** the answer; reserve output space. Bolt
sets `--n-predict 16384` and disables context shifting; verify out-of-budget
requests are rejected rather than silently truncating history. Test 32K first and
64K with output reserved, and stop on sustained swap, crashes or
malformed output rather than claiming a smaller silent fallback as success.

Quality defaults to Turbo, MTP depth 3, temperature 1, top-p 0.95 and top-k 20;
MoE uses Sustained, depth 1, temperature 0.6, top-p 0.95 and top-k 20. D1 won
the D0/D1/D2 comparison at about 78 tokens/s. Its vision weights are embedded
inside the body shards; image input was verified locally despite no separate
vision file being present.
Both use presence penalty 0 with thinking enabled; Pi's non-thinking Qwen
sampling uses temperature 0.7, top-p 0.8, top-k 20 and presence penalty 1.5.
Bolt defaults to temperature 1 and top-p 0.95, with top-k and min-p filtering
disabled. Bolt measured about 21 tokens/s on the short sampled throughput tests.
Quality D3 measured about 20 tokens/s versus 8 without speculation on this M5 Pro;
it won the D0/D1/D2/D3 comparison. MoE D1 won its separate depth comparison.
These short throughput tests do not establish task-quality rankings. The two new
MTPLX routes set `MTPLX_MANAGED_CLIENT_CONTROLS=client` so marked Pi and OpenCode
requests can override server sampling; without it MTPLX's `auto` mode keeps those
settings server-owned. The existing Speed route is unchanged. Verify actual
client behavior during runtime testing.

In Pi, open `/model` and select the provider/model; `/thinking` controls reasoning.
Quality supports low, medium and xhigh effort; MoE and Bolt expose only off and
medium, where medium means thinking on rather than a selectable effort tier.
OpenCode selects models through its model picker and initially relies on server
defaults; do not assume Pi's per-request thinking controls apply there. Pi tool
execution was verified with all three additions; OpenCode inference was verified
with the MoE route. OpenCode 2's
model listing can still show undownloaded built-in LM Studio entries despite the
existing whitelist; the five configured choices are present. Verify actual client
requests and tool round trips after runtime upgrades. Do not run `mtplx start pi` or
`mtplx start opencode`: they rewrite client configuration owned by chezmoi.

## Install the new weights

This is an explicit local operation, not part of normal apply. The three additions
total 76,931,165,702 bytes (76.93 GB / 71.65 GiB) beyond the existing models;
allow extra working space and check free disk first. No weights belong in Git,
chezmoi externals or provisioning scripts. No new package installation is needed.
Run the downloads sequentially. The MTPLX pulls use pinned full snapshots and do
not rewrite clients:

```sh
(
  set -e
  mtplx pull Youssofal/Qwen3.8-27B-MTPLX-Optimized-Quality \
    --revision 300a4ac6c6058585e80571ff6c910819711843ec \
    --cache-dir "$HOME/.mtplx/models"
  mtplx pull Youssofal/Qwen3.6-35B-A3B-MTPLX-Optimized-Speed \
    --revision 95460516fbfe34c48f577f67c9ed191f5d61fbaf \
    --cache-dir "$HOME/.mtplx/models"
)
```

Inspect both local directories and verify their complete snapshot inventories,
including large-file sizes and SHA-256 digests, against the pinned manifest before
serving. Metadata cache entries alone do not prove the weights are present:

```sh
mtplx inspect --model "$HOME/.mtplx/models/Youssofal--Qwen3.8-27B-MTPLX-Optimized-Quality" --require-mtp --json
mtplx inspect --model "$HOME/.mtplx/models/Youssofal--Qwen3.6-35B-A3B-MTPLX-Optimized-Speed" --require-mtp --json
```

Both inspections must report compatible native-MTP artifacts. The full snapshot
sizes are 29,972,714,046 and 21,014,908,552 bytes respectively. The pinned
inventory is in `home/.chezmoidata/local_models.json`.

Download Bolt's two pinned files sequentially. This script reuses a valid final
file, refuses to overwrite a corrupt final file, resumes partial files, and moves
a partial into place only after **both** its byte count and SHA-256 match. A
failed download or check stops the sequence and leaves the partial for inspection;
if a completed partial is corrupt, remove or rename it deliberately before a fresh
download. Do not activate the route until both files verify.

```sh
(
  set -eu
  dir="$HOME/.local/share/local-models/nemotron35-bolt-metal"
  base='https://huggingface.co/UraionLabs/Nemotron-3.5-Bolt-74B-A9B-24GB-Metal-GGUF/resolve/38ce8d963641fe219759a85eb5d72587ea554d1c'
  mkdir -p "$dir"

  valid() {
    [ -f "$1" ] || return 1
    size=$(wc -c < "$1" | tr -d '[:space:]')
    [ "$size" = "$2" ] || return 1
    digest=$(shasum -a 256 "$1") || return 1
    [ "${digest%% *}" = "$3" ]
  }

  fetch() {
    name=$1 expected_size=$2 expected_sha=$3
    final="$dir/$name" part="$dir/$name.part"
    if [ -e "$final" ] || [ -L "$final" ]; then
      if valid "$final" "$expected_size" "$expected_sha"; then
        printf 'Already verified: %s\n' "$final"
        return 0
      fi
      printf 'Invalid final file; refusing to overwrite: %s\n' "$final" >&2
      return 1
    fi
    if ! valid "$part" "$expected_size" "$expected_sha"; then
      curl --fail --location --retry 3 --continue-at - \
        --output "$part" "$base/$name"
    fi
    if ! valid "$part" "$expected_size" "$expected_sha"; then
      printf 'Integrity check failed; retaining: %s\n' "$part" >&2
      return 1
    fi
    mv -n "$part" "$final"
    valid "$final" "$expected_size" "$expected_sha" || {
      printf 'Final file verification failed: %s\n' "$final" >&2
      return 1
    }
  }

  fetch 'Nemotron-3.5-Bolt-74B-A9B-24GB-Metal-IQ2_XXS.gguf' \
    24209850368 d441866fe3b737161cbd65ba77a49ea1e1c6622e35bbd9f20b35bae99b8d110b
  fetch 'mmproj-Nemotron-3.5-Bolt-74B-A9B-24GB-BF16.gguf' \
    1733692736 0ee891eadc7bf0cae6289b249c74eb1ef420534351f6ef8b64d49f0ca6a926b0
)
```

## Apply and verify configuration

Only after implementation, weight integrity checks and review, and with separate
authorization to apply, check that no inference request is active. Apply only the
reviewed targets without provisioning scripts; the proxy watches its config. Do
not interrupt another user's workload or start parallel model tests.

```sh
chezmoi apply --exclude scripts ~/.config/llama-swap/config.yaml ~/.pi/agent/models.json ~/.pi/agent/settings.json ~/.config/opencode/opencode.jsonc
chezmoi verify --exclude scripts ~/.config/llama-swap/config.yaml ~/.pi/agent/models.json ~/.pi/agent/settings.json ~/.config/opencode/opencode.jsonc
chezmoi status
curl --fail --silent --show-error http://127.0.0.1:8000/v1/models
pi --list-models
```

Classify residual drift; the two always-run scripts normally remain pending `R`.
Exercise new routes one at a time at 32K then 64K, including streaming, thinking
on/off, tool round trips and images where supported. Monitor memory and swap,
verify switching leaves only one model loaded, and finish by unloading it. A
working model catalog does not prove inference or advertised context works.
Commit, push and NUC synchronization require separate authorization; follow
[AGENTS.md](../AGENTS.md) and do not download or run these Mac models on the NUC.
