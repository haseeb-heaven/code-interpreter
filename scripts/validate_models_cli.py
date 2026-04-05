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
    for line in config_path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if stripped.startswith("HF_MODEL") and "=" in stripped:
            return stripped.split("=", 1)[1].strip().strip("'").strip('"')
    raise ValueError(f"HF_MODEL missing in {config_path}")


def parse_provider(config_path: Path) -> str | None:
    for line in config_path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if stripped.startswith("provider") and "=" in stripped:
            return stripped.split("=", 1)[1].strip().strip("'").strip('"').lower()
    return None


def infer_provider(hf_model: str, explicit_provider: str | None = None) -> str:
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
    text = f"{alias} {hf_model}".lower()
    return "preview" if "preview" in text else "stable"


def list_model_configs() -> list[ModelConfig]:
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
    return {item.strip().lower() for item in value.split(",") if item.strip()}


def can_run_provider(provider: str) -> tuple[bool, str]:
    if provider == "local":
        return False, "SKIPPED (local provider not part of cloud smoke matrix)"
    env_key = PROVIDER_API_KEYS.get(provider)
    if not env_key:
        return False, "SKIPPED (unknown provider)"
    if not os.getenv(env_key):
        return False, f"SKIPPED (missing {env_key})"
    return True, "READY"


def build_stdin(mode: str) -> str:
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
    filtered = [m for m in models if m.provider in providers]
    if tier in {"stable", "preview"}:
        filtered = [m for m in filtered if m.tier == tier]
    return filtered


def main() -> int:
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
