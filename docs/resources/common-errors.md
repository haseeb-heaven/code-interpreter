# Common errors

Practical fixes for issues users hit with multi-provider OpenAgent, free tiers,
Windows shells, and file tools.

---

## Rate limits & context size

### Groq / free tier: request too large (TPM)

```text
groq stream failed (413): Request too large for model `openai/gpt-oss-120b`
Limit 8000, Requested 33502
code: rate_limit_exceeded
```

|              |                                                                                        |
| ------------ | -------------------------------------------------------------------------------------- |
| **Cause**    | Free **tokens-per-minute** budget is smaller than your prompt + tools + history.       |
| **Fix**      | New session; smaller model; local Ollama; avoid huge `@` trees; upgrade provider tier. |
| **Also try** | `--free` so OpenAgent can rotate; `cerebras-gpt-oss-120b`; `/models set ollama/…`      |

### OpenRouter / Hugging Face 429

|           |                                                             |
| --------- | ----------------------------------------------------------- |
| **Cause** | Shared free pool exhausted or key missing.                  |
| **Fix**   | Wait and retry; check key with `/byok`; fall back to local. |

---

## File access

### `@file.docx` → ReadManyFiles · Read 0 file(s)

```text
✓ ReadManyFiles  Attempting to read …\demo_word.docx → Read 0 file(s)
```

|                               |                                                                                                                                                            |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Cause (fixed for `.docx`)** | Older builds treated Word as unreadable binary and excluded `**/*.docx`. Current OpenAgent **extracts plain text from `.docx`** via `read_file` / `@path`. |
| **Still fails when**          | Path is **outside the workspace**, or the file is legacy `.doc` / Excel / PowerPoint.                                                                      |
| **Fix**                       | Copy the `.docx` into the project, then `@scratch/demo_word.docx summarize this`.                                                                          |

### Agent says it cannot locate a file that exists

|           |                                                                                                        |
| --------- | ------------------------------------------------------------------------------------------------------ |
| **Cause** | Path is outside the **workspace root**, ignored by `.gitignore` / ignore files, or binary-skipped.     |
| **Fix**   | Copy/symlink into the project; use `read_file` on a workspace-relative path; convert binaries to text. |

---

## Tool calling (weak / free models)

### `Shell {}` — params must have required property `command`

```text
x  Shell {}
params must have required property 'command'
```

|           |                                                                                                                     |
| --------- | ------------------------------------------------------------------------------------------------------------------- |
| **Cause** | The model invoked `run_shell_command` without arguments (schema violation). Common on small free models under load. |
| **Fix**   | Switch to a stronger model (`/models`); shorten context; retry the prompt; prefer models known for tool use.        |

### `Tool "generic_tool" not found`

```text
Tool "generic_tool" not found. Do not invent tool names.
Use one of: run_shell_command, read_file, grep_search, glob, list_directory, …
```

|           |                                                                         |
| --------- | ----------------------------------------------------------------------- |
| **Cause** | Model hallucinated a tool name.                                         |
| **Fix**   | Stronger model; restate the task; use `/tools` to confirm the live set. |

### `ver` failed on Windows

```text
ver: The term 'ver' is not recognized as a name of a cmdlet…
```

|           |                                                                                          |
| --------- | ---------------------------------------------------------------------------------------- |
| **Cause** | On Windows, shell tools run under **PowerShell**, not `cmd.exe`. `ver` is a CMD builtin. |
| **Fix**   | Use `$PSVersionTable`, `Get-ComputerInfo`, or `cmd /c ver`.                              |

---

## Auth & keys

### No model available / all providers unavailable

1. Run `openagent --models` or `npm start -- --models`.
2. Check `/byok` for missing keys.
3. Confirm Ollama is running for a local safety net.
4. Ensure `.env` is in the project root and not malformed.

### Wrong key for provider

Each provider has **one** env var (see
[Authentication](../get-started/authentication.mdx)). A Gemini key will not
unlock Groq models.

---

## Windows notes

| Topic        | Detail                                                   |
| ------------ | -------------------------------------------------------- |
| Shell        | `powershell.exe -NoProfile -Command <command>`           |
| Paths        | Prefer workspace-relative paths; quote paths with spaces |
| Line endings | Tools tolerate CRLF; prefer UTF-8 files                  |
| Node         | Node.js **22+** required                                 |

---

## Still stuck?

1. [Troubleshooting](./troubleshooting.md) — install / TLS / enterprise cases
2. [FAQ](./faq.md)
3. Open an issue:
   [haseeb-heaven/open-agent](https://github.com/haseeb-heaven/open-agent/issues)
