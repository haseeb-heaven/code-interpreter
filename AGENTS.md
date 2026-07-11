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
- Tests: `python -m unittest discover -s tests` — provider calls are mocked, so no live API keys or
  network are required. `pytest` also works.
- Feature suites (run separately while iterating):
  - ReAct (`--agentic`): `python -m unittest discover -s tests -p 'test_react*.py'`
  - Multi-agent pipeline (`--agent`): `python -m unittest discover -s tests/agents`
  - Async (#203): `python -m unittest discover -s tests/async`
  - Memory (#204): `python -m unittest discover -s tests/memory`
  - Tools (#205): `python -m unittest discover -s tests/tools`
- TestSprite backend suite (CLI only, no frontend):
  `python -m unittest discover -s testsprite_tests -p 'TC*.py' -v`
- Some passing tests intentionally print argparse `usage:`/error text and `SyntaxWarning` lines to the
  console; that output is expected and does not indicate failure.

### Agent modes (two entrypoints)
- `--agentic` → ReAct loop in `libs/agent/` (Coder / Executor / Reviewer / Debugger) from
  `langgraph-agents`.
- `--agent` → multi-agent pipeline in `libs/agents/` (IntentRouter → Planner → SafetyGuard →
  Executor → Repairer → Verifier → Reviewer). Prefer `AgentPipeline.run_async` / `route_async` /
  `execute_async` for non-blocking work; sync wrappers remain for CLI/tests.
- CLI helpers: `/memory show|clear|stats`, `/tools list|info <name>`.

### TestSprite GitHub App Pre-Check (gotcha)
This is a **CLI-only** product. The TestSprite GitHub App Pre-Check looks for tests registered in the
TestSprite cloud portal (MCP bootstrap + API key), not only local `testsprite_tests/TC*.py` files.
Without a portal project it posts **"No tests detected"**.
`.github/workflows/backend-tests.yml` runs the backend TC suite and then posts a success status on the
`TestSprite Pre-Check` context after those cases pass — that is the intended CLI workaround.
Do **not** add frontend/Playwright TestSprite cases. To use the official portal path instead, set
`TESTSPRITE_API_KEY` and register a backend project.

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
