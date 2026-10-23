"""RuAPI model providers for Hermes Agent.

Registers two providers on one RuAPI API key:

- ``ruapi``: Claude models over RuAPI's native Anthropic Messages endpoint
  (``https://www.ruapi.ai/v1/messages``), so Hermes applies Anthropic prompt
  caching and thinking exactly as it does for Anthropic.
- ``ruapi-openai``: GPT, Gemini, DeepSeek, GLM, Qwen, Kimi and other chat
  models over the OpenAI-compatible endpoint (``https://www.ruapi.ai/v1``).

Hermes picks one wire protocol per provider, so the split is by provider.
Credential resolution, ``--provider``, ``hermes doctor`` and the ``/model``
picker auto-wire from the provider registry. This module only declares the two
profiles, splits RuAPI's model list between them and declares context windows
and image input for the main models.

The plugin makes no network requests of its own. The model list comes from
Hermes' standard ``GET https://www.ruapi.ai/v1/models`` request, which Hermes
sends with RUAPI_API_KEY; the plugin only filters the ids it gets back. Chat
requests are made by Hermes' own clients. The plugin never reads, stores or
forwards the key, sends no extra headers and reports nothing.
"""

from __future__ import annotations

from urllib.parse import urlparse

from providers import register_provider
from providers.base import ProviderProfile

__version__ = "0.1.0"

CLAUDE_PROVIDER_ID = "ruapi"
OPENAI_PROVIDER_ID = "ruapi-openai"
API_KEY_ENV = "RUAPI_API_KEY"

API_HOST = "www.ruapi.ai"
# The Anthropic SDK appends /v1/messages to this.
ANTHROPIC_BASE_URL = "https://www.ruapi.ai"
OPENAI_BASE_URL = "https://www.ruapi.ai/v1"
# Authenticated model list (OpenAI format). The Claude profile names it
# explicitly because its base URL has no /v1.
MODELS_URL = "https://www.ruapi.ai/v1/models"
SIGNUP_URL = "https://www.ruapi.ai/register?utm_source=hermes&utm_medium=plugin"

CLAUDE_PREFIX = "claude-"
# Image, video and embedding models are not chat models; Hermes needs tools.
EXCLUDED_MARKERS = ("image", "banana", "seedance", "video", "embed")
# Older aliases RuAPI keeps for existing users; new users should pick the
# current ids (`deepseek-flash` is the current DeepSeek Flash).
EXCLUDED_IDS = frozenset({"deepseek-v4-flash", "deepseek-v4.1-flash"})

# Context windows and image input of the main models, as published on the
# model pages at https://www.ruapi.ai/models/<id> (checked 2026-10-23).
# gpt-5.5 has no page yet; its figures are OpenAI's (models.dev openai/gpt-5.5).
# Models not listed here keep Hermes' own lookup.
_CLAUDE_CAPABILITIES = {
    model: {"supports_tools": True, "supports_reasoning": True, "supports_vision": True,
            "context_window": 1_000_000, "model_family": "claude"}
    for model in ("claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5")
}


def _caps(context: int, vision: bool, family: str) -> dict:
    return {"supports_tools": True, "supports_reasoning": True, "supports_vision": vision,
            "context_window": context, "model_family": family}


_OPENAI_CAPABILITIES = {
    **{model: _caps(1_050_000, True, "gpt") for model in (
        "gpt-6.1-sol", "gpt-6-sol", "gpt-6-luna", "gpt-6-astra",
        "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5", "gpt-5.4")},
    "gpt-5.4-mini": _caps(400_000, True, "gpt"),
    **{model: _caps(1_048_576, True, "gemini") for model in (
        "gemini-4-argon", "gemini-3.1-pro-preview", "gemini-3.5-flash-lite")},
    "deepseek-flash": _caps(1_000_000, True, "deepseek"),
    "deepseek-v4-pro": _caps(1_000_000, False, "deepseek"),
    "qwen3.8-max": _caps(1_000_000, True, "qwen"),
}


def is_claude(model_id: str) -> bool:
    return model_id.lower().startswith(CLAUDE_PREFIX)


def listed_in_picker(model_id: object, *, claude: bool) -> bool:
    """True for a chat model id of the requested side (Claude or not)."""
    if not isinstance(model_id, str) or not model_id or any(c.isspace() for c in model_id):
        return False
    lowered = model_id.lower()
    if lowered in EXCLUDED_IDS or any(marker in lowered for marker in EXCLUDED_MARKERS):
        return False
    return is_claude(lowered) == claude


def picker_models(ids: list, *, claude: bool) -> list[str]:
    """One side's ids, sorted (case-insensitive), without duplicates."""
    return sorted({model for model in ids if listed_in_picker(model, claude=claude)}, key=str.lower)


class RuAPIProfile(ProviderProfile):
    """Splits RuAPI's model list: Claude on the Anthropic-wire profile, the rest on the OpenAI wire."""

    def _lists_claude(self) -> bool:
        return self.api_mode == "anthropic_messages"

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        """This profile's chat models from Hermes' standard /v1/models request.

        A ``base_url`` on another host means the user routes through a proxy
        (``model.base_url``); its catalog is returned unfiltered. ``None``
        (no key yet, network error, nothing for this side) makes Hermes show
        ``fallback_models``.
        """
        ids = super().fetch_models(api_key=api_key, base_url=base_url, timeout=timeout)
        caller_base = (base_url or "").strip()
        if caller_base and (urlparse(caller_base).hostname or "").lower() != API_HOST:
            return ids
        if not ids:
            return None
        return picker_models(ids, claude=self._lists_claude()) or None


ruapi = RuAPIProfile(
    name=CLAUDE_PROVIDER_ID,
    display_name="RuAPI",
    description="RuAPI Claude models (native Anthropic Messages API)",
    signup_url=SIGNUP_URL,
    env_vars=(API_KEY_ENV,),
    base_url=ANTHROPIC_BASE_URL,
    models_url=MODELS_URL,
    auth_type="api_key",
    api_mode="anthropic_messages",
    # Cheap Claude for compression, titles and other side tasks.
    default_aux_model="claude-haiku-5-5",
    # Shown when the live list is unavailable (no key yet, network error).
    fallback_models=(
        "claude-sonnet-5-5",
        "claude-opus-5-5",
        "claude-haiku-5-5",
        "claude-fable-5-1",
    ),
    model_capabilities=dict(_CLAUDE_CAPABILITIES),
)

ruapi_openai = RuAPIProfile(
    name=OPENAI_PROVIDER_ID,
    display_name="RuAPI (OpenAI-compatible)",
    description="RuAPI GPT, Gemini, DeepSeek, GLM, Qwen and Kimi models (OpenAI-compatible)",
    signup_url=SIGNUP_URL,
    env_vars=(API_KEY_ENV,),
    base_url=OPENAI_BASE_URL,
    auth_type="api_key",
    api_mode="chat_completions",
    # Cheap, 1M-context model that accepts images, for side tasks.
    default_aux_model="deepseek-flash",
    # The aux model above is served by DeepSeek's native API, which implements only ``json_object``
    # and answers ``json_schema`` with HTTP 400 "This response_format type is unavailable now"
    # (same declaration as Hermes' built-in deepseek provider). Only auxiliary requests consult this.
    unsupported_response_formats=("json_schema",),
    # Shown when the live list is unavailable (no key yet, network error).
    fallback_models=(
        "gpt-5.5",
        "gpt-5.4",
        "gpt-5.4-mini",
        "gemini-4-argon",
        "gemini-3.1-pro-preview",
        "deepseek-flash",
        "deepseek-v4-pro",
        "glm-5.3",
        "qwen3.8-max",
        "kimi/kimi-k3",
    ),
    model_capabilities=dict(_OPENAI_CAPABILITIES),
)

register_provider(ruapi)
register_provider(ruapi_openai)
