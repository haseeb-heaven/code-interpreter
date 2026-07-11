# Interpreter 3.3.0 Latest

@haseeb-heaven haseeb-heaven released this Jul 12, 2026

**3.3.0**

---

## Release highlights

* **Gemini-CLI-style agentic mode** via `--gemini-style` (ReAct loop + free/cheap model catalog).
* **Free LLM catalog** with `--list-free` / `--free` / `/free` (OpenRouter free, Groq, Gemini Flash, HF, local).
* **Production resilience**: multi-key rotation, token-bucket rate limiting, circuit breaker, structured error classifier, jitter backoff.
* **Observability**: `logs/metrics.jsonl` and `/key-status`, `/reload-keys`, `/metrics`.
* **CI-friendly CLI**: `--yes` auto-confirms prompts and exits after one file task.
* **Agent modes**: `--agent` multi-agent pipeline and `--agentic` ReAct specialists.
* **Docs**: Updated README screenshots for help, free catalog, code/chat, gemini-style, and agentic runs.

---

## Changelog

* v3.3.0 - Agentic free-LLM UX, key-manager resilience, metrics CLI, non-interactive e2e, refreshed screenshots.
* v3.2.3 - Windows command injection / path traversal fixes, HTTP timeouts, SafetyManager regex precompile, Ollama fixes, expanded tests.
* v3.2.2 - Sandbox default ON, `--sandbox` / `--no-sandbox`, stronger safe-mode protection.

---

## Assets

* Source code (zip)
* Source code (tar.gz)

---

## Quick start

```bash
python interpreter.py --list-free
python interpreter.py --gemini-style -m gemini-2.5-flash-lite
python interpreter.py --agentic --yes -m openrouter-free -f task.txt
```
