"""Offline tests for the RuAPI provider profiles (stub Hermes, no network)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import (  # noqa: E402
    EXPECTED_CLAUDE,
    EXPECTED_OPENAI,
    MODEL_IDS,
    StubProviderProfile,
    load_plugin,
)

FAKE_KEY = "sk-ruapi-test-not-a-real-key"


def _profiles():
    plugin, registered = load_plugin()
    by_name = {p.name: p for p in registered}
    return plugin, registered, by_name["ruapi"], by_name["ruapi-openai"]


class ProfileDeclarationTests(unittest.TestCase):
    def setUp(self):
        self.plugin, self.registered, self.claude, self.openai = _profiles()

    def test_registers_the_two_providers(self):
        self.assertEqual([p.name for p in self.registered], ["ruapi", "ruapi-openai"])
        for profile in self.registered:
            self.assertEqual(type(profile).__name__, "RuAPIProfile")

    def test_claude_goes_over_the_native_anthropic_messages_api(self):
        self.assertEqual(self.claude.api_mode, "anthropic_messages")
        # The Anthropic SDK appends /v1/messages to the base URL.
        self.assertEqual(self.claude.base_url, "https://www.ruapi.ai")
        self.assertEqual(self.claude.models_url, "https://www.ruapi.ai/v1/models")

    def test_other_models_go_over_the_openai_compatible_api(self):
        self.assertEqual(self.openai.api_mode, "chat_completions")
        self.assertEqual(self.openai.base_url, "https://www.ruapi.ai/v1")
        # {base_url}/models is the same authenticated list.
        self.assertEqual(self.openai.models_url, "")

    def test_side_tasks_skip_json_schema_on_the_openai_side(self):
        # The OpenAI-side aux model is deepseek-flash; DeepSeek's native API rejects json_schema
        # with a 400, so Hermes should send aux requests without it (as for its own deepseek provider).
        self.assertEqual(self.openai.default_aux_model, "deepseek-flash")
        self.assertEqual(self.openai.unsupported_response_formats, ("json_schema",))
        self.assertEqual(self.claude.unsupported_response_formats, ())

    def test_both_use_one_api_key(self):
        for profile in self.registered:
            self.assertEqual(profile.env_vars, ("RUAPI_API_KEY",))
            self.assertEqual(profile.auth_type, "api_key")

    def test_no_extra_headers_and_no_provider_wide_vision_claim(self):
        for profile in self.registered:
            self.assertEqual(profile.default_headers, {})
            self.assertFalse(profile.supports_vision)

    def test_signup_url_is_tracked(self):
        for profile in self.registered:
            url = urlparse(profile.signup_url)
            self.assertEqual((url.scheme, url.netloc, url.path), ("https", "www.ruapi.ai", "/register"))
            self.assertEqual(parse_qs(url.query), {"utm_source": ["hermes"], "utm_medium": ["plugin"]})

    def test_fallback_and_aux_models_belong_to_each_side(self):
        for profile, expected in ((self.claude, EXPECTED_CLAUDE), (self.openai, EXPECTED_OPENAI)):
            fallback = list(profile.fallback_models)
            self.assertTrue(fallback)
            self.assertEqual(len(fallback), len(set(fallback)))
            for model in [*fallback, profile.default_aux_model]:
                self.assertIn(model, expected, (profile.name, model))

    def test_declared_capabilities_belong_to_each_side(self):
        allowed = {"supports_tools", "supports_reasoning", "supports_vision", "context_window", "model_family"}
        for profile, expected in ((self.claude, EXPECTED_CLAUDE), (self.openai, EXPECTED_OPENAI)):
            self.assertTrue(profile.model_capabilities)
            for model, caps in profile.model_capabilities.items():
                self.assertIn(model, expected, (profile.name, model))
                self.assertLessEqual(set(caps), allowed, model)
                self.assertIs(type(caps["context_window"]), int)
                self.assertGreaterEqual(caps["context_window"], 64_000, model)
                for flag in ("supports_tools", "supports_reasoning", "supports_vision"):
                    self.assertIs(type(caps[flag]), bool, (model, flag))

    def test_published_context_windows(self):
        caps = {**self.claude.model_capabilities, **self.openai.model_capabilities}
        self.assertEqual(caps["claude-sonnet-5-5"]["context_window"], 1_000_000)
        self.assertEqual(caps["gpt-5.4-mini"]["context_window"], 400_000)
        self.assertEqual(caps["gemini-4-argon"]["context_window"], 1_048_576)
        self.assertFalse(caps["deepseek-v4-pro"]["supports_vision"])
        self.assertTrue(caps["deepseek-flash"]["supports_vision"])


class PickerFilterTests(unittest.TestCase):
    def setUp(self):
        self.plugin, _, _, _ = _profiles()

    def test_fixture_splits_into_the_expected_pickers(self):
        self.assertEqual(self.plugin.picker_models(MODEL_IDS, claude=True), EXPECTED_CLAUDE)
        self.assertEqual(self.plugin.picker_models(MODEL_IDS, claude=False), EXPECTED_OPENAI)

    def test_every_fixture_id_is_listed_once_or_deliberately_left_out(self):
        listed = set(EXPECTED_CLAUDE) | set(EXPECTED_OPENAI)
        left_out = sorted(set(MODEL_IDS) - listed)
        self.assertEqual(left_out, sorted([
            "deepseek-v4-flash", "deepseek-v4.1-flash",
            "doubao-seedance-2.0", "doubao-seedance-2.0-fast", "doubao-seedance-2.0-mini",
            "gemini-2.5-flash-image", "gemini-3-pro-image", "gemini-3-pro-image-preview",
            "gemini-3.1-flash-image", "gemini-3.1-flash-image-preview", "gemini-nano-banana-2.1",
            "gpt-image-2", "gpt-image-2.5-flare", "gpt-image-2.5-sunburst", "nano-banana-pro",
        ]))

    def test_excluded_entries(self):
        def listed(model, claude=False):
            return self.plugin.listed_in_picker(model, claude=claude)

        self.assertFalse(listed("gpt-image-2"))
        self.assertFalse(listed("nano-banana-pro"))
        self.assertFalse(listed("doubao-seedance-2.0"))
        self.assertFalse(listed("deepseek-v4-flash"))
        self.assertFalse(listed("DeepSeek-V4.1-Flash"))
        self.assertFalse(listed("text-embedding-3-large"))
        self.assertFalse(listed("gpt 5.5"))
        self.assertFalse(listed(""))
        self.assertFalse(listed(None))
        self.assertFalse(listed({"id": "gpt-5.5"}))

    def test_each_side_rejects_the_other(self):
        self.assertTrue(self.plugin.listed_in_picker("claude-sonnet-5-5", claude=True))
        self.assertFalse(self.plugin.listed_in_picker("claude-sonnet-5-5", claude=False))
        self.assertTrue(self.plugin.listed_in_picker("gpt-5.5", claude=False))
        self.assertFalse(self.plugin.listed_in_picker("gpt-5.5", claude=True))

    def test_duplicates_are_dropped(self):
        self.assertEqual(self.plugin.picker_models(["gpt-5.5", "gpt-5.5", "glm-5.3"], claude=False),
                         ["glm-5.3", "gpt-5.5"])


class FetchModelsTests(unittest.TestCase):
    def setUp(self):
        self.plugin, _, self.claude, self.openai = _profiles()
        StubProviderProfile.STUB_IDS = list(MODEL_IDS)
        StubProviderProfile.STUB_ERROR = None

    def tearDown(self):
        StubProviderProfile.STUB_IDS = None
        StubProviderProfile.STUB_ERROR = None

    def test_uses_hermes_standard_request_and_splits_it(self):
        self.assertEqual(self.claude.fetch_models(api_key=FAKE_KEY, base_url="https://www.ruapi.ai"),
                         EXPECTED_CLAUDE)
        self.assertEqual(self.openai.fetch_models(api_key=FAKE_KEY, base_url="https://www.ruapi.ai/v1/"),
                         EXPECTED_OPENAI)
        # The key, base URL and timeout go to Hermes' own fetch unchanged.
        self.assertEqual(self.claude.inherited_calls,
                         [{"api_key": FAKE_KEY, "base_url": "https://www.ruapi.ai", "timeout": 8.0}])

    def test_no_base_url_is_treated_as_ruapi(self):
        self.assertEqual(self.openai.fetch_models(api_key=FAKE_KEY), EXPECTED_OPENAI)

    def test_failed_or_empty_fetch_returns_none_for_fallback(self):
        for ids in (None, []):
            StubProviderProfile.STUB_IDS = ids
            self.assertIsNone(self.claude.fetch_models(api_key=FAKE_KEY))
            self.assertIsNone(self.openai.fetch_models(api_key=FAKE_KEY))

    def test_list_without_models_for_a_side_returns_none(self):
        StubProviderProfile.STUB_IDS = ["gpt-5.5", "gpt-image-2"]
        self.assertIsNone(self.claude.fetch_models(api_key=FAKE_KEY))
        self.assertEqual(self.openai.fetch_models(api_key=FAKE_KEY), ["gpt-5.5"])

    def test_proxy_base_url_returns_hermes_list_unfiltered(self):
        StubProviderProfile.STUB_IDS = ["my-model", "claude-sonnet-5-5", "gpt-image-2"]
        result = self.openai.fetch_models(api_key=FAKE_KEY, base_url="https://proxy.example.test/v1")
        self.assertEqual(result, ["my-model", "claude-sonnet-5-5", "gpt-image-2"])


if __name__ == "__main__":
    unittest.main()
