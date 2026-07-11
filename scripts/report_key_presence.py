"""Report which provider API keys look real (names only, never values)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

KEYS = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "DEEPSEEK_API_KEY",
    "HUGGINGFACE_API_KEY",
    "NVIDIA_API_KEY",
    "Z_AI_API_KEY",
    "OPENROUTER_API_KEY",
    "BROWSER_USE_API_KEY",
    "OPENAI_API_KEY_1",
    "OPENAI_API_KEY_2",
    "ANTHROPIC_API_KEY_1",
    "GEMINI_API_KEY_1",
]


def looks_real(name: str) -> bool:
    value = (os.getenv(name) or "").strip()
    if not value or len(value) < 16:
        return False
    low = value.lower()
    if any(tok in low for tok in ("your_", "changeme", "placeholder", "example", "xxx", "dummy")):
        return False
    if name == "OPENAI_API_KEY" and "1234567890" in value:
        return False
    return True


if __name__ == "__main__":
    for key in KEYS:
        print(f"{key}: {'PRESENT' if looks_real(key) else 'ABSENT'}")
