#!/usr/bin/env python3
"""
Live CLI smoke validation for model configs.

Examples:
  python scripts/validate_models_cli.py --providers gemini,groq --tier stable --mode chat
  python scripts/validate_models_cli.py --providers openai,anthropic,deepseek,huggingface --tier stable --mode chat
  python scripts/validate_models_cli.py --providers nvidia,z-ai,browser-use,openrouter --tier stable --mode chat
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIGS_DIR = ROOT_DIR / "configs"
DEFAULT_INTERPRETER_PATH = ROOT_DIR / "interpreter.py"

ERROR_INDICATORS = (
    "An error occurred interpreter main",
    "Traceback (most recent call last)",
    "not found in .env file",
    "AuthenticationError",
    "Unauthorized",
    "BadRequestError",
    "NotFoundError",
    "model_not_found",
    "404 Not Found",
)

QUOTA_INDICATORS = (
    "RESOURCE_EXHAUSTED",
    "RateLimitError",
    "quota",
    "retry in",
    "requires more credits",
    "upgrade to a paid account",
)

PROVIDER_API_KEYS = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "groq": "GROQ_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "huggingface": "HUGGINGFACE_API_KEY",
    "nvidia": "NVIDIA_API_KEY",
    "z-ai": "Z_AI_API_KEY",
    "browser-use": "BROWSER_USE_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


@dataclass
class ModelConfig:
    alias: str
    hf_model: str
    provider: str
    tier: str


def parse_hf_model(config_path: Path) -> str:
    """
    Extracts the HF_MODEL value from a model config file.
    
    Parameters:
        config_path (Path): Path to a `.config` file to read (UTF-8 with BOM tolerated).
    
    Returns:
        str: The HF_MODEL value with surrounding whitespace and quotes removed.
    
    Raises:
        ValueError: If no `HF_MODEL` assignment is found in the file.
    """
    for line in config_path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if stripped.startswith("HF_MODEL") and "=" in stripped:
            return stripped.split("=", 1)[1].strip().strip("'").strip('"')
    raise ValueError(f"HF_MODEL missing in {config_path}")


def parse_provider(config_path: Path) -> str | None:
    """
    Extracts the provider name from a config file, if specified.
    
    Parameters:
        config_path (Path): Path to a UTF-8 (BOM-tolerant) .config file to scan for a `provider = ...` assignment.
    
    Returns:
        str | None: The provider value lowercased with surrounding quotes and whitespace removed, or `None` if no provider assignment is found.
    """
    for line in config_path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if stripped.startswith("provider") and "=" in stripped:
            return stripped.split("=", 1)[1].strip().strip("'").strip('"').lower()
    return None


def infer_provider(hf_model: str, explicit_provider: str | None = None) -> str:
    """
    Infer the canonical provider identifier for a model based on its Hugging Face model string, with an optional explicit override.
    
    Parameters:
        hf_model (str): The model identifier from the config (used to infer provider by inspecting common prefixes and substrings).
        explicit_provider (str | None): If provided, this value is returned unchanged and no inference is performed.
    
    Returns:
        str: The provider identifier (e.g., "openai", "nvidia", "z-ai", "browser-use", "gemini", "anthropic", "groq", "deepseek", "local", or "huggingface").
    """
    if explicit_provider:
        return explicit_provider
    if hf_model.startswith(("gpt", "o1", "o3", "o4", "gpt-5")):
        return "openai"
    if hf_model.startswith("nvidia/"):
        return "nvidia"
    if hf_model.startswith(("glm-", "z-ai/", "zai/")):
        return "z-ai"
    if hf_model.startswith(("bu-", "browser-use/")):
        return "browser-use"
    if "gemini" in hf_model:
        return "gemini"
    if "claude" in hf_model:
        return "anthropic"
    if hf_model.startswith("groq/") or "groq" in hf_model:
        return "groq"
    if "deepseek" in hf_model:
        return "deepseek"
    if "local" in hf_model:
        return "local"
    return "huggingface"


def infer_tier(alias: str, hf_model: str) -> str:
    """
    Determine whether a model configuration is in the "preview" tier or "stable" tier.
    
    Returns:
        'preview' if either the alias or HF model string contains the substring "preview" (case-insensitive), 'stable' otherwise.
    """
    text = f"{alias} {hf_model}".lower()
    return "preview" if "preview" in text else "stable"


def list_model_configs() -> list[ModelConfig]:
    """
    Discover and parse model configuration files into ModelConfig objects.
    
    Scans CONFIGS_DIR for files matching `*.config` (sorted by filename), extracts each file's alias (stem), `HF_MODEL` value, optional `provider` setting, infers a provider when missing, determines the tier, and returns a list of populated ModelConfig instances.
    
    Returns:
        list[ModelConfig]: List of model configurations with `alias`, `hf_model`, `provider`, and `tier`.
    """
    models: list[ModelConfig] = []
    for config_path in sorted(CONFIGS_DIR.glob("*.config")):
        alias = config_path.stem
        hf_model = parse_hf_model(config_path)
        config_provider = parse_provider(config_path)
        provider = infer_provider(hf_model, explicit_provider=config_provider)
        tier = infer_tier(alias, hf_model)
        models.append(ModelConfig(alias=alias, hf_model=hf_model, provider=provider, tier=tier))
    return models


def parse_csv_set(value: str) -> set[str]:
    """
    Parse a comma-separated string into a set of normalized tokens.
    
    Parameters:
        value (str): Comma-separated items to parse.
    
    Returns:
        set[str]: Lowercased, trimmed, non-empty items from `value`.
    """
    return {item.strip().lower() for item in value.split(",") if item.strip()}


def can_run_provider(provider: str) -> tuple[bool, str]:
    """
    Determine whether the given provider is eligible to run in the cloud smoke test matrix.
    
    Returns:
        tuple: A pair where the first element is `True` if the provider is allowed to run (required API key present) and `False` otherwise. The second element is a human-readable status message explaining the result (e.g., `"READY"` or `"SKIPPED (...)"`).
    """
    if provider == "local":
        return False, "SKIPPED (local provider not part of cloud smoke matrix)"
    env_key = PROVIDER_API_KEYS.get(provider)
    if not env_key:
        return False, "SKIPPED (unknown provider)"
    if not os.getenv(env_key):
        return False, f"SKIPPED (missing {env_key})"
    return True, "READY"


def build_stdin(mode: str) -> str:
    """
    Construct stdin input tailored to the given interpreter mode.
    
    For "chat" this returns a single-sentence chat prompt. For "vision" this returns a path to a test image. For any other mode it returns a tiny code/example prompt. All returned strings end with a line containing "/exit" to terminate the interactive session.
    
    Parameters:
    	mode (str): Interpreter mode; expected values include "chat", "vision", or other modes (e.g., "code", "script", "command").
    
    Returns:
    	str: The complete stdin payload (including trailing newlines and the "/exit" line) to feed to the interpreter.
    """
    if mode == "chat":
        return "Say hello in one sentence.\n/exit\n"
    if mode == "vision":
        return "resources/logo.png\n/exit\n"
    return "Write a tiny hello world example.\nn\n/exit\n"


def run_cli_smoke(
    alias: str,
    mode: str,
    python_bin: str,
    interpreter_path: Path,
    timeout: int,
) -> tuple[str, str]:
    """
    Run the interpreter CLI for the given model alias using the specified Python binary and classify the captured output as PASS, FAIL, or SKIP.
    
    Parameters:
        alias (str): Module alias passed to the interpreter with `-m`.
        mode (str): Mode flag passed to the interpreter (`-md`).
        python_bin (str): Path to the Python executable to invoke.
        interpreter_path (Path): Path to the interpreter script to run.
        timeout (int): Maximum seconds to wait for the interpreter process.
    
    Returns:
        tuple[str, str]: A pair where the first element is one of `"PASS"`, `"FAIL"`, or `"SKIP"`, and the second is a short human-readable message describing the classification (e.g., reason for skip, failure detail, or success note).
    """
    cmd = [python_bin, str(interpreter_path), "-m", alias, "-md", mode, "-dc"]
    stdin_data = build_stdin(mode)
    try:
        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        completed = subprocess.run(
            cmd,
            cwd=str(ROOT_DIR),
            input=stdin_data,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=child_env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "FAIL", "Timed out"

    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    if any(indicator in output for indicator in QUOTA_INDICATORS):
        return "SKIP", "Rate-limit or quota exhausted for this model/key"
    if any(indicator in output for indicator in ERROR_INDICATORS):
        return "FAIL", "Error indicator found in CLI output"
    if "Welcome to" not in output or ("OS=" not in output and "OS:" not in output):
        return "FAIL", "Interpreter did not reach normal startup/output sequence"
    return "PASS", "CLI smoke succeeded"


def filter_models(
    models: Iterable[ModelConfig],
    providers: set[str],
    tier: str,
) -> list[ModelConfig]:
    """
    Filter a sequence of ModelConfig objects by provider membership and optional tier.
    
    Parameters:
        models (Iterable[ModelConfig]): Iterable of model configurations to filter.
        providers (set[str]): Set of provider names; only models whose `provider` is in this set are kept.
        tier (str): If "stable" or "preview", only models with a matching `tier` are kept; any other value (e.g., "all") disables tier filtering.
    
    Returns:
        list[ModelConfig]: List of models that match the provider set and optional tier filter.
    """
    filtered = [m for m in models if m.provider in providers]
    if tier in {"stable", "preview"}:
        filtered = [m for m in filtered if m.tier == tier]
    return filtered


def main() -> int:
    """
    Run CLI smoke validation for selected model configurations and return an exit code.
    
    Parses command-line options to select providers, tier, mode, timeouts, Python executable, and interpreter entrypoint; discovers and filters model configs; for each eligible model invokes the interpreter CLI, classifies the result as PASS/FAIL/SKIP, prints per-model lines and a final summary, and accumulates pass/fail/skip counts.
    
    Returns:
        int: `0` if no models failed; `1` if one or more models failed or if no models matched the filters.
    """
    load_dotenv(dotenv_path=ROOT_DIR / ".env", override=False)

    parser = argparse.ArgumentParser(description="Validate model configs via interpreter CLI smoke checks")
    parser.add_argument(
        "--providers",
        type=str,
        default="openai,gemini,anthropic,groq,deepseek,huggingface,nvidia,z-ai,browser-use,openrouter",
        help="Comma-separated providers",
    )
    parser.add_argument("--tier", choices=["stable", "preview", "all"], default="stable")
    parser.add_argument("--mode", choices=["chat", "code", "script", "command", "vision"], default="chat")
    parser.add_argument("--timeout", type=int, default=120, help="Per-model timeout in seconds")
    parser.add_argument("--python", type=str, default=sys.executable, help="Python executable")
    parser.add_argument("--interpreter", type=Path, default=DEFAULT_INTERPRETER_PATH, help="Interpreter entrypoint")
    args = parser.parse_args()

    selected_providers = parse_csv_set(args.providers)
    all_models = list_model_configs()
    targets = filter_models(all_models, selected_providers, args.tier)

    if not targets:
        print("No models matched the provided filters.")
        return 1

    print(f"Selected models: {len(targets)}")
    print(f"Providers: {','.join(sorted(selected_providers))}")
    print(f"Tier: {args.tier} | Mode: {args.mode}")
    print("-" * 80)

    passed = 0
    failed = 0
    skipped = 0

    for model in targets:
        can_run, reason = can_run_provider(model.provider)
        if not can_run:
            skipped += 1
            print(f"SKIP  {model.alias:32} [{model.provider:10}] {reason}")
            continue

        status, message = run_cli_smoke(
            alias=model.alias,
            mode=args.mode,
            python_bin=args.python,
            interpreter_path=args.interpreter,
            timeout=args.timeout,
        )
        if status == "PASS":
            passed += 1
            print(f"PASS  {model.alias:32} [{model.provider:10}] {message}")
        elif status == "SKIP":
            skipped += 1
            print(f"SKIP  {model.alias:32} [{model.provider:10}] {message}")
        else:
            failed += 1
            print(f"FAIL  {model.alias:32} [{model.provider:10}] {message}")

    print("-" * 80)
    print(f"Summary: PASS={passed} FAIL={failed} SKIPPED={skipped} TOTAL={len(targets)}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
