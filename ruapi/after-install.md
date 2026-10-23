# RuAPI providers installed

Set your key and pick a model:

    export RUAPI_API_KEY="..."
    hermes --provider ruapi --model claude-sonnet-5-5
    hermes --provider ruapi-openai --model gpt-5.5

`ruapi` serves Claude models over the native Anthropic Messages API, so prompt
caching and thinking work as with Anthropic. `ruapi-openai` serves GPT, Gemini,
DeepSeek, GLM, Qwen, Kimi and other chat models over the OpenAI-compatible API.
Both use the same key. Or run `hermes model` and choose either provider.

Create an account and an API key at
<https://www.ruapi.ai/register?utm_source=hermes&utm_medium=plugin>; the setup
guide is at <https://docs.ruapi.ai/en/integrations/hermes>
(по-русски: <https://docs.ruapi.ai/ru/integrations/hermes>).
