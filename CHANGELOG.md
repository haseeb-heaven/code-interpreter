# Changelog

## 0.53.0 — Multi-provider fork release

First release of the multi-provider, local-first fork of
[google-gemini/gemini-cli](https://github.com/google-gemini/gemini-cli) (Apache
2.0), rebuilt for the
[code-interpreter](https://github.com/haseeb-heaven/code-interpreter) project.

### Added

- **Local-first providers (no API key)**
  - Ollama at `localhost:11434` is the default provider: installed models are
    auto-detected via `/api/tags` and the best one is picked automatically when
    no provider is specified.
  - LM Studio at `localhost:1234` via its OpenAI-compatible `/v1` API.
- **Cloud providers (LiteLLM-style `provider/model` routing)**: OpenAI
  (`OPENAI_API_KEY`), Anthropic (`ANTHROPIC_API_KEY`), Gemini
  (`GEMINI_API_KEY`), Groq (`GROQ_API_KEY`), DeepSeek (`DEEPSEEK_API_KEY`),
  NVIDIA (`NVIDIA_API_KEY`), Together AI (`TOGETHER_API_KEY`), HuggingFace
  (`HF_TOKEN`), OpenRouter (`OPENROUTER_API_KEY`), Cerebras
  (`CEREBRAS_API_KEY`), Z.ai (`Z_AI_API_KEY`).
- **`configs/models.toml`**: single-file model registry (models, curated
  `[[free_catalog]]` rotation, `[[default_priority]]`) mirroring the original
  Python project's registry — every model entry carried over, plus LM Studio.
- **Free-model fallback chain**: on rate limits / routing failures the free
  catalog rotates to the next preset (jumping off OpenRouter first), with local
  models (Ollama / LM Studio) as the final fallback.
- **CLI flags**: `--provider`, `--free`, `--pick`, `--byok`; `-m/--model` now
  accepts registry keys, free-catalog ids, and `provider/model` ids.
- **Slash commands**: `/pick` (model picker grouped by provider with vision /
  streaming / key-availability markers) and `/byok` (saves a provider key to
  `.env` and reports newly available models).
- **Tests**: unit tests for Ollama detection, LM Studio connection checking, the
  model registry, picker grouping, BYOK key writing, the full free fallback
  chain, per-provider routing, and a registry-wide test covering every model
  entry in `configs/models.toml`; live integration tests for every provider
  (`RUN_LOCAL_PROVIDER_TESTS=1` / `RUN_LIVE_PROVIDER_TESTS=1`, skipped in CI).

### Changed

- New `AuthType.MULTI_PROVIDER` bypasses Google authentication entirely for
  provider-routed models; no Google account or sign-in flow is required.
- README and `Models.MD` rewritten around local-first, multi-provider usage,
  including the full vision + streaming support matrix.

### Removed

- Google OAuth client credentials no longer ship in the source (supply
  `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` via environment if you
  need the legacy Code Assist flow).

### Upstream base

Forked from `google-gemini/gemini-cli` nightly `0.52.0-nightly.20260707` (commit
`27a3da3e8`). All upstream functionality and tests are retained.
