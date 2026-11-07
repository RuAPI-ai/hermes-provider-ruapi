# hermes-provider-ruapi

[RuAPI](https://www.ruapi.ai/?utm_source=hermes&utm_medium=plugin) model providers for
[Hermes Agent](https://github.com/NousResearch/hermes-agent).

RuAPI is an API gateway for Russian-speaking developers: one API key for Claude, GPT,
Gemini, DeepSeek, Qwen, GLM, Kimi and other models. It works from Russia without a VPN,
and you top up the pay-as-you-go balance with USDT, so no foreign bank card is needed.
Hermes speaks one wire protocol per provider, so this plugin registers two providers on
the same key:

| Provider | Models | Wire protocol | Endpoint |
|---|---|---|---|
| `ruapi` | Claude (`claude-*`) | Native Anthropic Messages API | `https://www.ruapi.ai/v1/messages` |
| `ruapi-openai` | GPT, Gemini, DeepSeek, GLM, Qwen, Kimi and other chat models | OpenAI-compatible Chat Completions | `https://www.ruapi.ai/v1` |

Claude goes over the Anthropic protocol so Hermes applies Anthropic prompt caching
(cache breakpoints) and thinking (`agent.reasoning_effort`) exactly as it does for
Anthropic itself.

The plugin registers these two model providers and nothing else: no tools, hooks,
middleware, commands, background threads or processes. Hermes core files are not
touched.

Maintained by RuAPI.

**По-русски.** Плагин добавляет RuAPI в Hermes как два провайдера на одном ключе:
`ruapi` (Claude через родной Anthropic Messages API) и `ruapi-openai` (GPT, Gemini,
DeepSeek и другие модели через OpenAI-совместимый API). RuAPI работает из России без
VPN, баланс пополняется в USDT, карта иностранного банка не нужна. Инструкция на
русском: [docs.ruapi.ai/ru/integrations/hermes](https://docs.ruapi.ai/ru/integrations/hermes).

## What you get

- `--provider ruapi` / `--provider ruapi-openai`, both providers in `hermes model` and
  `/model`, `hermes setup` and `hermes doctor` checks, all wired by Hermes from the
  provider profiles.
- `/model` pickers built from your account's model list (`GET /v1/models`): Claude
  models under `ruapi`, the other chat models under `ruapi-openai`. Image and video
  models and two older DeepSeek aliases (`deepseek-v4-flash`, `deepseek-v4.1-flash`;
  use `deepseek-flash`) are left out. Without a key, or when the list cannot be
  fetched, a short built-in list is shown instead.
- Context windows and image input declared for the main models (Claude 5.5 and Fable
  5.1, GPT-6 / 5.6 / 5.5 / 5.4, Gemini 4 Argon and 3.1 Pro, DeepSeek Flash and V4 Pro,
  Qwen3.8 Max), so Hermes does not fall back to its generic default for them. Other
  models keep Hermes' own lookup.
- Cheap models for Hermes side tasks (compression, titles): `claude-haiku-5-5` on
  `ruapi`, `deepseek-flash` on `ruapi-openai`.

## Requirements

- Hermes Agent 0.21.5 or newer. The `ruapi` provider uses Hermes' Anthropic
  transport, which needs the `anthropic` Python package; Hermes installs it on first
  use (or ships it with its `anthropic` extra).
- A RuAPI API key in `RUAPI_API_KEY`. Create an account at
  [ruapi.ai](https://www.ruapi.ai/register?utm_source=hermes&utm_medium=plugin), then
  create a key in the console (API Keys). A new account usually gets a small trial
  balance for `deepseek-flash`, `claude-haiku-5-5` and `gpt-6-luna`; the other models
  (Claude Sonnet and Opus, other GPT models, Gemini and the rest) unlock after the
  first top-up of $5 or more. Prices per model:
  [ruapi.ai/pricing](https://www.ruapi.ai/pricing?utm_source=hermes&utm_medium=plugin).
- The plugin itself has no Python dependencies beyond the standard library.

## Install

From the Hermes plugin catalog (once listed):

```bash
hermes plugins install ruapi
```

Or drop the plugin directory into your Hermes home:

```bash
git clone https://github.com/RuAPI-ai/hermes-provider-ruapi.git
mkdir -p ~/.hermes/plugins/model-providers
cp -r hermes-provider-ruapi/ruapi ~/.hermes/plugins/model-providers/ruapi
```

## Use

```bash
export RUAPI_API_KEY="..."
hermes --provider ruapi --model claude-sonnet-5-5
hermes --provider ruapi-openai --model gpt-5.5
```

Or run `hermes model`, pick RuAPI or RuAPI (OpenAI-compatible), and choose a model.
`hermes setup` also offers `RUAPI_API_KEY`.

Some models are billed in two tiers by prompt length (for example GPT-5.x above 272K
tokens and Claude Haiku 5.5 above 100K; see the pricing page). To keep long sessions
in the lower tier, cap the window Hermes uses with `model.context_length` in
`config.yaml`.

If you point `model.base_url` at your own proxy, the picker shows that proxy's
unfiltered `{base_url}/models` list instead.

## Network calls, credentials and telemetry

- **Chat requests** go to RuAPI through Hermes' own clients with the key from
  `RUAPI_API_KEY`: Claude requests to `https://www.ruapi.ai/v1/messages` (key in the
  `x-api-key` header), other models to `https://www.ruapi.ai/v1/chat/completions` (key
  as `Authorization: Bearer`). Hermes reads the key; the plugin never reads, stores,
  logs or forwards it.
- **Model list**: Hermes' standard catalog request,
  `GET https://www.ruapi.ai/v1/models` with the key as `Authorization: Bearer`, made by
  Hermes' own `ProviderProfile.fetch_models`. The plugin only filters the model ids it
  returns. The plugin makes no network requests of its own.
- **No extra headers.** The plugin adds no headers to any request.
- **No telemetry.** The plugin sends no analytics, usage reports or crash data
  anywhere.
- **No files, no processes.** The plugin reads and writes no files, stores no
  credentials and starts no threads or processes.
- Prompts, tool schemas and model output are processed by RuAPI and the upstream model
  vendor serving the chosen model. RuAPI does not store prompt or response content; it
  records request metadata (model, token counts, time, status) for billing. See the
  [privacy policy](https://docs.ruapi.ai/en/legal/privacy) and
  [terms](https://docs.ruapi.ai/en/legal/terms).

## Development

```bash
python3 -m unittest discover -s tests -v
```

The unit tests use stub `providers` modules and need neither Hermes nor the network.
`tests/test_hermes_integration.py` runs only when Hermes is importable (a Hermes
checkout's interpreter, with `PYTHONPATH` pointing at it and its `anthropic` extra
installed). It installs the plugin into a temporary `HERMES_HOME` and drives real
Hermes turns against local fake servers, one per wire protocol, so it makes no real
network calls either. Check the plugin the way the catalog CI does:

```bash
hermes plugins validate ./ruapi --install-deps
```

## Changelog

### 0.1.0

First release: `ruapi` (Claude, Anthropic Messages) and `ruapi-openai`
(OpenAI-compatible) providers, pickers split from the account's model list, context
windows and image input for the main models.

## License

MIT. See [LICENSE](https://github.com/RuAPI-ai/hermes-provider-ruapi/blob/main/LICENSE).
