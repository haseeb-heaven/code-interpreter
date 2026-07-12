![Interpreter](https://github.com/haseeb-heaven/open-code-interpreter/blob/main/resources/movie.gif?raw=true)

### **Hosting and Spaces:**
[![Colab](https://img.shields.io/badge/Google-Colab-blue)](https://colab.research.google.com/drive/1jGg-NavH8t4W2UVs8MyVMv8bs49qggfA?usp=sharing)
[![Replit](https://img.shields.io/badge/Replit-IDE-blue)](https://replit.com/@HaseebMir/open-code-interpreter)
[![PyPi](https://img.shields.io/badge/PyPi-Package-blue)](https://pypi.org/project/open-code-interpreter/)
[![Building](https://github.com/haseeb-heaven/Open-Code-Interpreter/actions/workflows/python-app.yml/badge.svg)](https://github.com/haseeb-heaven/Open-Code-Interpreter/actions/workflows/python-app.yml)
[![CI](https://github.com/haseeb-heaven/code-interpreter/actions/workflows/ci.yml/badge.svg)](https://github.com/haseeb-heaven/code-interpreter/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/haseeb-heaven/code-interpreter/branch/develop/graph/badge.svg)](https://codecov.io/gh/haseeb-heaven/code-interpreter)

### **Support Project:**
<a href="https://www.buymeacoffee.com/haseebheaven">
    <img src="https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=&slug=haseebheaven&button_colour=40DCA5&font_colour=ffffff&font_family=Cookie&outline_colour=000000&coffee_colour=FFDD00" width="200" height="50" />
</a>
<a href="https://ko-fi.com/heavenhm">
    <img src="https://img.shields.io/badge/KoFi-ffdd00?style=for-the-badge&logo=Ko-fi&logoColor=orange" width="200" height="50" />
</a>

# Task-based Agentic Terminal — Free, Local, Any Model

> A powerful task-based agentic terminal and open-source alternative to ChatGPT Code Interpreter.
> Describe a task in plain English. Get the result. No coding required.

```bash
pip install open-code-interpreter
python interpreter.py --free "analyze sales.csv and plot top 10 customers"
```

✅ Works with free models (Gemini, Groq, OpenRouter — no paid API required)  
✅ Runs on your machine — your files never leave your computer  
✅ Windows, Mac, Linux  
✅ Drop-in replacement for the abandoned Open Interpreter

## Quick start with `--free` (zero-cost models)

The `--free` flag is the fastest way to try Code Interpreter without paid APIs:

```bash
# Prefer a free/cheap model from the built-in catalog
python interpreter.py --free "analyze this CSV"

# List curated free/cheap presets (OpenRouter free, Groq, Gemini Flash, Ollama, …)
python interpreter.py --list-free

# In-session: type /free to see zero-cost options
```

## Why not Open Interpreter?

| | Code Interpreter (this project) | Open Interpreter |
|---|---|---|
| Last updated | Active ✅ | Abandoned (Apr 2025) ❌ |
| Free models built-in | Yes — `--free` flag ✅ | No ❌ |
| Windows support | Full ✅ | Broken on Windows ❌ |
| Safety layer | Yes ✅ | No ❌ |
| pip install | Yes ✅ | Yes ✅ |

## **How We Compare**

| Feature | **Code-Interpreter** | [Open-Interpreter](https://github.com/OpenInterpreter/open-interpreter) | [Gemini CLI](https://github.com/google-gemini/gemini-cli) |
|---|:---:|:---:|:---:|
| **License** | ✅ MIT | ✅ AGPL-3.0 | ✅ Apache-2.0 |
| **Interface** | Terminal CLI + TUI | Terminal REPL | Terminal REPL |
| **Multi-model support** | ✅ 10+ providers | ✅ Any LLM | ❌ Gemini only |
| **Local / Offline models** | ✅ Ollama + LM Studio | ✅ Ollama | ❌ None |
| **Free tier (`--free`)** | ✅ Built-in catalog | ⚠️ Self-hosted only | ✅ Gemini free tier |
| **Zero-cost usage** | ✅ `--free` + Ollama | ⚠️ Self-hosted only | ⚠️ Rate-limited |
| **Agentic / Autonomous mode** | ✅ `--agentic` + `--yolo` | ✅ Default | ✅ ReAct loop |
| **Safety layer** | ✅ Dedicated SafetyGuard + Sandbox | ⚠️ Basic sandbox | ✅ Sandbox |
| **MCP support** | ✅ `--mcp-server` | ❌ | ✅ |
| **Web search** | ✅ `--search` (DDG/Tavily/Serper) | ❌ | ✅ Google Search |
| **Token streaming** | ✅ `--stream` / `--no-stream` | ✅ | ✅ |
| **Multimodal image input** | ✅ `--image` / `/image` + `vision` mode | ✅ | ✅ |
| **Code execution** | ✅ Python, JS, C++ | ✅ Python + shell | ✅ Python + shell |
| **TUI (arrow-key UI)** | ✅ Built-in | ❌ | ❌ |
| **Git auto-commit** | ❌ | ❌ | ❌ |
| **IDE integration** | ❌ Terminal only | ❌ Terminal only | ❌ Terminal only |
| **Persistent sessions** | ✅ `--session` / `/session` | ⚠️ In-process only | ❌ |
| **Structured output (`--output-format`)** | ✅ `json` / `markdown` / `plain` | ❌ | ❌ |
| **pip installable** | ✅ `pip install open-code-interpreter` | ✅ | ❌ |
| **Windows support** | ✅ Full | ⚠️ Partial | ⚠️ Partial |
| **Best fit** | Task-based Agentic Terminal | Natural-language computer control | Gemini-native agentic CLI |

> ✅ = Fully supported · ⚠️ = Partial / limited · ❌ = Not supported · 🔜 = On roadmap

## Table of Contents
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Examples](#examples)
- [TUI Screenshots](#tui-screenshots)
- [Agentic & Free LLMs](#agentic--free-llms)
- [Settings](#settings)
- [Contributing](#contributing)
- [Versioning](#versioning)
- [Changelog](#changelog)
- [License](#license)
- [Acknowledgments](#acknowledgments)

## **Installation**

### Installation with Python package manager
To install Code-Interpreter, run the following command:

```bash
pip install open-code-interpreter
```

Then try a free model immediately:

```bash
python interpreter.py --free "analyze sales.csv and plot top 10 customers"
```

Or pick a specific model:

```bash
python interpreter.py -m 'z-ai-glm-5' -md 'code'
```

Make sure you install required packages before running the interpreter and have API keys setup in the `.env` file (local / Ollama configs skip cloud key checks).

### Installation with Git
To get started with Code-Interpreter, follow these steps:

1. Clone the repository:

```bash
git clone https://github.com/haseeb-heaven/code-interpreter.git
cd code-interpreter
```

2. Install the required packages:

```bash
pip install -r requirements.txt
```

3. Copy the example environment file and add the keys you plan to use:

```bash
copy .env.example .env
```

## API Key setup for All models

Follow the steps below to obtain and set up the API keys for each service:

1. **Obtain the API keys:**
    - HuggingFace: Visit [HuggingFace Tokens](https://huggingface.co/settings/tokens) and get your Access Token.
    - Google Gemini: Visit [Google AI Studio](https://makersuite.google.com/app/apikey) and click on the **Create API Key** button.
    - OpenAI: Visit [OpenAI Dashboard](https://platform.openai.com/account/api-keys), sign up or log in, navigate to the API section in your account dashboard, and click on the **Create New Key** button.
    - Groq AI: Visit [Groq AI Console](https://console.groq.com/keys), sign up or log in, and click on the **Create API Key** button.
    - Anthropic AI: Visit [Anthropic AI Console](https://console.anthropic.com/settings/keys), sign up or log in, and click on the **Create Key** button.
    - NVIDIA API Catalog: Visit [NVIDIA Build](https://build.nvidia.com/), create a key, and use `NVIDIA_API_KEY`.
    - Z AI: Visit [Z AI Docs](https://docs.z.ai/) and use `Z_AI_API_KEY`.
    - OpenRouter: Visit [OpenRouter Keys](https://openrouter.ai/settings/keys) and use `OPENROUTER_API_KEY`.
    - Cerebras: Visit [Cerebras Cloud](https://cloud.cerebras.ai/) (free public endpoints, rate-limited) and use `CEREBRAS_API_KEY`.
    - Browser Use: Visit [Browser Use Docs](https://docs.browser-use.com/) and use `BROWSER_USE_API_KEY`.

2. **Save the API keys:**

Create a `.env` file in your project root directory and add the following lines:

```bash
export HUGGINGFACE_API_KEY="Your HuggingFace API Key"
export GEMINI_API_KEY="Your Google Gemini API Key"
export OPENAI_API_KEY="Your OpenAI API Key"
export GROQ_API_KEY="Your Groq API Key"
export ANTHROPIC_API_KEY="Your Anthropic API Key"
export DEEPSEEK_API_KEY="Your Deepseek API Key"
export NVIDIA_API_KEY="Your NVIDIA API Key"
export Z_AI_API_KEY="Your Z AI API Key"
export OPENROUTER_API_KEY="Your OpenRouter API Key"
export CEREBRAS_API_KEY="Your Cerebras API Key"
export BROWSER_USE_API_KEY="Your Browser Use API Key"
```

## Data Analysis Engine

Smart ingestion, offline EDA, chart gallery, cleaning, SQL, and exports:

```bash
# Offline EDA summary + load dataset into the session
python interpreter.py --eda sales.csv --cli -m local-model

# Attach a file for schema-aware prompting
python interpreter.py --attach sales.csv -t "find outliers in revenue"

# Prefer Plotly interactive HTML charts
python interpreter.py --interactive-charts --attach sales.csv --cli
```

In the REPL:

| Command | Purpose |
|---|---|
| `/eda file.csv` | Offline EDA + load dataset |
| `/clean all` | Whitespace, dupes, types, dates, nulls |
| `/sql SELECT * FROM data LIMIT 10` | SQL via DuckDB/SQLite |
| `/export report` | HTML report with embedded charts |
| `/charts` | List saved charts under `~/.code_interpreter/charts` |
| `/templates data` | Copy-paste analysis prompts |
| `/chart-style plotly` | Prefer interactive charts |

R scientists: `python interpreter.py -l r --cli` (requires `Rscript` on PATH).

## For Scientists

```bash
# Scientific prompting + publication theme
python interpreter.py --science --plot-theme paper --attach experiment.csv "run ANOVA across groups"

# EDA + PDF report
python interpreter.py --eda experiment.csv --report --cli -m local-model

# In REPL: /notebook, /ml classify target, /output full
```

This Interpreter supports offline models via **LM Studio** and **Ollama**. Follow the steps below:

### Ollama first-class (recommended)

```bash
# Start Ollama, then auto-pick a local model
ollama serve
python interpreter.py --ollama "summarize notes.txt"

# Or pick a specific installed model
python interpreter.py --ollama llama3 "rename PDFs with today's date"

# List installed Ollama models
python interpreter.py --list-ollama

# Truly local: local model + attached local files (privacy banner)
python interpreter.py --local --attach sensitive_data.csv "summarize this for me"
```

Attach files mid-session with `/file path`, list with `/files`, clear with `/clear-files`.
(`--file` / `-f` still means "read the task prompt from a file".)

### LM Studio / manual local-model config

- Download any model from [LM Studio](https://lmstudio.ai/) like _Phi-2, Code-Llama, Mistral_.
- In the app go to **Local Server** option and select the model.
- Start the server and copy the **URL** (LM-Studio will provide you with the URL).
- Run command `ollama serve` and copy the **URL** (Ollama will provide you with the URL).
- Open `configs/models.toml`, find the `[models."local-model"]` table, and paste the **URL** into the `api_base` field.
- Set the model name to `local-model` and run the interpreter.

```bash
python interpreter.py -md 'code' -m 'local-model'
```

## **Features**

- 🚀 Executes generated code from instructions
- 💾 Saves and edits code with advanced editor
- 📡 Supports offline models via LM Studio and Ollama
- 📜 Command history and mode selection
- 🧠 Multiple models and languages (Python/JavaScript)
- 👀 Code review before execution
- 🛡️ Safe sandbox execution with timeout and security
- 🔁 Self-repair for failed executions
- 💻 Cross-platform (Windows/macOS/Linux)
- 🤝 Integrates with HuggingFace, OpenAI, Gemini, Groq, Claude, DeepSeek, NVIDIA, Z AI, Cerebras, OpenRouter, Browser Use
- 🎯 Versatile tasks: file ops, image/video editing, data analysis
- 🔌 Native FS/shell tool registry + MCP stdio client for autonomous agent loops (`--yolo`, `--mcp-server`)
- ⚡ Token streaming (`--stream` / `--no-stream`) and multimodal image input (`--image`, `/image`)
- 🌐 Web search tool (`--search`, `/search`) via DuckDuckGo / Tavily / Serper
- 🧩 Code generation without execution: `--mode generate` (snippet) and `--mode project` (scaffold)
- 📝 Structured output for scripting: `--output-format json|markdown|plain`
- 💾 Persistent sessions: `--session` / `--list-sessions` / `/session`
- 📊 Data analysis engine: `--eda`, `--attach`, charts, SQL, exports
- 🧪 Science mode: `--science`, notebooks, plot themes, ML helpers, PDF reports
- 🐳 Sandbox backends: `--sandbox subprocess|docker`, `--timeout`, `--safety` levels

## **Safety Features**

### Mode Indicator
The interpreter displays the current safety mode in the session banner:
- **[SAFE MODE]** - Default mode with safety restrictions enabled (green)
- **[UNSAFE MODE ⚠️]** - Unrestricted mode (red with warning emoji)

### Dangerous Operation Handling
The interpreter handles dangerous operations with a single confirmation prompt:

**SAFE MODE:**
- Dangerous operations are **blocked entirely** (no confirmation prompt)
- You will see: `❌ Dangerous operation blocked in SAFE MODE.`
- No file deletion or modification operations are allowed

**UNSAFE MODE:**
- Single prompt for ALL operations (safe or dangerous)
- Safe operations: `Execute the code? (Y/N):`
- Dangerous operations: `⚠️ Dangerous operation. Continue? (Y/N):`
- Operations execute only if you confirm with `Y`

To enable unsafe mode:
```bash
python interpreter.py --unsafe
```

To enable safe mode:
```bash
python interpreter.py --sandbox
```

> **Warning:** Use unsafe mode with caution. Dangerous operations can delete or modify your files.

## 🛠️ **Usage**

To use Code-Interpreter, use the following command options:

- List of all **programming languages**:
    - `python` - Python programming language.
    - `javascript` - JavaScript programming language.

- List of all **modes**:
    - `code` - Generates code from your instructions.
    - `script` - Generates shell scripts from your instructions.
    - `command` - Generates single line commands from your instructions.
    - `vision` - Generates description of image or video.
    - `chat` - Chat with your files and data.

- See [Models.MD](Models.MD) for the complete list of supported models.

### Start TUI (default)
```bash
python interpreter.py
```

`python interpreter.py` opens the TUI and uses arrow-key navigation in a real terminal. The TUI falls back to plain text prompts when stdin is piped or not attached to a terminal.

**Persisted wizard config.** The first bare run above saves your answers to `~/.code-interpreter/config.json` (model *name*, mode, sandbox/safety choice, session name, etc. — never API keys). Every later bare `python interpreter.py` skips the wizard and reuses that saved config directly. Pass `--config` to force the wizard to run again (e.g. to change your setup) — it re-saves your answers afterward:

```bash
# Re-run the setup wizard and persist the new answers
python interpreter.py --config
```

Any explicit CLI flag (`-m`, `--agentic`, `--cli`, `--yes`, ...) still takes precedence over both the wizard and the saved config, exactly as before.

### Open CLI mode
```bash
python interpreter.py --cli
```

`python interpreter.py --cli` automatically picks the best configured model from your `.env` file if you do not pass `-m`.

### Gemini-CLI-style agentic REPL (free LLMs)
Open Code Interpreter can run a **Gemini-CLI-inspired** agentic REPL with curated free/cheap models (OpenRouter free, Groq, Gemini Flash free tier, HuggingFace, Ollama/local):

```bash
# Prefer free model — the primary zero-cost path
python interpreter.py --free "analyze this CSV"

# List curated free/cheap presets
python interpreter.py --list-free

# Agentic ReAct REPL + prefer free model when -m omitted
python interpreter.py --gemini-style

# Pick a specific free preset
python interpreter.py --gemini-style -m openrouter-free
python interpreter.py --gemini-style -m groq-llama-3.1-8b
python interpreter.py --gemini-style -m gemini-2.5-flash
python interpreter.py --gemini-style -m local-model

# Prefer free model without enabling agentic mode
python interpreter.py --cli --free -md code
```

In the agentic REPL (and classic `--cli`), use `/free` to discover presets and `/model <name>` to switch.

See the `[[free_catalog]]` entries in `configs/models.toml` for the curated list. Existing `--agentic` / `--agent` flags remain unchanged.

#### Thought-only live view (default) vs. `--verbose`

By default, `--agentic` shows only the **Thought** panels, back-to-back — no per-step "Action"/"Observation"
panels, and no retry/fallback log chatter ("Rate limited; sleeping…", "Retrying … after rate limit…", "Free model
fallback succeeded…"). The final result/summary and the workflow completion status (`Status`/`Steps`/`Tokens`/`Cost`)
always print, and the full trajectory is still logged to `logs/agent_react.jsonl` regardless of what's shown live.

```bash
# Default: Thought-only quiet view
python interpreter.py --agentic --yes -m openrouter-free -f task.txt

# Full detail: restores Action/Observation panels + retry/fallback logs
python interpreter.py --agentic --verbose --yes -m openrouter-free -f task.txt
python interpreter.py --agentic -V --yes -m openrouter-free -f task.txt
```

In the agentic REPL, toggle it at runtime with `/verbose` (alongside `/free`, `/model`, `/settings`, `/help`).

#### Startup UI

Every genuinely interactive session — the arrow-key TUI wizard, classic `--cli` REPL, `--agentic`, the
autonomous `--yolo` loop, and `--gemini-style` — opens with a blocky, gradient "INTERPRETER" wordmark
(blue → purple → pink, built from Unicode block-drawing glyphs via `libs/agent/gemini_ui.py`). One-shot
`-f`/prompt-file runs and structured (`--output-format json|markdown`) runs skip it, since there's no one
watching a live terminal to show it to. The banner is "persistent": it redraws immediately after any
`/clear` (or other `UtilityManager.clear_screen()` call), so it visually stays pinned to the top of the
screen. `--gemini-style` additionally shows a real-capability "Tips for getting started" list (`/free`,
`/model`, `/settings`, `/help`) and a status bar re-printed above each prompt showing the current
directory, sandbox state (`sandboxed (SAFE MODE)` vs `no sandbox`), and confirm mode (`auto`
vs `manual confirm`) — the same visual language as [Gemini CLI](https://github.com/google-gemini/gemini-cli),
rebranded for this project. ReAct steps that write code render in a bordered, line-numbered panel
(`libs/agent/step_ui.py`'s `GeminiStepPresenter`), similar to Gemini CLI's `WriteFile` tool-call box.
Legacy cp1252 Windows consoles (`cmd.exe` / old `conhost`) and narrow terminals automatically fall back to
a plain ASCII banner and icons instead of the block-drawing glyphs.

### Structured output (`--output-format`)
Machine-readable results for shell pipelines, CI, and editor wrappers. Non-TTY (piped) stdout auto-selects JSON and disables colors; override with an explicit format.

```bash
# Explicit JSON (works in a terminal or when piped)
python interpreter.py --cli --yes --output-format json -m local-model -md code -f task.txt

# Extract generated code with jq
python interpreter.py --cli --yes --output-format json -m local-model -f task.txt | jq -r '.code'

# Markdown sections for docs / PR bodies
python interpreter.py --cli --yes --output-format markdown -m local-model -f task.txt

# Piped without a format flag → auto JSON + no color
python interpreter.py --cli --yes -m local-model -f task.txt | jq '.status'

# Force plain text even when piped
python interpreter.py --cli --yes --output-format plain -m local-model -f task.txt | grep -i print
```

JSON schema (stable):

```json
{
  "status": "success",
  "result": "…",
  "code": "print('Hello')",
  "execution_output": "Hello\n"
}
```

Use `--no-color` to strip ANSI codes in plain mode.

### Persistent sessions (`--session`)
Resume named conversations across runs. Sessions are stored under `~/.code-interpreter/sessions/<id>.json`.

```bash
# Start or resume a named session
python interpreter.py --cli --session my-project -m local-model

# List / delete sessions (no API keys required)
python interpreter.py --list-sessions
python interpreter.py --delete-session old-project

# Wipe and restart a session name
python interpreter.py --cli --session my-project --new-session

# In-REPL
#   /session info | save | clear
#   /sessions
```

### Run with sandbox (safe)
```bash
python interpreter.py --tui --sandbox
python interpreter.py --cli --sandbox subprocess --timeout 60
python interpreter.py --cli --sandbox docker "analyze this CSV safely"
```

### Security levels & hardening (#225)

| Flag | Behavior |
|---|---|
| `--safety strict` | Block network, file writes, and shell — pure computation only |
| `--safety standard` | Default: regex/AST dangerous-pattern blocking + CWD sandbox |
| `--safety relaxed` | Warn only; still logs to the audit trail |
| `--safety off` | No checks (prefer with `--sandbox docker`) |
| `--sandbox docker` | Run code in a read-only, network-disabled Docker container |
| `--timeout 60` | Kill sandboxed execution after 60 seconds |

Also included:
- Pre-execution **secret scanning** (API keys / tokens) with confirm prompt
- **Audit log** at `~/.code_interpreter/audit.jsonl` (`/audit`, `/audit full`, `/audit clear`)
- Optional path deny-list: `~/.config/code_interpreter/ignore` (gitignore-style patterns)

> Recommended for beginners: `--safety strict`  
> Default: `--safety standard`  
> Power users: `--yolo --safety off --sandbox docker`

### Run without sandbox (unsafe)
```bash
python interpreter.py --cli --no-sandbox
```

### Upgrade interpreter
```bash
python interpreter.py --upgrade
```

### Live CLI smoke validation (stable models only)
```bash
python scripts/validate_models_cli.py --providers gemini,groq --tier stable --mode chat
python scripts/validate_models_cli.py --providers openai,anthropic,deepseek,huggingface --tier stable --mode chat
python scripts/validate_models_cli.py --providers nvidia,z-ai,browser-use,openrouter --tier stable --mode chat
python scripts/validate_models_cli.py --providers cerebras --tier stable --mode chat
```

### Direct provider examples
```bash
python interpreter.py -m 'nvidia-nemotron' -md 'chat' -dc
python interpreter.py -m 'z-ai-glm-5' -md 'chat' -dc
python interpreter.py -m 'openrouter-free' -md 'chat' -dc
python interpreter.py -m 'openrouter-qwen3-coder' -md 'chat' -dc
python interpreter.py -m 'cerebras-gpt-oss-120b' -md 'chat' -dc
python interpreter.py -m 'browser-use-bu-max' -md 'chat' -dc
```

Last verified model baseline: **April 5, 2026**.

## **TUI Screenshots**

The TUI flow is designed for fast keyboard-first setup. Run `python interpreter.py` or `python interpreter.py --tui` to launch the selector UI, then use the arrow keys to choose the same user-facing options the CLI exposes.

### Mode selection
Choose between `code`, `chat`, `script`, `command`, `vision`, plus codegen-only `generate` / `project`.

### Workflow and flags (TUI / CLI parity)
After mode, the TUI also lets you pick:

- **Workflow** — classic, `--agentic` (ReAct), `--agent` (multi-agent pipeline), or `--gemini-style`
- **Free/cheap presets** — `--free` catalog models from the `[[free_catalog]]` entries in `configs/models.toml`
- **Sandbox / safety** — `subprocess` | `docker` | `off`, and `--safety` levels
- **Streaming / search / output** — `--stream`, `--search`, `--output-format`
- **Session** — optional `--session` name
- **Advanced** (opt-in) — "Configure advanced options?" **no** (the default) skips *every* advanced prompt below and uses their existing defaults; **yes** asks each one: `--yolo`, `--yes`, `--science`, `--interactive-charts`, `--image`, `--attach`, `--mcp-server`, plus the session name

Selections are written onto the same argparse `Namespace` the CLI uses, so runtime behavior matches flag-driven starts. They're also saved to `~/.code-interpreter/config.json` so the wizard doesn't run again on the next bare invocation — see *Persisted wizard config* above and `--config` in `--help`.

Cancelling any selector (Ctrl+C or Esc) exits cleanly with a short `Cancelled.` message instead of a traceback.

![TUI mode selection](resources/interpreter-tui-mode-selection.png)

### Model selection
Pick your provider and model directly from the terminal without typing long aliases manually.

![TUI model selection](resources/interpreter-tui-model-selection.png)

### Live output
After entering the session, generated code and execution output remain inside the terminal flow with the same safer runtime behavior used by the CLI.

![TUI output](resources/interpreter-tui-output.png)

### Sandbox Security
You can enable or disable sandbox mode directly from the terminal session. This makes it easy to switch between the safer isolated runtime and unrestricted execution when needed.

![Sandbox enable / SAFE MODE](resources/interpreter-sandbox-enable.png)

When sandbox mode is enabled, commands and generated code run with the same safer execution constraints used by the CLI.

![TUI sandbox disable](resources/interpreter-sandbox-disable.png)

When sandbox mode is disabled, execution runs in unsafe mode without sandbox restrictions, intended only for trusted local workflows.

## **Agentic & Free LLMs**

v3.3.0 added Gemini-CLI-style agentic UX and resilience. **v3.4.0** adds MCP/tools, streaming + vision, sessions, structured output, data/science engines, Docker sandbox levels, and CI/coverage.

### Help & flags
![CLI help (v3.3)](resources/interpreter-help-v33.png)

### Free / cheap model catalog
```bash
python interpreter.py --list-free
python interpreter.py --gemini-style -m gemini-2.5-flash-lite
python interpreter.py --agentic --yes -m openrouter-free -f task.txt
```

![Free LLM catalog](resources/interpreter-list-free.png)

### Code mode (CLI)
![Code mode](resources/interpreter-mode-code.png)

### Chat mode (CLI)
![Chat mode](resources/interpreter-mode-chat.png)

### Gemini-style agentic REPL
Blocky gradient "INTERPRETER" wordmark, tips list, and a cwd/sandbox/confirm-mode status bar — see
[*Startup UI*](#gemini-cli-style-agentic-repl-free-llms) above for details.

![Gemini-style ReAct](resources/interpreter-gemini-style.png)

### ReAct `--agentic` workflow
![Agentic ReAct](resources/interpreter-agentic.png)

### Autonomous tool loop (`--yolo`) + MCP
Fully autonomous FS/shell tools (`read_file`, `write_file`, `list_dir`, `run_shell`, `glob_search`) via an OpenAI-style tool-calling loop. Optional MCP servers attach extra tools over stdio JSON-RPC.

Put `--mcp-server` last so server args like `npx -y ...` are not parsed as interpreter flags.

```bash
# YOLO — no approval prompts (use with caution)
python interpreter.py --yolo -m local-model -f task.txt --yes

# Confirm each tool call (interactive)
python interpreter.py --cli -m local-model --mcp-server npx -y @modelcontextprotocol/server-filesystem .

# Combine YOLO + MCP (--mcp-server last)
python interpreter.py --yolo --yes -f task.txt --mcp-server npx -y @modelcontextprotocol/server-filesystem .
```

In the autonomous REPL: `/tools` lists registered tools; `/model`, `/free`, `/exit` work as usual.

### Streaming + multimodal images
```bash
# Stream tokens (default). Disable with --no-stream
python interpreter.py --cli -m gpt-4o --stream -md chat

# Gemini-style always streams
python interpreter.py --gemini-style -m gemini-2.5-flash

# Pass one or more images with a prompt file / REPL task
python interpreter.py --cli -m gpt-4o --image ./diagram.png -md chat
python interpreter.py --cli -m gpt-4o --image ./before.png ./after.png -md chat

# In-REPL
# /image ./screenshot.png
# → then type your question about the image
```

### Web search (`--search`)
Enable an LLM-callable `web_search` tool (and the `/search` REPL command). DuckDuckGo is the default and needs no API key; set `TAVILY_API_KEY` / `SERPER_API_KEY` or pass `--search-provider` for premium backends.

```bash
# DuckDuckGo (free)
python interpreter.py --gemini-style --search -m local-model

# With YOLO autonomy so the agent can call web_search mid-task
python interpreter.py --yolo --search --yes -m local-model -f task.txt

# Tavily / Serper
python interpreter.py --search --search-provider tavily --search-api-key "$TAVILY_API_KEY" --cli
```

In the REPL: `/search latest litellm version`

### Code generation (no execution)
Produce a snippet or multi-file project scaffold without running code:

```bash
# Single snippet → file
python interpreter.py --mode generate -t "write a binary search function in Python" -o output/bs.py -m local-model

# Full project scaffold → directory (includes main entry, README.md, requirements.txt)
python interpreter.py --mode project -t "create a REST API with FastAPI and SQLite" -o output/my_api -m local-model

# Task from a prompt file
python interpreter.py --mode generate -f task.txt -o output/snippet.py -m local-model
```

Existing interpret modes (`code`, `script`, `command`, `vision`, `chat`) are unchanged.

## 🖥️ **Interpreter Commands**

Here are the available commands:

- 📝 `/save` - Save the last code generated.
- ✏️ `/edit` - Edit the last code generated.
- ▶️ `/execute` - Execute the last code generated.
- 🔄 `/mode` - Change the mode of interpreter.
- 🔄 `/model` - Change the model of interpreter.
- 📦 `/install` - Install a package from npm or pip.
- 🌐 `/language` - Change the language of the interpreter.
- 🧹 `/clear` - Clear the screen.
- 🆘 `/help` - Display this help message.
- 🚪 `/list` - List all the _models/modes/language_ available.
- 📝 `/version` - Display the version of the interpreter.
- 🚪 `/exit` - Exit the interpreter.
- 🐞 `/fix` - Fix the generated code for errors.
- ⚙️ `/settings` - Open interactive TUI settings when running with `--tui`.
- 📜 `/log` - Toggle different modes of logging.
- ⏫ `/upgrade` - Upgrade the interpreter.
- 📁 `/prompt` - Switch the prompt mode _File or Input_ modes.
- 🐞 `/debug` - Toggle Debug mode for debugging.
- 📦 `/sandbox` - Toggles secure sandbox system.
- 🔑 `/key-status` - Show API key pool / circuit breaker status.
- 🔄 `/reload-keys` - Reload API keys from `.env` without restart.
- 📊 `/metrics` - Show LLM call metrics summary.
- 🆓 `/free` - List curated free/cheap LLM presets.
- 🖼️ `/image` - Attach an image path/URL, then ask a multimodal question.
- 🌐 `/search` - Search the web (DuckDuckGo by default).

## **Settings**

All model configuration lives in a single human-editable registry file: **`configs/models.toml`**.
It replaces the old per-model JSON files with one TOML document containing:

- `default_model` / `[[default_priority]]` — which model is picked when `-m` is omitted, keyed off
  which provider API key is present in your environment (checked in order).
- `[models."<key>"]` tables — one per model, e.g. `[models."gpt-4o"]`, `[models."gemini-2.5-flash"]`,
  `[models."local-model"]`. Supported fields: `model` (litellm-style id, required), `provider`,
  `api_base`, `temperature`, `max_tokens`, `notes`, plus optional extras like `timeout_seconds`,
  `rate_limits`, `circuit_breaker`, `browser_use_timeout`, `browser_use_poll_interval`.
- `[[free_catalog]]` — the curated rotation used by `--free` / `/free` / `--list-free` and the
  automatic free-fallback logic. Each entry has `id`, `model_key` (points at a `[models.*]` table),
  `provider`, `env_key` (API key env var required, or omit for local/no-key models), `tier`, `notes`.

The registry is loaded by `libs/core/model_registry.py` (`tomllib` on Python 3.11+, the `tomli`
backport on 3.10) and cached until the file's mtime changes, so edits are picked up automatically.

### Steps to add your own custom API Server
To integrate your own API server for OpenAI (or any provider) instead of the default endpoint:

1. Open `configs/models.toml`.
2. Find (or add) the `[models."<your-model-key>"]` table for the model you want to modify.
3. Add or edit the `api_base` field:
   ```toml
   [models."gpt-4o"]
   model = "gpt-4o"
   api_base = "https://my-custom-base.com"
   ```
4. Save the file.

Now, whenever you select that model, the system will automatically use your custom server.

## **Steps to add new models**

### Manual Method
1. Open `configs/models.toml` and add a new `[models."hf-model-new"]` table, e.g.:
   ```toml
   [models."hf-model-new"]
   model = "huggingface/org/Model-Name-Here"
   provider = "huggingface"
   temperature = 0.1
   max_tokens = 2048
   notes = "Custom HuggingFace model"
   ```
2. (Optional) Add it to `[[free_catalog]]` if it's free/cheap and should show up in `/free`.
3. Use it like this: `python interpreter.py -m 'hf-model-new' -md 'code'`.
4. Make sure `-m 'hf-model-new'` matches the table key you added (`[models."hf-model-new"]`).

### Automatic Method
1. Go to the `scripts` directory and run the `config_builder` script.
2. For Linux/MacOS run `config_builder.sh`, for Windows run `config_builder.bat`.
3. Follow the instructions and enter the model name and parameters.
4. The script will automatically append a new `[models."<name>"]` table to `configs/models.toml`.

## Star History

<a href="https://star-history.com/#haseeb-heaven/open-code-interpreter&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=haseeb-heaven/open-code-interpreter&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=haseeb-heaven/open-code-interpreter&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=haseeb-heaven/open-code-interpreter&type=Date" />
  </picture>
</a>

## **Contributing**

If you're interested in contributing to **Code-Interpreter**, we'd love to have you! Please fork the repository and submit a pull request. We welcome all contributions and are always eager to hear your feedback and suggestions for improvements.

## **Versioning**

Current version: **3.4.0**

Quick highlights:
- **v3.4.0** - MCP + native tools/`--yolo`, streaming + multimodal images, web search, codegen modes, `--output-format`, persistent `--session`, identity/onboarding, Ollama/`--local` + `--attach`, data analysis + science engines, Docker/subprocess sandbox levels, matrix CI/coverage, interactive live tests (#212, #215–#226).
- **v3.3.0** - Gemini-CLI-style `--gemini-style` free LLM catalog, multi-key resilience (rate limiter + circuit breaker), metrics CLI, `--yes` non-interactive e2e, refreshed screenshots.
- **v3.2.3** - Fixed Windows command injection, path traversal hardening, HTTP timeouts, SafetyManager regex precompile, Ollama fixes, expanded tests.
- **v3.2.2** - Added sandbox security, improved Code Interpreter architecture, fixed execution language routing, restored sandbox toggle compatibility, added subprocess security delegation, and improved safe-mode timeout handling.
- **v3.2.1** - Added mode indicator ([SAFE MODE] or [UNSAFE MODE ⚠️]) in session banner, implemented strict safety blocking for dangerous operations in SAFE MODE, added single confirmation prompt for operations in UNSAFE MODE.
- **v3.1.0** - Added OpenRouter free-model aliases, made `openrouter/free` the default OpenRouter selection, improved simple-task code generation, added fresh TUI screenshots, and prepared release packaging assets.
- **v3.0.0** - Added a default execution safety sandbox, dangerous command/code circuit breaker, bounded ReACT-style repair retries after failures, clearer execution feedback, and polished CLI/TUI runtime output.
- **v2.4.1** - Added NVIDIA, Z AI, Browser Use, `.env.example`, and `--cli` / `--tui` startup flows.
- **v2.4.0** - 2026 model refresh across OpenAI, Gemini, Anthropic, Groq, and DeepSeek.

Full release history: [CHANGELOG.md](CHANGELOG.md)

---

## **License**

This project is licensed under the **MIT License**. For more details, please refer to the LICENSE file.

Please note the following additional licensing details:
This project is a client interface only. All models are provided by their respective third-party providers and subject to their own terms of service.

## **Acknowledgments**

- We would like to express our gratitude to **HuggingFace**,**Google**,**META**,**OpenAI**,**GroqAI**,**AnthropicAI** for providing the models.
- A special shout-out to the open-source community. Your continuous support and contributions are invaluable to us.

## * Author**
This project is created and maintained by [Haseeb-Heaven](www.github.com/haseeb-heaven).
