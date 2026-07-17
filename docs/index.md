# OpenAgent documentation

**OpenAgent** is an open-source terminal agent for real work: describe a task in
plain English, and it plans, uses tools, and delivers results — on your machine.

Use free cloud models, local models (Ollama / LM Studio), or bring-your-own-key
frontier APIs. No vendor lock-in. No required account.

![OpenAgent Main UI](./assets/openagent-main-ui.png)

<div align="center">

|                      |                                               |
| :------------------: | :-------------------------------------------: |
|   **Local-first**    |   Ollama is the default when no key is set    |
| **`--free` catalog** | Curated zero-cost models + automatic fallback |
|   **13 providers**   |          One CLI, one model registry          |
|    **Apache-2.0**    |        Fork-friendly, no sign-in wall         |

</div>

---

## Start in 60 seconds

```bash
# From a clone of this repo (Node.js 20+)
npm install
npm run build

# Local models (recommended) — start Ollama, then:
npm start

# Or zero-cost cloud rotation (needs free-tier keys where applicable)
npm start -- --free "summarize this repository"

# Interactive key setup for any provider
npm start -- --byok
```

```bash
# If installed as a global package
npm install -g open-agent
openagent
openagent --free "list the five largest files"
```

---

## Choose your path

| Goal                           | Guide                                                                                             |
| ------------------------------ | ------------------------------------------------------------------------------------------------- |
| First session end-to-end       | [Quickstart](./get-started/index.md)                                                              |
| Install on your OS             | [Installation](./get-started/installation.mdx)                                                    |
| API keys & multi-provider auth | [Authentication & providers](./get-started/authentication.mdx)                                    |
| Free / cheap models            | [Free models (`--free`)](./get-started/free-models.md)                                            |
| Fully offline with Ollama      | [Local models](./get-started/local-models.md)                                                     |
| Every provider & env var       | [Provider catalog](./get-started/providers.md)                                                    |
| Slash commands & flags         | [CLI cheatsheet](./cli/cli-reference.md)                                                          |
| Something broke                | [Common errors](./resources/common-errors.md) · [Troubleshooting](./resources/troubleshooting.md) |

---

## Use OpenAgent

Hands-on tutorials for daily workflows.

| Tutorial                                                    | What you'll learn                          |
| ----------------------------------------------------------- | ------------------------------------------ |
| [File management](./cli/tutorials/file-management.md)       | `@path`, read/write tools, workspace scope |
| [Shell commands](./cli/tutorials/shell-commands.md)         | Safe system commands & confirmation        |
| [Session management](./cli/tutorials/session-management.md) | Resume, rewind, history                    |
| [Memory & context](./cli/tutorials/memory-management.md)    | Project context files and facts            |
| [Task planning](./cli/tutorials/task-planning.md)           | Todos for multi-step work                  |
| [Plan mode](./cli/tutorials/plan-mode-steering.md)          | Read-only planning before edits            |
| [Web tools](./cli/tutorials/web-tools.md)                   | Search and fetch from the web              |
| [MCP setup](./cli/tutorials/mcp-setup.md)                   | Connect external tool servers              |
| [Agent skills](./cli/tutorials/skills-getting-started.md)   | Specialized skill packages                 |
| [Automation](./cli/tutorials/automation.md)                 | Headless / scripted runs                   |

---

## Features

| Feature                                       | Description                                            |
| --------------------------------------------- | ------------------------------------------------------ |
| [Model selection](./cli/model.md)             | Pick models via `--model`, `/models`, or registry keys |
| [Model routing](./cli/model-routing.md)       | Automatic fallback when a free endpoint rate-limits    |
| [Sandboxing](./cli/sandbox.md)                | Isolate tool execution                                 |
| [Plan mode](./cli/plan-mode.md)               | Safe, read-only planning                               |
| [Skills](./cli/skills.md)                     | Specialized expertise packs                            |
| [Extensions](./extensions/index.md)           | Bundle tools, themes, and MCP servers                  |
| [Hooks](./hooks/index.md)                     | Script lifecycle customization                         |
| [MCP servers](./tools/mcp-server.md)          | Model Context Protocol tools                           |
| [Subagents](./core/subagents.md)              | Specialized delegated agents                           |
| [IDE integration](./ide-integration/index.md) | Editor companion / ACP                                 |
| [Headless mode](./cli/headless.md)            | CI and scripting (`-p`)                                |
| [Themes](./cli/themes.md)                     | Terminal UI personalization                            |
| [Trusted folders](./cli/trusted-folders.md)   | Workspace trust & permissions                          |
| [Checkpointing](./cli/checkpointing.md)       | Session snapshots                                      |
| [Telemetry](./cli/telemetry.md)               | Optional metrics (local-first by default)              |

---

## Configuration

| Topic                                         | Link                                                                |
| --------------------------------------------- | ------------------------------------------------------------------- |
| Settings file                                 | [Settings](./cli/settings.md)                                       |
| Full settings / env reference                 | [Configuration reference](./reference/configuration.md)             |
| Model registry (`configs/models.toml`)        | [Providers](./get-started/providers.md) · [Models.MD](../Models.MD) |
| Project context (`GEMINI.md` / context files) | [Project context](./cli/gemini-md.md)                               |
| Ignore patterns                               | [Ignore files](./cli/gemini-ignore.md)                              |
| Custom slash commands                         | [Custom commands](./cli/custom-commands.md)                         |
| System prompt override                        | [System prompt](./cli/system-prompt.md)                             |
| Policy engine                                 | [Policy engine](./reference/policy-engine.md)                       |

---

## Reference

| Reference            | Link                                                    |
| -------------------- | ------------------------------------------------------- |
| Slash commands       | [Command reference](./reference/commands.md)            |
| Built-in tools       | [Tools reference](./reference/tools.md)                 |
| Keyboard shortcuts   | [Keyboard shortcuts](./reference/keyboard-shortcuts.md) |
| CLI flags cheatsheet | [CLI cheatsheet](./cli/cli-reference.md)                |

---

## Resources & development

|                                                     |                                          |
| --------------------------------------------------- | ---------------------------------------- |
| [FAQ](./resources/faq.md)                           | Common product questions                 |
| [Common errors](./resources/common-errors.md)       | TPM limits, binary files, bad tool calls |
| [Troubleshooting](./resources/troubleshooting.md)   | Auth, network, install issues            |
| [Quota & pricing](./resources/quota-and-pricing.md) | Provider limits (where applicable)       |
| [Uninstall](./resources/uninstall.md)               | Clean removal                            |
| [Local development](./local-development.md)         | Build from source                        |
| [Contributing](./CONTRIBUTING.md)                   | How to contribute                        |
| [Release notes](./changelogs/index.md)              | What's new                               |

---

## Architecture at a glance

```text
┌─────────────────────────────────────────────────────────────┐
│  openagent  (CLI / TUI)                                      │
│  prompts · sessions · approvals · /models · /byok            │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  Core agent loop                                             │
│  tools · policy · sandbox · MCP · skills · memory            │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  Provider layer  (configs/models.toml)                       │
│  Ollama · LM Studio · OpenAI · Anthropic · Gemini · Groq     │
│  DeepSeek · NVIDIA · Together · HuggingFace · OpenRouter     │
│  Cerebras · Z.ai                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Support the project

OpenAgent is free and open source. If it saves you time:

- [Buy me a coffee](https://www.buymeacoffee.com/haseebheaven)
- [Ko-fi](https://ko-fi.com/heavenhm)
- Star the repo:
  [haseeb-heaven/open-agent](https://github.com/haseeb-heaven/open-agent)

**License:** Apache-2.0
