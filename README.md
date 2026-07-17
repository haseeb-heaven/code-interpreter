### **Support Project:**

<a href="https://www.buymeacoffee.com/haseebheaven">
    <img src="https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=&slug=haseebheaven&button_colour=40DCA5&font_colour=ffffff&font_family=Cookie&outline_colour=000000&coffee_colour=FFDD00" width="200" height="50" />
</a>
<a href="https://ko-fi.com/heavenhm">
    <img src="https://img.shields.io/badge/KoFi-ffdd00?style=for-the-badge&logo=Ko-fi&logoColor=orange" width="200" height="50" />
</a>

# OpenAgent — Open-Source Agent for Your Terminal

> An open-source agent that performs your tasks with the harness of a modern
> terminal agent — powered by open-source free models, local models, and
> bring-your-own-key frontier models. Describe a task in plain English. Get the
> result.

### Main UI / UX

![OpenAgent Main UI](assets/openagent_main_ui.png)

The interactive terminal UI shows the **OA** header, auth status (for example
`Authenticated with Gemini API key`), approval mode, model, workspace, branch,
memory usage, and the prompt — ready for natural-language tasks.

```bash
npm install
npm run build
npm start -- --free "analyze sales.csv and plot top 10 customers"
```

✅ Works with OpenRouter `:free` models — no paid API required ✅ Runs on your
machine — local models via Ollama and LM Studio, your files never leave your
computer ✅ Windows, Mac, Linux ✅ No account, no sign-in, no vendor lock-in

## Quick start with `--free` (zero-cost models)

The `--free` flag is the fastest way to use OpenAgent without paid APIs:

```bash
# Prefer a free/cheap model from the built-in catalog
npm start -- --free "analyze this CSV"

# See every model grouped by provider (availability clearly marked)
npm start -- --models

# In-session: /models lists and switches models (/model remains an alias)
```

When a free model hits a rate limit or a routing failure, OpenAgent
automatically falls through the curated free catalog — and **local models are
always the final fallback**, so a running Ollama means your task never dies.

## Truly local (no API key at all)

Ollama at `localhost:11434` is the **default provider**. Installed models are
auto-detected; when no provider is specified, OpenAgent tries Ollama first:

```bash
# Start Ollama, then OpenAgent auto-picks your best installed model
npm start

# Or pick a specific installed model
npm start -- -m ollama/llama3.1:8b

# LM Studio works the same way through its OpenAI-compatible server
npm start -- --provider lmstudio
```

## How We Compare

| Feature                    |         **OpenAgent**          | Terminal REPL agents  |
| -------------------------- | :----------------------------: | :-------------------: |
| **License**                |         ✅ Apache-2.0          |        varies         |
| **Multi-model support**    |    ✅ 13 providers built-in    | ❌ usually one vendor |
| **Local / Offline models** |     ✅ Ollama + LM Studio      |       ⚠️ rarely       |
| **Free tier (`--free`)**   | ✅ Built-in catalog + fallback |    ⚠️ rate-limited    |
| **Zero-cost usage**        |      ✅ `--free` + Ollama      |          ❌           |
| **BYOK frontier models**   |  ✅ one env key per provider   |       ⚠️ varies       |
| **Model picker**           |   ✅ `--models` / `/models`    |          ❌           |
| **Account / sign-in**      |         ✅ none needed         |   ❌ often required   |
| **MCP support**            |               ✅               |       ⚠️ varies       |

## Documentation

Full guides live in **[`docs/`](docs/README.md)** (beautifully structured for
GitHub browsing):

| Guide         | Link                                                                 |
| ------------- | -------------------------------------------------------------------- |
| **Docs home** | [docs/index.md](docs/index.md)                                       |
| Quickstart    | [docs/get-started/index.md](docs/get-started/index.md)               |
| Free models   | [docs/get-started/free-models.md](docs/get-started/free-models.md)   |
| Local models  | [docs/get-started/local-models.md](docs/get-started/local-models.md) |
| Providers     | [docs/get-started/providers.md](docs/get-started/providers.md)       |
| Common errors | [docs/resources/common-errors.md](docs/resources/common-errors.md)   |
| Model matrix  | [Models.MD](Models.MD)                                               |

## Table of Contents

- [Documentation](#documentation)
- [Installation](#installation)
- [API key setup for all providers](#api-key-setup-for-all-providers)
- [Web search (for agents & open-source models)](#web-search-for-agents--open-source-models)
- [Model registry](#model-registry-configsmodelstoml)
- [Usage](#usage)
- [Features](#features)
- [Building and testing](#building-and-testing)
  - [Prerequisites (`.env`)](#prerequisites-env)
  - [Unit tests — web search](#unit-tests--web-search)
  - [Unit tests — models & providers](#unit-tests--models--providers)
  - [Live tests — web search](#live-tests--web-search)
  - [Live tests — cloud models](#live-tests--cloud-models)
  - [Live tests — local models](#live-tests--local-models)
  - [All-in-one commands](#all-in-one-commands)
- [Attribution](#attribution)
- [License](#license)

## **Installation**

Requires Node.js 20+.

```bash
git clone --branch claude/gemini-cli-multi-provider-ru0q2f https://github.com/haseeb-heaven/open-agent.git
cd open-agent
npm install
npm run build
npm start            # launches OpenAgent (also available as the `openagent` bin)
```

## API key setup for all providers

Local providers (Ollama, LM Studio) need **no key**. Each cloud provider takes
exactly one environment variable — set it in `.env` (see
[`.env.example`](.env.example)) or let the interactive walkthrough do it:

```bash
npm start -- --byok     # asks for each provider key, writes .env,
                        # and shows which models just became available
```

| Provider    | Environment variable | Notes                               |
| ----------- | -------------------- | ----------------------------------- |
| Ollama      | — (none)             | local, default provider             |
| LM Studio   | — (none)             | local, OpenAI-compatible server     |
| OpenAI      | `OPENAI_API_KEY`     | frontier models (BYOK)              |
| Anthropic   | `ANTHROPIC_API_KEY`  | frontier models (BYOK)              |
| Gemini      | `GEMINI_API_KEY`     | free tier available                 |
| Groq        | `GROQ_API_KEY`       | generous free tier, ultra fast      |
| DeepSeek    | `DEEPSEEK_API_KEY`   | low-cost frontier models            |
| NVIDIA      | `NVIDIA_API_KEY`     | OpenAI-compatible endpoint          |
| Together AI | `TOGETHER_API_KEY`   | open-source model host              |
| HuggingFace | `HF_TOKEN`           | rate-limited free inference         |
| OpenRouter  | `OPENROUTER_API_KEY` | many `:free` models                 |
| Cerebras    | `CEREBRAS_API_KEY`   | free public endpoints, rate-limited |
| Z.ai        | `Z_AI_API_KEY`       | GLM models                          |

In-session, `/byok <provider> <key>` saves a key and immediately reports the
newly unlocked models.

## Web search (for agents & open-source models)

The `google_web_search` tool routes across **multiple backends**. You do **not**
need every key — OpenAgent picks the best available one for your **active
model**.

### Recommended backend by model family

| Active model family                                    | Recommended web search                                | Why                                      |
| ------------------------------------------------------ | ----------------------------------------------------- | ---------------------------------------- |
| **Gemini**                                             | Google Search (Gemini grounding) via `GEMINI_API_KEY` | Native grounding                         |
| **Open-source / free** (OpenRouter, Groq, Cerebras, …) | **Brave** (`BRAVE_API_KEY`)                           | Independent index, cheap, agent-friendly |
| **Local** (Ollama / LM Studio)                         | **DuckDuckGo** (no key)                               | Zero setup offline-friendly fallback     |
| Any + `TAVILY_API_KEY`                                 | Tavily also available                                 | AI-shaped snippets                       |
| Any + `SERPER_API_KEY`                                 | Serper                                                | Google-style SERP                        |
| Any + `EXA_API_KEY`                                    | Exa                                                   | Semantic / research search               |

Auto order when keys exist: **preferred env → recommended for model → Brave →
Tavily → Serper → Exa → Gemini → DuckDuckGo**.

Force a backend: `WEB_SEARCH_PROVIDER=brave` (or `tavily`, `serper`, `exa`,
`gemini`, `duckduckgo`).

### Get API keys (open these pages)

| Backend                   | Env var          | Create key                            |
| ------------------------- | ---------------- | ------------------------------------- |
| Brave Search              | `BRAVE_API_KEY`  | https://api.search.brave.com/app/keys |
| Tavily                    | `TAVILY_API_KEY` | https://app.tavily.com/home           |
| Serper                    | `SERPER_API_KEY` | https://serper.dev/api-key            |
| Exa                       | `EXA_API_KEY`    | https://dashboard.exa.ai/api-keys     |
| Google / Gemini grounding | `GEMINI_API_KEY` | https://aistudio.google.com/apikey    |
| DuckDuckGo                | —                | No key                                |

### Interactive wizard

```text
/websearch                 # open settings wizard (★ = recommended for current model)
/websearch list            # text table of providers + key status
/websearch brave           # details for one provider
/websearch open brave      # open signup page in browser when key is empty
/websearch brave <key>     # save BRAVE_API_KEY to .env
```

In the wizard: select a provider → paste the key → **Enter**. If the key box is
**empty** and you press **Enter**, OpenAgent opens that provider’s signup
website so you can create a key.

Or add keys to `.env` (see [`.env.example`](.env.example)):

```dotenv
BRAVE_API_KEY=
TAVILY_API_KEY=
SERPER_API_KEY=
EXA_API_KEY=
GEMINI_API_KEY=
WEB_SEARCH_PROVIDER=
```

**Open-source models need a search key for best results.** Without any search
key, OpenAgent still works via **DuckDuckGo** (no signup), but quality varies.

How to run unit and live web-search tests: see
[Building and testing → Web search](#unit-tests--web-search).

## Model registry (`configs/models.toml`)

Every model OpenAgent knows about lives in one human-editable file:
[`configs/models.toml`](configs/models.toml). It defines the `[models.*]`
entries, the curated `[[free_catalog]]` rotation used by `--free`, and the
`[[default_priority]]` order used when no model is specified. Add your own
models or providers by editing this single file — no code changes required.

See [Models.MD](Models.MD) for the complete supported-model list including the
**vision + streaming support matrix** for every provider.

How to run unit and live model/provider tests: see
[Building and testing → Models](#unit-tests--models--providers).

## 🛠️ **Usage**

```bash
# Default: local-first — uses your running Ollama automatically
npm start

# Pin a provider
npm start -- --provider ollama
npm start -- --provider groq -m llama-3.1-8b-instant

# Pick any model by registry key or provider/model id
npm start -- -m groq-llama-3.1-8b
npm start -- -m openrouter-free
npm start -- -m ollama/llama3.1:8b

# Prefer free models with automatic fallback (local models close the chain)
npm start -- --free "summarize this repository"

# Terminal picker and interactive BYOK setup
npm start -- --models
npm start -- --byok

# Non-interactive (headless) mode
npm start -- --free -p "list the 5 largest files in this project"
```

| Flag                  | What it does                                                                                                                                                                 |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--provider <id>`     | Route through one provider: `ollama`, `lmstudio`, `openai`, `anthropic`, `gemini`, `groq`, `deepseek`, `nvidia`, `together`, `huggingface`, `openrouter`, `cerebras`, `z-ai` |
| `--model, -m <name>`  | Registry key, free-catalog id, or `provider/model` id                                                                                                                        |
| `--free`              | Prefer the free/cheap catalog rotation from `configs/models.toml`                                                                                                            |
| `--models`            | Print all configured models grouped by provider and exit                                                                                                                     |
| `--resume [id]`, `-r` | Resume the latest session, a numbered session, or a session ID                                                                                                               |
| `--yolo`, `-y`        | Auto-approve all tool actions; use only in trusted workspaces                                                                                                                |
| `--approval-mode`     | Set `default`, `auto_edit`, `yolo`, or `plan` approval behavior                                                                                                              |
| `--byok`              | Interactive API-key setup writing to `.env`, then exit                                                                                                                       |

Inside a session:

- `/models` — open the grouped model picker. It marks vision, streaming, and key
  availability; selecting a provider with no key offers to save that provider's
  key to `.env`. `/model` remains a compatibility alias.
- `/byok` — list providers and key status; `/byok <provider> <key>` to save.
- `/models set <name>` — switch models directly.

## **Features**

- **Task-based agent**: describe the task; the agent plans, uses tools (file
  operations, shell commands, web fetching), and delivers the result.
- **13 providers, one interface**: local (Ollama, LM Studio) and cloud (OpenAI,
  Anthropic, Gemini, Groq, DeepSeek, NVIDIA, Together AI, HuggingFace,
  OpenRouter, Cerebras, Z.ai) behind LiteLLM-style `provider/model` routing.
- **Free-model catalog with resilient fallback**: rate limits and flaky free
  routers are classified and rotated through automatically; local models are the
  final fallback.
- **MCP (Model Context Protocol)**: extend the agent with custom tool servers.
- **Vision + streaming**: multimodal input and token streaming wherever the
  backing model supports it (see the matrix in [Models.MD](Models.MD)).
- **Privacy-first**: with local models, prompts and files never leave your
  machine. No telemetry account, no sign-in.
- **Single-file model registry**: `configs/models.toml` — bring any
  OpenAI-compatible provider without touching code.

## Building and testing

All vitest commands below run from the **repo root** with
`--root packages/core`. Vitest loads keys from the **repo-root `.env`**
automatically (via `packages/core/test-setup.ts`); shell env vars still win if
already set.

```bash
npm install       # install all workspace dependencies
npm run build     # build every package
npm test          # full unit test suite (all workspaces)
```

### Prerequisites (`.env`)

Copy [`.env.example`](.env.example) → `.env` and fill the keys you have. You do
**not** need every key.

| Area | Env vars used by tests |
| ---- | ---------------------- |
| **Web search (live)** | `BRAVE_API_KEY`, `TAVILY_API_KEY`, `SERPER_API_KEY`, `EXA_API_KEY`, `GEMINI_API_KEY` (DuckDuckGo needs none) |
| **Cloud models (live)** | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `DEEPSEEK_API_KEY`, `NVIDIA_API_KEY`, `TOGETHER_API_KEY`, `HF_TOKEN` / `HUGGINGFACE_API_KEY`, `OPENROUTER_API_KEY`, `CEREBRAS_API_KEY`, `Z_AI_API_KEY` |
| **Local models (live)** | none (Ollama / LM Studio must be running) |

Missing keys → that backend/provider is **skipped**, not failed. Quota /
empty-balance errors on live model probes are **soft-skipped** (not product
failures).

---

### Unit tests — web search

Mocked backends + router (no paid keys required). DuckDuckGo may hit the public
network in one backend unit test.

```bash
# Entire websearch package (unit + live file; live cases skip without keys)
npx vitest run src/websearch --root packages/core

# Individual backend unit files
npx vitest run src/websearch/backends/brave.test.ts --root packages/core
npx vitest run src/websearch/backends/tavily.test.ts --root packages/core
npx vitest run src/websearch/backends/serper.test.ts --root packages/core
npx vitest run src/websearch/backends/exa.test.ts --root packages/core
npx vitest run src/websearch/backends/duckduckgo.test.ts --root packages/core
npx vitest run src/websearch/router.test.ts --root packages/core
```

---

### Unit tests — models & providers

Registry-wide coverage of `configs/models.toml` (every model entry), free
catalog, BYOK helpers, routing, and provider metadata. **No live API calls.**

```bash
# All provider unit tests under packages/core
npx vitest run src/providers --root packages/core

# Focused suites
npx vitest run src/providers/allModels.test.ts --root packages/core
npx vitest run src/providers/modelRegistry.test.ts --root packages/core
npx vitest run src/providers/freeCatalog.test.ts --root packages/core
npx vitest run src/providers/providers.test.ts --root packages/core
npx vitest run src/providers/byok.test.ts --root packages/core
npx vitest run src/providers/resolve.test.ts --root packages/core
npx vitest run src/providers/picker.test.ts --root packages/core
```

---

### Live tests — web search

Hits real search APIs with keys from `.env`. Safe to run anytime: missing keys
skip that backend.

```bash
# All live web-search probes (Brave / Tavily / Serper / Exa / DDG / route plan)
npx vitest run src/websearch/live.websearch.test.ts --root packages/core
```

**PowerShell:** same command (`.env` is loaded by the test setup).

Optional: force a backend for manual app use (not required for tests):

```bash
# bash / zsh
export WEB_SEARCH_PROVIDER=brave

# PowerShell
$env:WEB_SEARCH_PROVIDER = 'brave'
```

---

### Live tests — cloud models

One cheap model per cloud provider (complete + stream). Requires
`RUN_LIVE_PROVIDER_TESTS=1`. Skipped in CI. Skipped when the provider key is
missing. Quota/billing soft-skips pass with a warning.

```bash
# bash / zsh — all providers that have keys in .env
RUN_LIVE_PROVIDER_TESTS=1 npx vitest run src/providers/cloud.integration.test.ts --root packages/core

# Single provider (example: OpenRouter free)
RUN_LIVE_PROVIDER_TESTS=1 npx vitest run src/providers/cloud.integration.test.ts --root packages/core -t openrouter
```

**PowerShell:**

```powershell
$env:RUN_LIVE_PROVIDER_TESTS = '1'
# Unset CI if your shell injects it (CI skips the whole live suite)
Remove-Item Env:CI -ErrorAction SilentlyContinue
npx vitest run src/providers/cloud.integration.test.ts --root packages/core --reporter=verbose
```

Providers in the live matrix: `openai`, `anthropic`, `gemini`, `groq`,
`deepseek`, `nvidia`, `together`, `huggingface`, `openrouter`, `cerebras`,
`z-ai`.

---

### Live tests — local models

Needs a running Ollama and/or LM Studio server (no cloud keys).

```bash
# bash / zsh
RUN_LOCAL_PROVIDER_TESTS=1 npx vitest run src/providers/local.integration.test.ts --root packages/core
```

**PowerShell:**

```powershell
$env:RUN_LOCAL_PROVIDER_TESTS = '1'
npx vitest run src/providers/local.integration.test.ts --root packages/core
```

---

### All-in-one commands

```bash
# Unit: web search + model registry (good default before a PR)
npx vitest run src/websearch src/providers/allModels.test.ts src/providers/providers.test.ts src/providers/freeCatalog.test.ts src/providers/modelRegistry.test.ts --root packages/core

# Live: web search + every cloud provider that has a key (bash)
RUN_LIVE_PROVIDER_TESTS=1 npx vitest run src/websearch/live.websearch.test.ts src/providers/cloud.integration.test.ts --root packages/core
```

**PowerShell live combo:**

```powershell
$env:RUN_LIVE_PROVIDER_TESTS = '1'
Remove-Item Env:CI -ErrorAction SilentlyContinue
npx vitest run src/websearch/live.websearch.test.ts src/providers/cloud.integration.test.ts --root packages/core --reporter=verbose
```

## 📝 **Changelog**

See [CHANGELOG.md](CHANGELOG.md). OpenAgent v4.0.0 continues the release line of
the original Python project (last release v3.6.0).

## 🙏 **Attribution**

This project is based on [Gemini CLI](https://github.com/google-gemini/gemini-cli)
by Google LLC, licensed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).

Modifications have been made by Haseeb Mir as part of the `open-agent` fork.

## 🙏 **Acknowledgments**

- Everyone who contributed to the original open-code-interpreter project.
- The open-source model community — free and local models make OpenAgent
  possible.

## 📜 **License**

Apache-2.0 — see [LICENSE](LICENSE). OpenAgent contains code forked from an
Apache-2.0 licensed terminal agent project.
