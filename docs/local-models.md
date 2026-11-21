# Local models on the pro Mac

Two local choices, both behind llama-swap on `127.0.0.1:8000`. Model weights are
installed explicitly and validated locally; normal chezmoi apply does not
download them. The cloud default stays unchanged. Other hosts see the client
catalog but do not run these services.

| Provider / model ID | Choice | When to use it |
|---|---|---|
| `mtplx/mtplx-qwen38-27b-optimized-speed` | Qwen3.8 27B, MLX 4-bit with MTP | Fast default; text and images; 128K context |
| `local-gguf/nanbeige43-33b` | Nanbeige4.3 33B, GGUF Q4_K_M | Hardest agentic and coding work; text only; slower |

## Why these two

Reviewed 2026-11-21 against the open-weight models that fit 64GB of unified
memory. Vendor-reported agentic scores (Terminal-Bench 2.1 with Terminus 2,
DeepSWE with mini-swe-agent):

| Model | Terminal-Bench 2.1 | DeepSWE |
|---|---|---|
| Nanbeige4.3-33B | 80.9 | 65.5 |
| Qwen3.8-27B | 73.0 | 42.2 |
| Nemotron 3.5 Bolt 74B-A9B (IQ2) | 51.0 | – |
| Qwen3.6-35B-A3B | ~44.5 | ~0 |

The retired routes were Qwen3.6-35B-A3B (MTPLX), Nemotron 3.5 Bolt (Metal
GGUF), the LM Studio copy of Qwen3.8-27B (a duplicate of the MTPLX pack) and the
Qwen3.8-27B Quality Q8 pack (same model, higher precision, about 20 tok/s).
Larger MoE releases (Qwen3.8-Flash-Next, GLM-5.3-Flash, Hy4-flash) do not fit.

Candidates to revisit:

- **Inkling 2 Mini** (Thinking Machines, 26B MoE, ~5.4B effective active,
  looped): coding scores above Qwen3.8-27B at MoE speed, about 18GB at Q4. Wait
  for llama.cpp's looped-architecture support (ggml-org/llama.cpp#32695) to reach
  Homebrew; it would take the fast-sparse slot.
- **DaisyRose-27B** (RadixArk): RL-only fine-tune of Qwen3.8-27B, a drop-in
  replacement with somewhat higher reported scores. Replace the MTPLX Speed pack
  once an MTP-capable MTPLX pack exists.

## Runtime behavior

llama-swap loads a model on demand and unloads it after 15 idle minutes. It
allows one resident model and one inference request at a time; competing
requests receive 429. Switching models unloads and loads weights, so the first
request can take much longer than later turns. See [the UI](http://127.0.0.1:8000/ui);
to release the current model when no request is active:

```sh
curl --fail --show-error -X POST http://127.0.0.1:8000/api/models/unload
```

**Qwen3.8 27B (MTPLX)** keeps MTPLX's own defaults for its pack (Turbo profile,
128K context, 32K output). Do not run `mtplx start pi` or `mtplx start
opencode`: they rewrite client configuration owned by chezmoi.

**Nanbeige4.3 33B** is a dense Llama-architecture model run by Homebrew's
`llama-server`. It loads with 131,072 tokens of context and a q8_0 KV cache
(about 208KB per token at f16, roughly half that at q8_0), caps output at 32,768
tokens and disables context shifting, so out-of-budget requests are rejected
rather than silently truncated. Sampling follows the model card's agentic
setting: temperature 1.0, top-p 0.95, no top-k or min-p. Its chat template
emits XML tool calls (`<function=...>`), which llama-server parses. The template
keeps earlier turns' reasoning unless `preserve_thinking` is false, the
recommended mode for agent work. It has no MTP head and no vision input.
Context must fit input, history, tools, reasoning **and** the answer.

Measured on this M5 Pro (64GB) on 2026-11-21, with nothing else loaded:

| Prompt | Prefill | Decode |
|---|---|---|
| short | – | 8–8.5 tok/s |
| 18K tokens | ~140 tok/s (about 2 min) | ~7 tok/s |
| 62K tokens | ~78 tok/s (about 13 min) | ~4 tok/s |

Loading takes 6–40 s depending on the page cache. Thinking on/off, a tool
round trip and rejection of a 187K-token request (HTTP 400, no truncation) were
verified; free memory stayed at 14% or more at 62K. Larger micro-batches
(`-ub 2048`) did not speed up prefill. Use it for hard tasks where waiting pays
off, not for interactive back-and-forth; prompt caching makes later turns of
a session much faster than the first.

In Pi, open `/model` and select the provider/model; `/thinking` controls
reasoning. Nanbeige exposes only off and medium, where medium means thinking on.
OpenCode selects models through its model picker and relies on server defaults.
OpenCode's built-in `lmstudio` catalog is disabled so undownloaded models do not
appear.

## Install the weights

An explicit local operation, not part of normal apply. No weights belong in Git,
chezmoi externals or provisioning scripts. The pinned inventory is in
`home/.chezmoidata/local_models.json`.

The MTPLX Speed pack:

```sh
mtplx pull Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed --cache-dir "$HOME/.mtplx/models"
```

Nanbeige (20,788,825,216 bytes). The script resumes a partial file and moves it
into place only after its byte count and SHA-256 match; a failed check leaves
the partial for inspection:

```sh
(
  set -eu
  dir="$HOME/.local/share/local-models/nanbeige43-33b"
  base='https://huggingface.co/bartowski/Nanbeige_Nanbeige4.3-33B-GGUF/resolve/9beb68421fdf7be095093a6888325fa2c83ddd38'
  name='Nanbeige_Nanbeige4.3-33B-Q4_K_M.gguf'
  size=20788825216
  sha=2cef79855ca47ee6571e166db32a07089e34f3cf78e0397b262d124ddb814c37
  mkdir -p "$dir"
  final="$dir/$name" part="$dir/$name.part"
  [ -e "$final" ] && { echo "already present: $final"; exit 0; }
  curl --fail --location --retry 3 --continue-at - --output "$part" "$base/$name"
  [ "$(wc -c < "$part" | tr -d ' ')" = "$size" ] || { echo "size mismatch: $part" >&2; exit 1; }
  [ "$(shasum -a 256 "$part" | cut -d' ' -f1)" = "$sha" ] || { echo "sha mismatch: $part" >&2; exit 1; }
  mv -n "$part" "$final"
)
```

## Verify

After landing, with no inference request active:

```sh
chezmoi verify --exclude scripts ~/.config/llama-swap/config.yaml ~/.pi/agent/models.json ~/.pi/agent/settings.json ~/.config/opencode/opencode.jsonc
curl --fail --silent --show-error http://127.0.0.1:8000/v1/models
pi --list-models
```

Exercise a route with streaming, thinking on and off, and a tool round trip;
then a long prompt to check the context budget. Monitor memory and swap, check
that switching leaves only one model loaded, and finish by unloading it. A
working model catalog does not prove inference or the advertised context works.
