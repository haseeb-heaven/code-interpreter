# Supported Models

This document lists all supported models in Code-Interpreter.

## OpenAI stable-first (2026)
- `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.4-nano`, `gpt-5-mini`, `o4-mini`, `o3`, `o3-mini`, `gpt-4o`, `gpt-4o-mini`, `gpt-4.1-mini`.

## OpenAI legacy aliases
- `gpt-4` -> `gpt-4.1`, `gpt-3.5-turbo` -> `gpt-4o-mini`, `o1-preview` -> `o1`.

## Gemini stable-first (2026)
- `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`.

## Gemini preview (optional)
- `gemini-3.1-pro-preview`, `gemini-3-flash-preview`, `gemini-3.1-flash-lite-preview`.

## Gemini legacy aliases
- `gemini-pro`, `gemini-1.5-pro`, `gemini-1.5-flash` are remapped to Gemini 2.5 stable models.

## Anthropic stable-first (2026)
- `claude-sonnet-4-6`, `claude-opus-4-6`, `claude-haiku-4-5`.

## Anthropic legacy aliases
- `claude-2`, `claude-2.1`, `claude-3-sonnet`, `claude-3-5-sonnet`, `claude-3-7-sonnet` -> `claude-sonnet-4-6`.

## Groq stable-first (2026)
- `groq-llama-3.3`, `groq-llama-3.1-8b`, `groq-gpt-oss-120b`, `groq-gpt-oss-20b`.

## Groq preview (optional)
- `groq-llama-4-scout-preview`.

## Groq legacy aliases
- `groq-mixtral`, `groq-llama2`, `groq-gemma` are remapped to modern Groq models.

## DeepSeek
- `deepseek-chat`, `deepseek-reasoner`, with `deepseek-coder` remapped to `deepseek-chat`.

## NVIDIA (OpenAI-compatible API)
- `nvidia-nemotron` -> `nvidia/nemotron-3-super-120b-a12b`.

## Z AI (OpenAI-compatible API)
- `z-ai-glm-5` -> `glm-5`.

## OpenRouter (OpenAI-compatible API)
- `openrouter-free` -> `openrouter/free`
- `openrouter-qwen3-coder` -> `qwen/qwen3-coder:free`
- `openrouter-claude-opus-4-6` -> `anthropic/claude-opus-4.6`
- `openrouter-mimo-v2-pro` -> `xiaomi/mimo-v2-pro`
- `openrouter-gpt-5-4` -> `openai/gpt-5.4`
- `openrouter-deepseek-v3-2` -> `deepseek/deepseek-v3.2`
- `openrouter-qwen3-coder-480b-free` -> `qwen/qwen3-coder-480b:free`
- `openrouter-mimo-v2-flash-free` -> `xiaomi/mimo-v2-flash:free`
- `openrouter-nemotron-3-super-free` -> `nvidia/nemotron-3-super:free`
- `openrouter-minimax-m2-5-free` -> `minimax/minimax-m2.5:free`
- `openrouter-qwen3-6-plus-free` -> `qwen/qwen3.6-plus:free`

## Browser Use
- `browser-use-bu-max` -> `bu-max` (session-based model).

## Hugging Face + local
- `hf-meta-llama-3`, `code-llama`, `code-llama-phind`, `mistral-7b`, `wizard-coder`, `star-chat`, `local-model`.

Last verified model baseline: **April 5, 2026**.