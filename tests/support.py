"""Load the plugin against stub ``providers`` modules, so unit tests run without Hermes."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "ruapi"
TESTS_DIR = Path(__file__).resolve().parent

# A GET https://www.ruapi.ai/v1/models answer in OpenAI format, built from the
# public model catalogue of 2026-10-23 (ids and endpoint types only). Which ids
# a real key sees depends on the account.
MODELS = json.loads((TESTS_DIR / "models_fixture.json").read_text(encoding="utf-8"))
MODEL_IDS = [item["id"] for item in MODELS["data"]]

# What each picker must show for that fixture.
EXPECTED_CLAUDE = [
    "claude-fable-5", "claude-fable-5-1", "claude-haiku-4-5-20251001", "claude-haiku-5-5",
    "claude-opus-4-5-20251101", "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8",
    "claude-opus-5", "claude-opus-5-5", "claude-sonnet-4-5-20250929", "claude-sonnet-4-6",
    "claude-sonnet-5", "claude-sonnet-5-5",
]
EXPECTED_OPENAI = [
    "deepseek-flash", "deepseek-v4-pro",
    "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro", "gemini-3-flash-preview",
    "gemini-3.1-pro-preview", "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash",
    "gemini-3.7-flash", "gemini-3.8-flash", "gemini-4-argon",
    "GLM-5-Turbo", "GLM-5.2", "glm-5.3", "glm-5.3-flash", "GLM-5V-Turbo",
    "gpt-5.4", "gpt-5.4-mini", "gpt-5.5", "gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra",
    "gpt-6-astra", "gpt-6-luna", "gpt-6-sol", "gpt-6.1-sol",
    "kimi/kimi-k3", "MiniMax/MiniMax-M3",
    "qwen3.7-max", "qwen3.7-plus", "qwen3.8-27b", "qwen3.8-flash", "qwen3.8-max", "qwen3.8-max-0902",
    "xiaomi/mimo-v2.5-pro",
]


@dataclass
class StubProviderProfile:
    """The ``providers.base.ProviderProfile`` fields this plugin sets.

    ``fetch_models`` stands in for Hermes' standard ``/models`` request: it
    records the call and returns ``STUB_IDS`` (or raises ``STUB_ERROR``).
    """

    name: str
    api_mode: str = "chat_completions"
    aliases: tuple = ()
    display_name: str = ""
    description: str = ""
    signup_url: str = ""
    env_vars: tuple = ()
    base_url: str = ""
    models_url: str = ""
    auth_type: str = "api_key"
    supports_vision: bool = False
    fallback_models: tuple = ()
    hostname: str = ""
    default_headers: dict = field(default_factory=dict)
    default_aux_model: str = ""
    unsupported_response_formats: tuple = ()
    model_capabilities: dict = field(default_factory=dict)

    STUB_IDS = None
    STUB_ERROR = None

    def fetch_models(self, *, api_key=None, base_url=None, timeout=8.0):
        self.inherited_calls = getattr(self, "inherited_calls", [])
        self.inherited_calls.append({"api_key": api_key, "base_url": base_url, "timeout": timeout})
        if StubProviderProfile.STUB_ERROR is not None:
            raise StubProviderProfile.STUB_ERROR
        ids = StubProviderProfile.STUB_IDS
        return list(ids) if ids is not None else None

    def get_model_context_length(self, model):
        return None


def load_plugin():
    """Import the plugin fresh; return ``(module, [registered profiles])``."""
    registered: list = []
    providers = types.ModuleType("providers")
    providers.register_provider = registered.append
    base = types.ModuleType("providers.base")
    base.ProviderProfile = StubProviderProfile
    providers.base = base
    saved = {name: sys.modules.get(name) for name in ("providers", "providers.base")}
    sys.modules.update({"providers": providers, "providers.base": base})
    try:
        spec = importlib.util.spec_from_file_location(
            "ruapi_provider_under_test",
            PLUGIN_DIR / "__init__.py",
            submodule_search_locations=[str(PLUGIN_DIR)],
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
    return module, registered
