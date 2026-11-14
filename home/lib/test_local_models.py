"""Offline checks for local-model provenance and rendered client/server configuration."""
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHEZMOI = shutil.which("chezmoi")
LLAMA_SWAP = shutil.which("llama-swap")
QUALITY = "mtplx-qwen38-27b-optimized-quality"
MOE = "mtplx-qwen36-35b-a3b-optimized-speed"
BOLT = "nemotron35-bolt-metal"
SPEED = "mtplx-qwen38-27b-optimized-speed"
LMSTUDIO = "qwen3.8-27b"
ROUTES = {QUALITY, MOE, BOLT, SPEED, LMSTUDIO}


def manifest():
    return json.loads((ROOT / ".chezmoidata/local_models.json").read_text())["localModels"]["additions"]


def route_blocks(config):
    # The models map is the final top-level YAML map. Only route keys at two
    # spaces are captured, not similarly named fields or comments in commands.
    models = config.split("\nmodels:\n", 1)[1]
    keys = list(re.finditer(r'^  ["\']?([\w.-]+)["\']?:\s*$', models, re.M))
    result = {m.group(1): models[m.end():keys[i + 1].start() if i + 1 < len(keys) else len(models)]
              for i, m in enumerate(keys)}
    if len(result) != len(keys):
        raise AssertionError("duplicate model route IDs")
    return result


def route_args(block):
    match = re.search(r'^    cmd:[ \t]*\|[-+]?[ \t]*\n((?: {6,}[^\n]*\n)+)', block, re.M)
    if not match:
        raise AssertionError("expected a literal command block")
    return shlex.split(match.group(1))


def option(args, key):
    return args[args.index(key) + 1]


class Manifest(unittest.TestCase):
    def test_pinned_inventories(self):
        entries = manifest()
        self.assertEqual(len(entries), 3)
        models = {m["id"]: m for m in entries}
        self.assertEqual(set(models), {QUALITY, MOE, BOLT})
        expected = {
            QUALITY: ("mtplx", "mtplx", ["text", "image"], "Youssofal/Qwen3.8-27B-MTPLX-Optimized-Quality", "300a4ac6c6058585e80571ff6c910819711843ec", 29972714046, 6),
            MOE: ("mtplx", "mtplx", ["text", "image"], "Youssofal/Qwen3.6-35B-A3B-MTPLX-Optimized-Speed", "95460516fbfe34c48f577f67c9ed191f5d61fbaf", 21014908552, 4),
            BOLT: ("local-gguf", "llama.cpp", ["text", "image"], "UraionLabs/Nemotron-3.5-Bolt-74B-A9B-24GB-Metal-GGUF", "38ce8d963641fe219759a85eb5d72587ea554d1c", 25943543104, 0),
        }
        for ident, (provider, runtime, modalities, repo, revision, size, shards) in expected.items():
            with self.subTest(model=ident):
                model = models[ident]
                self.assertEqual((model["provider"], model["runtime"], model["input"], model["repo"], model["revision"], model["downloadBytes"]), (provider, runtime, modalities, repo, revision, size))
                self.assertRegex(model["revision"], r"^[0-9a-f]{40}$")
                self.assertEqual((model["contextWindow"], model["maxTokens"]), (32768 if ident == QUALITY else 65536, 16384))
                self.assertFalse(Path(model["directory"]).is_absolute())
                self.assertNotIn("..", Path(model["directory"]).parts)
                files = {f["name"]: f for f in model["files"]}
                self.assertEqual(len(files), len(model["files"]))
                self.assertEqual(sum(f["size"] for f in files.values()), size)
                for f in files.values():
                    self.assertGreater(f["size"], 0)
                    if f["sha256"] is not None:
                        self.assertRegex(f["sha256"], r"^[0-9a-f]{64}$")
                    if f["name"].endswith((".safetensors", ".gguf")):
                        self.assertRegex(f["sha256"] or "", r"^[0-9a-f]{64}$")
                if shards:
                    required = {"config.json", "tokenizer.json", "tokenizer_config.json", "model.safetensors.index.json", "mtp.safetensors", "mtplx_runtime.json", "chat_template.jinja"}
                    required.update(f"model-{n:05d}-of-{shards:05d}.safetensors" for n in range(1, shards + 1))
                    if ident == QUALITY:
                        required.add("model-vision.safetensors")
                    self.assertTrue(required <= files.keys())
                else:
                    self.assertEqual({name: (f["size"], f["sha256"]) for name, f in files.items()}, {
                        "Nemotron-3.5-Bolt-74B-A9B-24GB-Metal-IQ2_XXS.gguf": (24209850368, "d441866fe3b737161cbd65ba77a49ea1e1c6622e35bbd9f20b35bae99b8d110b"),
                        "mmproj-Nemotron-3.5-Bolt-74B-A9B-24GB-BF16.gguf": (1733692736, "0ee891eadc7bf0cae6289b249c74eb1ef420534351f6ef8b64d49f0ca6a926b0"),
                    })


@unittest.skipUnless(CHEZMOI, "chezmoi is not installed")
class RenderedModels(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.config = self.base / "chezmoi.toml"
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"), XDG_CACHE_HOME=str(self.home / ".cache"), XDG_DATA_HOME=str(self.home / ".local/share"))
        self.configure("mac-pro")

    def configure(self, host):
        role = "pro" if host == "mac-pro" else "air" if host == "mac-air" else ""
        self.config.write_text('[data]\nhost = %s\nrole = %s\nextras = ""\n' % (json.dumps(host), json.dumps(role)))

    def render(self, path):
        return subprocess.check_output([CHEZMOI, "--config", str(self.config), "--source", str(ROOT), "execute-template", "--file", str(ROOT / path)], env=self.env, text=True)

    def test_routes_and_runtime_settings(self):
        config = self.render("dot_config/llama-swap/config.yaml.tmpl")
        self.assertRegex(config, r"(?m)^globalConcurrencyLimit:\s*1\s*$")
        for key, value in (("globalTTL", "900"), ("unloadTimeout", "20"), ("healthCheckTimeout", "300"), ("sendLoadingState", "false")):
            self.assertRegex(config, rf"(?m)^{key}:\s*{value}(?:\s|$)")
        routes = route_blocks(config)
        self.assertEqual(set(routes), ROUTES)
        self.assertEqual(route_args(routes[SPEED]), ["/opt/homebrew/bin/mtplx", "serve", "--model", "Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed", "--host", "127.0.0.1", "--port", "${PORT}"])
        self.assertNotIn("MTPLX_MANAGED_CLIENT_CONTROLS", routes[SPEED])
        self.assertIn("lmstudio-hold", routes[LMSTUDIO])
        self.assertIn("http://127.0.0.1:1234", routes[LMSTUDIO])
        for model in manifest():
            with self.subTest(model=model["id"]):
                block = routes[model["id"]]
                self.assertRegex(block, r"(?m)^    checkEndpoint:\s*/health\s*$")
                self.assertRegex(block, r"(?m)^    ttl:\s*900\s*$")
                args = route_args(block)
                self.assertEqual(option(args, "--host"), "127.0.0.1")
                self.assertEqual(option(args, "--port"), "${PORT}")
                self.assertNotIn("--allow-swap", args)
                self.assertFalse(any(re.search(r"(?:force|fan|allow-swap|cpu-moe|draft|speculative)", arg, re.I) for arg in args if arg.startswith("-")))
                directory = self.home / model["directory"]
                settings = model["settings"]
                if model["runtime"] == "mtplx":
                    self.assertEqual(args[:4], ["/usr/bin/env", "MTPLX_MANAGED_CLIENT_CONTROLS=client", "/opt/homebrew/bin/mtplx", "serve"])
                    pairs = {"--model": str(directory), "--model-id": model["id"], "--context-window": model["contextWindow"], "--max-tokens": model["maxTokens"], "--profile": settings["profile"], "--depth": settings["depth"], "--default-temperature": settings["temperature"], "--default-top-p": settings["topP"], "--default-top-k": settings["topK"], "--default-presence-penalty": settings["presencePenalty"]}
                    if "reasoningEffort" in settings:
                        pairs["--reasoning-effort"] = settings["reasoningEffort"]
                    self.assertIn("--no-stats-footer", args)
                else:
                    self.assertEqual(args[0], "/opt/homebrew/bin/llama-server")
                    pairs = {"--model": str(directory / settings["modelFile"]), "--mmproj": str(directory / settings["mmprojFile"]), "--alias": model["id"], "-ngl": settings["gpuLayers"], "-fa": settings["flashAttention"], "-c": model["contextWindow"], "--n-predict": model["maxTokens"], "-np": settings["parallel"], "-b": settings["batchSize"], "-ub": settings["microBatchSize"], "--cache-type-k": settings["cacheTypeK"], "--cache-type-v": settings["cacheTypeV"], "--reasoning-format": settings["reasoningFormat"], "--temp": settings["temperature"], "--top-p": settings["topP"], "--top-k": settings["topK"], "--min-p": settings["minP"], "--repeat-penalty": settings["repeatPenalty"]}
                    self.assertIn("--jinja", args)
                    self.assertIn("--no-context-shift", args)
                    self.assertEqual(json.loads(option(args, "--chat-template-kwargs")), settings["chatTemplateKwargs"])
                    self.assertEqual((settings["cacheTypeK"], settings["cacheTypeV"]), ("f16", "f16"))
                for flag, expected in pairs.items():
                    actual = option(args, flag)
                    if isinstance(expected, (int, float)):
                        self.assertEqual(float(actual), expected, flag)
                    else:
                        self.assertEqual(actual, str(expected), flag)

    @unittest.skipUnless(LLAMA_SWAP, "llama-swap is not installed")
    def test_llama_swap_validation(self):
        config = self.base / "config.yaml"
        config.write_text(self.render("dot_config/llama-swap/config.yaml.tmpl"))
        subprocess.run([LLAMA_SWAP, "-config", str(config), "-validate"], env=self.env, check=True, capture_output=True, text=True)

    def test_client_catalogs_and_controls(self):
        pi = json.loads((ROOT / "private_dot_pi/private_agent/models.json").read_text())["providers"]
        raw = self.render("dot_config/opencode/opencode.jsonc.tmpl")
        oc = json.loads("\n".join(line for line in raw.splitlines() if not line.lstrip().startswith("//")))["provider"]
        entries = manifest() + [
            {"id": SPEED, "provider": "mtplx", "name": "Qwen3.8 27B (MTPLX, local)", "contextWindow": 131072, "maxTokens": 32768, "input": ["text", "image"]},
            {"id": LMSTUDIO, "provider": "lmstudio", "name": "Qwen3.8 27B (LM Studio, local)", "contextWindow": 131072, "maxTokens": 32768, "input": ["text", "image"]},
        ]
        for m in entries:
            with self.subTest(model=m["id"]):
                p = next(x for x in pi[m["provider"]]["models"] if x["id"] == m["id"])
                o = oc[m["provider"]]["models"][m["id"]]
                for key in ("name", "contextWindow", "maxTokens", "input"):
                    self.assertEqual(p[key], m[key])
                self.assertEqual(o["name"], m["name"])
                self.assertEqual(o["limit"], {"context": m["contextWindow"], "output": m["maxTokens"]})
                self.assertEqual(o["modalities"], {"input": m["input"], "output": ["text"]})
                self.assertTrue(p["reasoning"] and o["reasoning"] and o["tool_call"] and o["temperature"])
                self.assertTrue(all(value == 0 for value in p["cost"].values()))
                self.assertEqual(oc[m["provider"]]["options"]["baseURL"], "http://127.0.0.1:8000/v1")
                self.assertEqual(pi[m["provider"]]["baseUrl"], "http://127.0.0.1:8000/v1")
        quality, moe = (next(x for x in pi["mtplx"]["models"] if x["id"] == ident) for ident in (QUALITY, MOE))
        bolt = pi["local-gguf"]["models"][0]
        for level in ("low", "medium", "xhigh"):
            self.assertEqual(quality["thinkingLevelMap"][level], level)
        for level in ("minimal", "high", "max"):
            self.assertIsNone(quality["thinkingLevelMap"][level])
        for model in (moe, bolt):
            self.assertEqual(model["thinkingLevelMap"]["medium"], "medium")
            for level in ("minimal", "low", "high", "xhigh", "max"):
                self.assertIsNone(model["thinkingLevelMap"][level])
        self.assertFalse(moe["compat"]["supportsReasoningEffort"])
        compat = pi["local-gguf"]["compat"]
        for key in ("supportsDeveloperRole", "supportsReasoningEffort", "supportsStore"):
            self.assertFalse(compat[key])
        self.assertEqual((compat["maxTokensField"], compat["thinkingFormat"]), ("max_tokens", "chat-template"))
        self.assertEqual(compat["chatTemplateKwargs"], {"enable_thinking": {"$var": "thinking.enabled"}})
        bolt_settings = next(m["settings"] for m in entries if m["id"] == BOLT)
        self.assertEqual(bolt["samplingParams"], {"temperature": bolt_settings["temperature"], "top_p": bolt_settings["topP"], "top_k": 0, "min_p": 0})
        for model in (quality, moe):
            self.assertEqual(model["samplingParamsByThinkingLevel"]["off"], {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5})
            settings = next(m["settings"] for m in entries if m["id"] == model["id"])
            self.assertEqual(model["samplingParams"], {"temperature": settings["temperature"], "top_p": settings["topP"], "top_k": settings["topK"], "presence_penalty": settings["presencePenalty"]})

    def test_enabled_models_and_baseline_load(self):
        settings = json.loads((ROOT / "private_dot_pi/private_agent/settings.managed.json").read_text())
        self.assertEqual((settings["defaultProvider"], settings["defaultModel"], settings["defaultThinkingLevel"]), ("anthropic", "claude-opus-5-5", "medium"))
        expected = {"anthropic/claude-opus-5-5", "openai/gpt-6-astra", "openai/gpt-6.1-sol", "google/antigravity-gemini-4-carbon", "google/antigravity-gemini-4-argon", "mtplx/" + SPEED, "lmstudio/" + LMSTUDIO}
        expected.update(m["provider"] + "/" + m["id"] for m in manifest())
        self.assertTrue(expected <= set(settings["enabledModels"]))
        # Muse stays installed (pi-muse-bridge) but is not a favorite: it stays off the splash.
        self.assertNotIn("muse-code/muse-wonder-1.0", settings["enabledModels"])
        path = ROOT / "dot_lmstudio/dot_internal/user-concrete-model-default-config/unsloth/Qwen3.8-27B-GGUF/Qwen3.8-27B-UD-Q4_K_XL.gguf.json"
        fields = {f["key"]: f["value"] for f in json.loads(path.read_text())["load"]["fields"]}
        self.assertEqual(fields["llm.load.contextLength"], 131072)
        self.assertIs(fields["llm.load.llama.speculativeDecoding.draftMtp"], True)
        self.assertEqual(fields["llm.load.llama.speculativeDecoding.draftMaxTokens"], 3)

    def test_non_pro_hosts_do_not_provision_models(self):
        for host in ("mac-pro", "mac-air", "nuc", "agentbox-box"):
            with self.subTest(host=host):
                self.configure(host)
                ignore = self.render(".chezmoiignore").splitlines()
                for target in (".config/llama-swap", ".lmstudio", "Library/LaunchAgents/com.spencerboucher.llama-swap.plist"):
                    if host != "mac-pro":
                        self.assertIn(target, ignore)
                    else:
                        self.assertNotIn(target, ignore)
                for script in (".chezmoiscripts/run_before_bootstrap.sh.tmpl", ".chezmoiscripts/run_after_converge.sh.tmpl"):
                    rendered = self.render(script)
                    for model in manifest():
                        self.assertNotIn(model["repo"], rendered)
                        self.assertNotIn(model["directory"], rendered)
                    self.assertNotRegex(rendered, r"(?i)\bmtplx\s+pull\b")


if __name__ == "__main__":
    unittest.main()
