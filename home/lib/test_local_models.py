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
NANBEIGE = "nanbeige43-33b"
SPEED = "mtplx-qwen38-27b-optimized-speed"
ROUTES = {NANBEIGE, SPEED}
# Routes retired 2026-11-21; they must not come back by accident.
RETIRED = {"mtplx-qwen38-27b-optimized-quality", "mtplx-qwen36-35b-a3b-optimized-speed", "nemotron35-bolt-metal", "qwen3.8-27b"}


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
        self.assertEqual([m["id"] for m in entries], [NANBEIGE])
        model = entries[0]
        self.assertEqual((model["provider"], model["runtime"], model["input"], model["repo"], model["revision"], model["downloadBytes"]),
                         ("local-gguf", "llama.cpp", ["text"], "bartowski/Nanbeige_Nanbeige4.3-33B-GGUF", "9beb68421fdf7be095093a6888325fa2c83ddd38", 20788825216))
        self.assertEqual((model["contextWindow"], model["maxTokens"]), (131072, 32768))
        self.assertFalse(Path(model["directory"]).is_absolute())
        self.assertNotIn("..", Path(model["directory"]).parts)
        self.assertEqual({f["name"]: (f["size"], f["sha256"]) for f in model["files"]}, {
            "Nanbeige_Nanbeige4.3-33B-Q4_K_M.gguf": (20788825216, "2cef79855ca47ee6571e166db32a07089e34f3cf78e0397b262d124ddb814c37"),
        })
        self.assertEqual(sum(f["size"] for f in model["files"]), model["downloadBytes"])
        self.assertNotIn("mmprojFile", model["settings"])


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
        self.assertNotIn("lmstudio", config)
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
                    pairs = {"--model": str(directory / settings["modelFile"]), "--alias": model["id"], "-ngl": settings["gpuLayers"], "-fa": settings["flashAttention"], "-c": model["contextWindow"], "--n-predict": model["maxTokens"], "-np": settings["parallel"], "-b": settings["batchSize"], "-ub": settings["microBatchSize"], "--cache-type-k": settings["cacheTypeK"], "--cache-type-v": settings["cacheTypeV"], "--reasoning-format": settings["reasoningFormat"], "--temp": settings["temperature"], "--top-p": settings["topP"], "--top-k": settings["topK"], "--min-p": settings["minP"], "--repeat-penalty": settings["repeatPenalty"]}
                    self.assertIn("--jinja", args)
                    self.assertIn("--no-context-shift", args)
                    # Thinking defaults come from --reasoning; --chat-template-kwargs'
                    # enable_thinking is deprecated in llama-server.
                    self.assertEqual(option(args, "--reasoning"), settings["reasoning"])
                    self.assertIn(settings["reasoning"], ("on", "off", "auto"))
                    self.assertNotIn("--chat-template-kwargs", args)
                    if "mmprojFile" in settings:
                        pairs["--mmproj"] = str(directory / settings["mmprojFile"])
                    else:
                        self.assertNotIn("--mmproj", args)
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
                self.assertEqual(o["attachment"], "image" in m["input"])
                self.assertTrue(all(value == 0 for value in p["cost"].values()))
                self.assertEqual(oc[m["provider"]]["options"]["baseURL"], "http://127.0.0.1:8000/v1")
                self.assertEqual(pi[m["provider"]]["baseUrl"], "http://127.0.0.1:8000/v1")
        self.assertNotIn("lmstudio", pi)
        self.assertNotIn("lmstudio", oc)
        listed = {x["id"] for prov in pi.values() for x in prov.get("models", [])} | {k for prov in oc.values() for k in prov.get("models", {})}
        self.assertFalse(listed & RETIRED)
        self.assertEqual({x["id"] for x in pi["mtplx"]["models"]}, {SPEED})
        nanbeige = next(x for x in pi["local-gguf"]["models"] if x["id"] == NANBEIGE)
        self.assertEqual(nanbeige["thinkingLevelMap"]["medium"], "medium")
        for level in ("minimal", "low", "high", "xhigh", "max"):
            self.assertIsNone(nanbeige["thinkingLevelMap"][level])
        compat = pi["local-gguf"]["compat"]
        for key in ("supportsDeveloperRole", "supportsReasoningEffort", "supportsStore"):
            self.assertFalse(compat[key])
        self.assertEqual((compat["maxTokensField"], compat["thinkingFormat"]), ("max_tokens", "chat-template"))
        self.assertEqual(compat["chatTemplateKwargs"], {"enable_thinking": {"$var": "thinking.enabled"}})
        settings = manifest()[0]["settings"]
        self.assertEqual(nanbeige["samplingParams"], {"temperature": settings["temperature"], "top_p": settings["topP"], "top_k": settings["topK"], "min_p": settings["minP"]})

    def test_enabled_models_and_baseline_load(self):
        settings = json.loads((ROOT / "private_dot_pi/private_agent/settings.managed.json").read_text())
        self.assertEqual((settings["defaultProvider"], settings["defaultModel"], settings["defaultThinkingLevel"]), ("anthropic", "claude-opus-5-5", "medium"))
        expected = {"anthropic/claude-opus-5-5", "openai/gpt-6-astra", "openai/gpt-6.1-sol", "google/antigravity-gemini-4-carbon", "google/antigravity-gemini-4-argon", "mtplx/" + SPEED}
        expected.update(m["provider"] + "/" + m["id"] for m in manifest())
        self.assertTrue(expected <= set(settings["enabledModels"]))
        # Muse stays installed (pi-muse-bridge) but is not a favorite: it stays off the splash.
        self.assertNotIn("muse-code/muse-wonder-1.0", settings["enabledModels"])
        self.assertFalse({m.split("/", 1)[1] for m in settings["enabledModels"]} & RETIRED)
        self.assertFalse((ROOT / "dot_lmstudio").exists())
        self.assertFalse((ROOT / "dot_config/llama-swap/executable_lmstudio-hold").exists())
        remove = (ROOT / ".chezmoiremove").read_text().splitlines()
        self.assertIn(".config/llama-swap/lmstudio-hold", remove)

    def test_non_pro_hosts_do_not_provision_models(self):
        for host in ("mac-pro", "mac-air", "nuc", "agentbox-box"):
            with self.subTest(host=host):
                self.configure(host)
                ignore = self.render(".chezmoiignore").splitlines()
                for target in (".config/llama-swap", "Library/LaunchAgents/com.spencerboucher.llama-swap.plist"):
                    if host != "mac-pro":
                        self.assertIn(target, ignore)
                    else:
                        self.assertNotIn(target, ignore)
                for script in sorted(p.name for p in (ROOT / ".chezmoiscripts").glob("*.tmpl")):
                    rendered = self.render(".chezmoiscripts/" + script)
                    for model in manifest():
                        self.assertNotIn(model["repo"], rendered)
                        self.assertNotIn(model["directory"], rendered)
                    self.assertNotRegex(rendered, r"(?i)\bmtplx\s+pull\b")


if __name__ == "__main__":
    unittest.main()
