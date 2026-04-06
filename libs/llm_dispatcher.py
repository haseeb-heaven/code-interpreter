"""
Centralised helper that builds the keyword-arguments dictionary for a single
`litellm.completion()` call, eliminating the duplicated provider branches that
previously lived in Interpreter.generate_content.
"""

import os


# Providers whose configs route through the OpenAI-compatible shim.
_OPENAI_COMPATIBLE_PROVIDERS = frozenset({"nvidia", "z-ai", "zai", "openrouter", "browser-use", "browser_use"})

# Explicit tags for a self-hosted OpenAI-compatible server (Ollama, LM Studio, vLLM, llama.cpp, etc.).
_LOCAL_OPENAI_ENDPOINT_PROVIDERS = frozenset({"local", "ollama", "lmstudio"})

# Maps a config_provider value to the environment-variable name that holds its
# API key.
_PROVIDER_KEY_MAP = {
    "nvidia": "NVIDIA_API_KEY",
    "z-ai": "Z_AI_API_KEY",
    "zai": "Z_AI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "browser-use": "BROWSER_USE_API_KEY",
    "browser_use": "BROWSER_USE_API_KEY",
}


def _has_openai_compatible_api_base(api_base: str) -> bool:
    """True when config points at an http(s) URL (local or custom OpenAI-compatible API)."""
    if not api_base or api_base == "None":
        return False
    lower = api_base.strip().lower()
    return lower.startswith("http://") or lower.startswith("https://")


def _detect_provider(model: str, config_provider: str, api_base: str) -> str:
    """Return a canonical provider tag based on config or model name."""
    cp = (config_provider or "").strip().lower()
    if cp in _OPENAI_COMPATIBLE_PROVIDERS:
        return cp
    if cp in _LOCAL_OPENAI_ENDPOINT_PROVIDERS:
        return "local"

    model_lower = model.lower()

    if model_lower.startswith(("gpt", "o1", "o3", "o4")):
        return "openai"
    if "gemini" in model_lower:
        return "gemini"
    if "groq" in model_lower:
        return "groq"
    if "claude" in model_lower:
        return "claude"
    if "local" in model_lower:
        return "local"
    if "deepseek" in model_lower:
        return "deepseek"

    # Custom endpoint in config (e.g. configs/local-model.json) without "local" in the model id.
    if _has_openai_compatible_api_base(api_base) and not cp:
        return "local"

    return "huggingface"


def build_completion_kwargs(
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    config_provider: str,
    api_base: str,
) -> dict:
    """Build and return the ``**kwargs`` dict for ``litellm.completion(model, **kwargs)``.

    The returned dict always contains ``messages``.  Other keys (``temperature``,
    ``max_tokens``, ``api_key``, ``api_base``, ``custom_llm_provider``, etc.)
    are added only when the detected provider requires them.

    Raises
    ------
    ValueError
        When a required environment variable (API key) is missing or when
        ``api_base`` is required but not set.
    """
    provider = _detect_provider(model, config_provider, api_base)

    kwargs: dict = {
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # ── OpenAI-compatible providers (nvidia, z-ai/zai, openrouter) ──────
    if provider in _OPENAI_COMPATIBLE_PROVIDERS:
        key_env = _PROVIDER_KEY_MAP.get(provider)
        if key_env:
            api_key = os.getenv(key_env)
            if not api_key:
                raise ValueError(f"{key_env} not found in environment / .env file.")
            kwargs["api_key"] = api_key

        if api_base == "None":
            raise ValueError("api_base not set for custom model")
        kwargs["api_base"] = api_base
        kwargs["custom_llm_provider"] = "openai"

        if provider == "openrouter":
            kwargs["extra_headers"] = {
                "HTTP-Referer": "https://github.com/haseeb-heaven/code-interpreter",
                "X-OpenRouter-Title": "Code Interpreter",
            }

        return kwargs

    # ── OpenAI native (GPT / o-series) ──────────────────────────────────
    if provider == "openai":
        reasoning_model = model.startswith(("o1", "o3", "o4", "gpt-5"))
        if reasoning_model:
            kwargs.pop("temperature", None)
            kwargs["drop_params"] = True
        if api_base != "None":
            kwargs["custom_llm_provider"] = "openai"
            kwargs["api_base"] = api_base
        else:
            if model.startswith(("o1", "o3", "o4")):
                kwargs["custom_llm_provider"] = "openai"
        return kwargs

    # ── Local model ─────────────────────────────────────────────────────
    if provider == "local":
        if api_base == "None":
            raise ValueError("api_base not set for local model")
        kwargs["api_base"] = api_base
        kwargs["custom_llm_provider"] = "openai"
        return kwargs

    # ── Gemini / Groq / Claude / Deepseek / HuggingFace ─────────────────
    # litellm handles routing via the model name; no extra kwargs needed.
    return kwargs
