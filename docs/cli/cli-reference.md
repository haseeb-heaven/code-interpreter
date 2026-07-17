# OpenAgent cheatsheet

Quick reference for **OpenAgent** CLI flags, interactive slash commands, and
model selection. For full setup, see the [Quickstart](../get-started/index.md).

## OpenAgent essentials

| Goal                    | Command                          |
| ----------------------- | -------------------------------- |
| Start (local-first)     | `openagent` or `npm start`       |
| Free catalog rotation   | `openagent --free "task"`        |
| List models by provider | `openagent --models`             |
| Interactive API keys    | `openagent --byok`               |
| Pin model               | `openagent -m groq-llama-3.1-8b` |
| Pin provider            | `openagent --provider ollama`    |
| Headless                | `openagent -p "task"`            |
| Resume                  | `openagent -r latest`            |

In-session: `/models`, `/byok`, `/tools`, `/help`, `/quit`.

## CLI commands

| Command                               | Description                        | Example                                                            |
| ------------------------------------- | ---------------------------------- | ------------------------------------------------------------------ |
| `openagent`                           | Start interactive REPL             | `openagent`                                                        |
| `openagent -p "query"`                | Query non-interactively            | `openagent -p "summarize README.md"`                               |
| openagent "query"                     | Query and continue interactively   | openagent "explain this project"                                   |
| `cat file \| openagent`               | Process piped content              | `cat logs.txt \| openagent`<br>`Get-Content logs.txt \| openagent` |
| `openagent -i "query"`                | Execute and continue interactively | `openagent -i "What is the purpose of this project?"`              |
| `openagent -r "latest"`               | Continue most recent session       | `openagent -r "latest"`                                            |
| `openagent -r "latest" "query"`       | Continue session with a new prompt | `openagent -r "latest" "Check for type errors"`                    |
| `openagent -r "<session-id>" "query"` | Resume session by ID               | `openagent -r "abc123" "Finish this PR"`                           |
| `openagent update`                    | Update to latest version           | `openagent update`                                                 |
| `openagent extensions`                | Manage extensions                  | See [Extensions Management](#extensions-management)                |
| `openagent mcp`                       | Configure MCP servers              | See [MCP Server Management](#mcp-server-management)                |

### Positional arguments

| Argument | Type              | Description                                                                                                |
| -------- | ----------------- | ---------------------------------------------------------------------------------------------------------- |
| `query`  | string (variadic) | Positional prompt. Defaults to interactive mode in a TTY. Use `-p/--prompt` for non-interactive execution. |

## Interactive commands

These commands are available within the interactive REPL.

| Command              | Description                                        |
| -------------------- | -------------------------------------------------- |
| `/skills reload`     | Reload discovered skills from disk                 |
| `/agents reload`     | Reload the agent registry                          |
| `/commands list`     | List available custom slash commands               |
| `/commands reload`   | Reload custom slash commands                       |
| `/memory reload`     | Reload context files (for example, `OPENAGENT.md`) |
| `/mcp reload`        | Restart and reload MCP servers                     |
| `/extensions reload` | Reload all active extensions                       |
| `/help`              | Show help for all commands                         |
| `/quit`              | Exit the interactive session                       |

## CLI Options

| Option                           | Alias | Type    | Default   | Description                                                                                                                                                            |
| -------------------------------- | ----- | ------- | --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--debug`                        | `-d`  | boolean | `false`   | Run in debug mode with verbose logging                                                                                                                                 |
| `--version`                      | `-v`  | -       | -         | Show CLI version number and exit                                                                                                                                       |
| `--help`                         | `-h`  | -       | -         | Show help information                                                                                                                                                  |
| `--model`                        | `-m`  | string  | `auto`    | Model to use. See [Model Selection](#model-selection) for available values.                                                                                            |
| `--prompt`                       | `-p`  | string  | -         | Prompt text. Appended to stdin input if provided. Forces non-interactive mode.                                                                                         |
| `--prompt-interactive`           | `-i`  | string  | -         | Execute prompt and continue in interactive mode                                                                                                                        |
| `--worktree`                     | `-w`  | string  | -         | Start open-agent in a new git worktree. If no name is provided, one is generated automatically. Requires `experimental.worktrees: true` in settings.                   |
| `--sandbox`                      | `-s`  | boolean | `false`   | Run in a sandboxed environment for safer execution                                                                                                                     |
| `--skip-trust`                   | -     | boolean | `false`   | Trust the current workspace for this session, skipping the folder trust check.                                                                                         |
| `--approval-mode`                | -     | string  | `default` | Approval mode for tool execution. Choices: `default`, `auto_edit`, `auto`, `yolo`, `plan`                                                                              |
| `--auto-mode`                    | -     | boolean | `false`   | Auto mode: auto-approve safe tools; still prompt on dangerous commands/deletes/system paths (same as `--approval-mode=auto`)                                           |
| `--yolo`                         | `-y`  | boolean | `false`   | YOLO mode: auto-approve **all** actions including dangerous (same as `--approval-mode=yolo`). Prefer `--auto-mode` for safer runs.                                     |
| `--experimental-acp`             | -     | boolean | -         | Start in ACP (Agent Code Pilot) mode. **Experimental feature.**                                                                                                        |
| `--experimental-zed-integration` | -     | boolean | -         | Run in Zed editor integration mode. **Experimental feature.**                                                                                                          |
| `--allowed-mcp-server-names`     | -     | array   | -         | Allowed MCP server names (comma-separated or multiple flags)                                                                                                           |
| `--allowed-tools`                | -     | array   | -         | **Deprecated.** Use the [Policy Engine](../reference/policy-engine.md) instead. Tools that are allowed to run without confirmation (comma-separated or multiple flags) |
| `--extensions`                   | `-e`  | array   | -         | List of extensions to use. If not provided, all extensions are enabled (comma-separated or multiple flags)                                                             |
| `--list-extensions`              | `-l`  | boolean | -         | List all available extensions and exit                                                                                                                                 |
| `--resume`                       | `-r`  | string  | -         | Resume a previous session. Bare `--resume` (or `--resume latest`) resumes the most recent chat; also accepts index (`--resume 5`) or session UUID                      |
| `--list-sessions`                | -     | boolean | -         | List available sessions for the current project and exit                                                                                                               |
| `--delete-session`               | -     | string  | -         | Delete a session by index number (use `--list-sessions` to see available sessions)                                                                                     |
| `--include-directories`          | -     | array   | -         | Additional directories to include in the workspace (comma-separated or multiple flags)                                                                                 |
| `--screen-reader`                | -     | boolean | -         | Enable screen reader mode for accessibility                                                                                                                            |
| `--output-format`                | `-o`  | string  | `text`    | The format of the CLI output. Choices: `text`, `json`, `stream-json`                                                                                                   |

## Model selection

The `--model` (or `-m`) flag accepts:

- **Registry keys** from [`configs/models.toml`](../../configs/models.toml) (for
  example `groq-llama-3.1-8b`, `openrouter-free`, `gpt-4o`)
- **Provider-qualified ids** such as `ollama/llama3.1:8b`
- **Free-catalog ids** used by `--free`

Also:

| Flag              | Purpose                                          |
| ----------------- | ------------------------------------------------ |
| `--provider <id>` | Force `ollama`, `groq`, `openai`, `anthropic`, … |
| `--free`          | Prefer the curated free/cheap rotation           |
| `--models`        | Print all models grouped by provider and exit    |
| `--byok`          | Interactive key setup → `.env`                   |

Full lists: [Providers](../get-started/providers.md) ·
[Models.MD](../../Models.MD) · [Free models](../get-started/free-models.md).

### Model aliases

These are convenient shortcuts that map to specific models (Gemini-oriented
aliases may still appear for compatibility):

| Alias        | Resolves To                                | Description                                                                                                               |
| ------------ | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| `auto`       | `gemini-2.5-pro` or `gemini-3-pro-preview` | **Default.** Resolves to the preview model if preview features are enabled, otherwise resolves to the standard pro model. |
| `pro`        | `gemini-2.5-pro` or `gemini-3-pro-preview` | For complex reasoning tasks. Uses preview model if enabled.                                                               |
| `flash`      | `gemini-2.5-flash`                         | Fast, balanced model for most tasks.                                                                                      |
| `flash-lite` | `gemini-2.5-flash-lite`                    | Fastest model for simple tasks.                                                                                           |

## Extensions management

| Command                                               | Description                                  | Example                                                                           |
| ----------------------------------------------------- | -------------------------------------------- | --------------------------------------------------------------------------------- |
| `openagent extensions install <source>`               | Install extension from Git URL or local path | `openagent extensions install https://github.com/user/my-extension`               |
| `openagent extensions install <source> --ref <ref>`   | Install from specific branch/tag/commit      | `openagent extensions install https://github.com/user/my-extension --ref develop` |
| `openagent extensions install <source> --auto-update` | Install with auto-update enabled             | `openagent extensions install https://github.com/user/my-extension --auto-update` |
| `openagent extensions uninstall <name>`               | Uninstall one or more extensions             | `openagent extensions uninstall my-extension`                                     |
| `openagent extensions list`                           | List all installed extensions                | `openagent extensions list`                                                       |
| `openagent extensions update <name>`                  | Update a specific extension                  | `openagent extensions update my-extension`                                        |
| `openagent extensions update --all`                   | Update all extensions                        | `openagent extensions update --all`                                               |
| `openagent extensions enable <name>`                  | Enable an extension                          | `openagent extensions enable my-extension`                                        |
| `openagent extensions disable <name>`                 | Disable an extension                         | `openagent extensions disable my-extension`                                       |
| `openagent extensions link <path>`                    | Link local extension for development         | `openagent extensions link /path/to/extension`                                    |
| `openagent extensions new <path>`                     | Create new extension from template           | `openagent extensions new ./my-extension`                                         |
| `openagent extensions validate <path>`                | Validate extension structure                 | `openagent extensions validate ./my-extension`                                    |

See [Extensions Documentation](../extensions/index.md) for more details.

## MCP server management

| Command                                                          | Description                     | Example                                                                                                 |
| ---------------------------------------------------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `openagent mcp add <name> <command>`                             | Add stdio-based MCP server      | `openagent mcp add github npx -y @modelcontextprotocol/server-github`                                   |
| `openagent mcp add <name> <url> --transport http`                | Add HTTP-based MCP server       | `openagent mcp add api-server http://localhost:3000 --transport http`                                   |
| `openagent mcp add <name> <command> --env KEY=value`             | Add with environment variables  | `openagent mcp add slack node server.js --env SLACK_TOKEN=xoxb-xxx`                                     |
| `openagent mcp add <name> <command> --scope user`                | Add with user scope             | `openagent mcp add db node db-server.js --scope user`                                                   |
| `openagent mcp add <name> <command> --include-tools tool1,tool2` | Add with specific tools         | `openagent mcp add github npx -y @modelcontextprotocol/server-github --include-tools list_repos,get_pr` |
| `openagent mcp remove <name>`                                    | Remove an MCP server            | `openagent mcp remove github`                                                                           |
| `openagent mcp list`                                             | List all configured MCP servers | `openagent mcp list`                                                                                    |

See [MCP Server Integration](../tools/mcp-server.md) for more details.

## Skills management

| Command                             | Description                           | Example                                              |
| ----------------------------------- | ------------------------------------- | ---------------------------------------------------- |
| `openagent skills list`             | List all discovered agent skills      | `openagent skills list`                              |
| `openagent skills install <source>` | Install skill from Git, path, or file | `openagent skills install https://github.com/u/repo` |
| `openagent skills link <path>`      | Link local agent skills via symlink   | `openagent skills link /path/to/my-skills`           |
| `openagent skills uninstall <name>` | Uninstall an agent skill              | `openagent skills uninstall my-skill`                |
| `openagent skills enable <name>`    | Enable an agent skill                 | `openagent skills enable my-skill`                   |
| `openagent skills disable <name>`   | Disable an agent skill                | `openagent skills disable my-skill`                  |
| `openagent skills enable --all`     | Enable all skills                     | `openagent skills enable --all`                      |
| `openagent skills disable --all`    | Disable all skills                    | `openagent skills disable --all`                     |

See [Agent Skills Documentation](./skills.md) for more details.
