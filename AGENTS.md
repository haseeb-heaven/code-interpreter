# AGENTS.md

## Cursor Cloud specific instructions

Open Code Interpreter is a **single-product, terminal-based Python CLI/TUI** (no web server, no
database). It turns natural-language tasks into code and executes it in a sandbox. It talks to
external LLM providers over HTTP; there is nothing long-running to "start" besides the CLI itself.

### Environment
- Python dependencies live in a virtualenv at `.venv` (gitignored). The startup update script keeps
  it in sync with `requirements.txt`. Activate it with `source .venv/bin/activate` (or call
  `.venv/bin/python` directly) before running any command below.
- Runtime is Python 3.12 here; upstream CI (`.github/workflows/python-app.yml`) pins 3.10. Both work.
- A `.env` file is required at the repo root for the app to start (it is gitignored). Copy it from
  `.env.example` and populate at least one provider key. `initialize_client` validates a key even for
  the `local-model` config (it falls through to the HuggingFace check because the config's `model`
  value is `llama3.1:8b`, which does not contain the string "local"), so a placeholder
  `HUGGINGFACE_API_KEY=hf_...` plus `OPENAI_API_KEY=sk-...` is enough to reach the local endpoint.

### Lint / Test (no external services needed)
- Lint: `flake8 . --select=E9,F63,F7,F82 --show-source --exclude=.venv` (fatal errors only, as CI does).
- Tests: `python -m unittest discover -s tests` — 252 tests, all provider calls are mocked, so no live
  API keys or network are required. `pytest` also works.
- Some passing tests intentionally print argparse `usage:`/error text and `SyntaxWarning` lines to the
  console; that output is expected and does not indicate failure.

### Running the app end-to-end without cloud API keys
The documented "offline model" flow (README → *Offline models setup*) points `configs/local-model.json`
at an OpenAI-compatible endpoint (`api_base`, default `http://localhost:11434/v1`), i.e. LM Studio /
Ollama / vLLM. In this environment there are no provider keys and no Ollama, so end-to-end runs use a
tiny local OpenAI-compatible stub server that returns a fenced code block. The interpreter's real
pipeline (litellm dispatch → HTTP → response parse → code extraction → sandbox execution) runs
unchanged against it.

- The CLI is non-interactive-friendly: pipe the task, then `y` to approve execution, then `/exit`, e.g.
  `printf 'print hello world\ny\n/exit\n' | python interpreter.py --cli -m local-model -md code -dc`.
- Default mode is SAFE MODE (sandboxed); dangerous file ops are blocked outright. Use `--no-sandbox`
  only for trusted local runs.
- `python interpreter.py` with no args launches the arrow-key TUI (needs a real TTY); prefer `--cli`
  for scripted/automated runs.
