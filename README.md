# Code Interpreter CLI (multi-provider fork)

An open-source AI agent for your terminal, forked from
[gemini-cli](https://github.com/google-gemini/gemini-cli) (Apache 2.0) and
rebuilt around **local-first, multi-provider routing**: no account and no API
key required — if Ollama is running on your machine, it just works. Cloud
providers (OpenAI, Anthropic, Gemini, Groq, DeepSeek, NVIDIA, Together AI,
HuggingFace, OpenRouter, Cerebras, Z.ai) plug in with a single API key each.

The model catalog lives in a single human-editable file,
[`configs/models.toml`](configs/models.toml) — see [Models.MD](Models.MD) for
the full list with the vision/streaming support matrix.

## 🚀 Why this fork?

- **🏠 Local-first**: Ollama at `localhost:11434` is the default provider —
  installed models are auto-detected, zero configuration, zero keys.
- **🎛️ LM Studio support**: point-and-shoot against `localhost:1234` via its
  OpenAI-compatible API.
- **☁️ Every major cloud provider**: LiteLLM-style `provider/model` routing
  through each provider's OpenAI-compatible endpoint.
- **🆓 Free-model rotation**: `--free` walks a curated catalog of free/cheap
  presets (OpenRouter `:free`, Groq/Gemini free tiers, Cerebras, HF) with
  automatic fallback on rate limits — local models are the final fallback.
- **🎯 Model picker**: `--pick` / `/pick` shows every model grouped by provider
  with vision, streaming, and key availability marked.
- **🔑 BYOK**: `--byok` / `/byok` walks you through adding API keys to `.env`
  and immediately shows which models just became available.
- **🔧 Built-in tools**: file operations, shell commands, web fetching.
- **🔌 Extensible**: MCP (Model Context Protocol) support for custom
  integrations.
- **💻 Terminal-first**: Designed for developers who live in the command line.
- **🛡️ Open source**: Apache 2.0 licensed.

## ⚡ Multi-provider quickstart

```bash
# Local, keyless: uses your running Ollama automatically (default provider)
npm start

# Pin a provider explicitly
npm start -- --provider ollama            # best installed Ollama model
npm start -- --provider lmstudio          # first model loaded in LM Studio
npm start -- --provider groq -m llama-3.1-8b-instant

# Pick any model by registry key or LiteLLM-style id
npm start -- -m groq-llama-3.1-8b         # key from configs/models.toml
npm start -- -m ollama/llama3.1:8b        # explicit provider/model id
npm start -- -m openrouter-free           # OpenRouter free router

# Prefer free models (rotates through the free catalog, local final fallback)
npm start -- --free "explain this repo"

# Interactive model picker: all models grouped by provider,
# with vision / streaming / API-key availability marked
npm start -- --pick

# Bring your own key: interactive walkthrough that writes .env
npm start -- --byok
```

Inside a session, `/pick` lists or switches models and `/byok <provider> <key>`
saves a key and reports the newly unlocked models.

| Flag                 | What it does                                                                                                                                                                 |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--provider <id>`    | Route through one provider: `ollama`, `lmstudio`, `openai`, `anthropic`, `gemini`, `groq`, `deepseek`, `nvidia`, `together`, `huggingface`, `openrouter`, `cerebras`, `z-ai` |
| `--model, -m <name>` | Registry key, free-catalog id, or `provider/model` id                                                                                                                        |
| `--free`             | Prefer the free/cheap catalog rotation from `configs/models.toml`                                                                                                            |
| `--pick`             | Print the grouped model picker and exit                                                                                                                                      |
| `--byok`             | Interactive API-key setup writing to `.env`, then exit                                                                                                                       |

API keys (only needed for cloud providers): `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `DEEPSEEK_API_KEY`,
`NVIDIA_API_KEY`, `TOGETHER_API_KEY`, `HF_TOKEN`, `OPENROUTER_API_KEY`,
`CEREBRAS_API_KEY`, `Z_AI_API_KEY`.

## 🧪 Building and testing

```bash
npm install       # install all workspace dependencies
npm run build     # build every package
npm test          # full unit test suite (all workspaces)
```

Provider-specific test suites (in `packages/core`):

```bash
npx vitest run src/providers                        # all provider unit tests
RUN_LOCAL_PROVIDER_TESTS=1 npx vitest run src/providers/local.integration.test.ts   # live Ollama / LM Studio
RUN_LIVE_PROVIDER_TESTS=1 npx vitest run src/providers/cloud.integration.test.ts    # live cloud endpoints (needs keys)
```

Live integration tests are skipped in CI and for any provider whose API key is
not set, so they are always safe to run.

## 📦 Installation

See
[Gemini CLI installation, execution, and releases](https://www.geminicli.com/docs/get-started/installation)
for recommended system specifications and a detailed installation guide.

### Quick Install

#### Run instantly with npx

```bash
# Using npx (no installation required)
npx @google/gemini-cli
```

#### Install globally with npm

```bash
npm install -g @google/gemini-cli
```

#### Install globally with Homebrew (macOS/Linux)

```bash
brew install gemini-cli
```

#### Install globally with MacPorts (macOS)

```bash
sudo port install gemini-cli
```

#### Install with Anaconda (for restricted environments)

```bash
# Create and activate a new environment
conda create -y -n gemini_env -c conda-forge nodejs
conda activate gemini_env

# Install Gemini CLI globally via npm (inside the environment)
npm install -g @google/gemini-cli
```

## Release Channels

See [Releases](https://www.geminicli.com/docs/changelogs) for more details.

### Preview

New preview releases will be published each week at UTC 23:59 on Tuesdays. These
releases will not have been fully vetted and may contain regressions or other
outstanding issues. Please help us test and install with `preview` tag.

```bash
npm install -g @google/gemini-cli@preview
```

### Stable

- New stable releases will be published each week at UTC 20:00 on Tuesdays, this
  will be the full promotion of last week's `preview` release + any bug fixes
  and validations. Use `latest` tag.

```bash
npm install -g @google/gemini-cli@latest
```

### Nightly

- New releases will be published each day at UTC 00:00. This will be all changes
  from the main branch as represented at time of release. It should be assumed
  there are pending validations and issues. Use `nightly` tag.

```bash
npm install -g @google/gemini-cli@nightly
```

## 📋 Key Features

### Code Understanding & Generation

- Query and edit large codebases
- Generate new apps from PDFs, images, or sketches using multimodal capabilities
- Debug issues and troubleshoot with natural language

### Automation & Integration

- Automate operational tasks like querying pull requests or handling complex
  rebases
- Use MCP servers to connect new capabilities, including
  [media generation with Imagen, Veo or Lyria](https://github.com/GoogleCloudPlatform/vertex-ai-creative-studio/tree/main/experiments/mcp-genmedia)
- Run non-interactively in scripts for workflow automation

### Advanced Capabilities

- Ground your queries with built-in
  [Google Search](https://ai.google.dev/gemini-api/docs/grounding) for real-time
  information
- Conversation checkpointing to save and resume complex sessions
- Custom context files (GEMINI.md) to tailor behavior for your projects

### GitHub Integration

Integrate Gemini CLI directly into your GitHub workflows with
[**Gemini CLI GitHub Action**](https://github.com/google-github-actions/run-gemini-cli):

- **Pull Request Reviews**: Automated code review with contextual feedback and
  suggestions
- **Issue Triage**: Automated labeling and prioritization of GitHub issues based
  on content analysis
- **On-demand Assistance**: Mention `@gemini-cli` in issues and pull requests
  for help with debugging, explanations, or task delegation
- **Custom Workflows**: Build automated, scheduled and on-demand workflows
  tailored to your team's needs

## 🔐 Authentication Options

No account or sign-in flow is required. Pick whichever fits:

### Option 1: Local models — no key at all (default)

**✨ Best for:** Everyone. Fully free, fully private, works offline.

Start Ollama (`ollama serve`) or LM Studio's local server, and the CLI
auto-detects it — installed models are picked up automatically:

```bash
gemini                       # uses your best installed Ollama model
gemini --provider lmstudio   # or LM Studio at localhost:1234
```

### Option 2: Bring your own key (any cloud provider)

**✨ Best for:** Access to frontier cloud models with one key per provider.

```bash
gemini --byok                # interactive walkthrough, writes .env
# or set keys directly:
export OPENAI_API_KEY="..."      # or ANTHROPIC_API_KEY, GROQ_API_KEY,
export OPENROUTER_API_KEY="..."  # DEEPSEEK_API_KEY, NVIDIA_API_KEY,
                                 # TOGETHER_API_KEY, HF_TOKEN,
                                 # CEREBRAS_API_KEY, Z_AI_API_KEY, ...
gemini --pick                # see what became available
```

### Option 3: Gemini API key (optional)

**✨ Best for:** Using Google's models like any other provider in the catalog.

```bash
export GEMINI_API_KEY="YOUR_API_KEY"
gemini -m gemini-2.5-flash
```

## 🚀 Getting Started

### Basic Usage

#### Start in current directory

```bash
gemini
```

#### Include multiple directories

```bash
gemini --include-directories ../lib,../docs
```

#### Use specific model

```bash
gemini -m gemini-2.5-flash
```

#### Non-interactive mode for scripts

Get a simple text response:

```bash
gemini -p "Explain the architecture of this codebase"
```

For more advanced scripting, including how to parse JSON and handle errors, use
the `--output-format json` flag to get structured output:

```bash
gemini -p "Explain the architecture of this codebase" --output-format json
```

For real-time event streaming (useful for monitoring long-running operations),
use `--output-format stream-json` to get newline-delimited JSON events:

```bash
gemini -p "Run tests and deploy" --output-format stream-json
```

### Quick Examples

#### Start a new project

```bash
cd new-project/
gemini
> Write me a Discord bot that answers questions using a FAQ.md file I will provide
```

#### Analyze existing code

```bash
git clone https://github.com/google-gemini/gemini-cli
cd gemini-cli
gemini
> Give me a summary of all of the changes that went in yesterday
```

## 📚 Documentation

### Getting Started

- [**Quickstart Guide**](https://www.geminicli.com/docs/get-started) - Get up
  and running quickly.
- [**Authentication Setup**](https://www.geminicli.com/docs/get-started/authentication) -
  Detailed auth configuration.
- [**Configuration Guide**](https://www.geminicli.com/docs/reference/configuration) -
  Settings and customization.
- [**Keyboard Shortcuts**](https://www.geminicli.com/docs/reference/keyboard-shortcuts) -
  Productivity tips.

### Core Features

- [**Commands Reference**](https://www.geminicli.com/docs/reference/commands) -
  All slash commands (`/help`, `/chat`, etc).
- [**Custom Commands**](https://www.geminicli.com/docs/cli/custom-commands) -
  Create your own reusable commands.
- [**Context Files (GEMINI.md)**](https://www.geminicli.com/docs/cli/gemini-md) -
  Provide persistent context to Gemini CLI.
- [**Checkpointing**](https://www.geminicli.com/docs/cli/checkpointing) - Save
  and resume conversations.
- [**Token Caching**](https://www.geminicli.com/docs/cli/token-caching) -
  Optimize token usage.

### Tools & Extensions

- [**Built-in Tools Overview**](https://www.geminicli.com/docs/reference/tools)
  - [File System Operations](https://www.geminicli.com/docs/tools/file-system)
  - [Shell Commands](https://www.geminicli.com/docs/tools/shell)
  - [Web Fetch & Search](https://www.geminicli.com/docs/tools/web-fetch)
- [**MCP Server Integration**](https://www.geminicli.com/docs/tools/mcp-server) -
  Extend with custom tools.
- [**Custom Extensions**](https://geminicli.com/docs/extensions/writing-extensions) -
  Build and share your own commands.

### Advanced Topics

- [**Headless Mode (Scripting)**](https://www.geminicli.com/docs/cli/headless) -
  Use Gemini CLI in automated workflows.
- [**IDE Integration**](https://www.geminicli.com/docs/ide-integration) - VS
  Code companion.
- [**Sandboxing & Security**](https://www.geminicli.com/docs/cli/sandbox) - Safe
  execution environments.
- [**Trusted Folders**](https://www.geminicli.com/docs/cli/trusted-folders) -
  Control execution policies by folder.
- [**Enterprise Guide**](https://www.geminicli.com/docs/cli/enterprise) - Deploy
  and manage in a corporate environment.
- [**Telemetry & Monitoring**](https://www.geminicli.com/docs/cli/telemetry) -
  Usage tracking.
- [**Tools reference**](https://www.geminicli.com/docs/reference/tools) -
  Built-in tools overview.
- [**Local development**](https://www.geminicli.com/docs/local-development) -
  Local development tooling.

### Troubleshooting & Support

- [**Troubleshooting Guide**](https://www.geminicli.com/docs/resources/troubleshooting) -
  Common issues and solutions.
- [**FAQ**](https://www.geminicli.com/docs/resources/faq) - Frequently asked
  questions.
- Use `/bug` command to report issues directly from the CLI.

### Using MCP Servers

Configure MCP servers in `~/.gemini/settings.json` to extend Gemini CLI with
custom tools:

```text
> @github List my open pull requests
> @slack Send a summary of today's commits to #dev channel
> @database Run a query to find inactive users
```

See the
[MCP Server Integration guide](https://www.geminicli.com/docs/tools/mcp-server)
for setup instructions.

## 🤝 Contributing

We welcome contributions! Gemini CLI is fully open source (Apache 2.0), and we
encourage the community to:

- Report bugs and suggest features.
- Improve documentation.
- Submit code improvements.
- Share your MCP servers and extensions.

See our [Contributing Guide](./CONTRIBUTING.md) for development setup, coding
standards, and how to submit pull requests.

Check our [Official Roadmap](https://github.com/orgs/google-gemini/projects/11)
for planned features and priorities.

## 📖 Resources

- **[Free Course](https://learn.deeplearning.ai/courses/gemini-cli-code-and-create-with-an-open-source-agent/information)** -
  Learn the basics.
- **[Official Roadmap](./ROADMAP.md)** - See what's coming next.
- **[Changelog](https://www.geminicli.com/docs/changelogs)** - See recent
  notable updates.
- **[NPM Package](https://www.npmjs.com/package/@google/gemini-cli)** - Package
  registry.
- **[GitHub Issues](https://github.com/google-gemini/gemini-cli/issues)** -
  Report bugs or request features.
- **[Security Advisories](https://github.com/google-gemini/gemini-cli/security/advisories)** -
  Security updates.

### Uninstall

See the [Uninstall Guide](https://www.geminicli.com/docs/resources/uninstall)
for removal instructions.

## 📄 Legal

- **License**: [Apache License 2.0](LICENSE)
- **Terms of Service**:
  [Terms & Privacy](https://www.geminicli.com/docs/resources/tos-privacy)
- **Security**: [Security Policy](SECURITY.md)

<p align="left">
 <a href="https://www.star-history.com/google-gemini/gemini-cli">
  <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/badge?repo=google-gemini/gemini-cli&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/badge?repo=google-gemini/gemini-cli" />
   <img alt="Star History Rank" src="https://api.star-history.com/badge?repo=google-gemini/gemini-cli" />
  </picture>
 </a>
</p>

---

<p align="center">
  Built with ❤️ by Google and the open source community
</p>
