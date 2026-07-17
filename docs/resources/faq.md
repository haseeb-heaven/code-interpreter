# Frequently asked questions (FAQ)

Answers for **OpenAgent** — multi-provider terminal agent (local, free, and
BYOK).

For step-by-step fixes (TPM, `.docx`, bad tool calls), see
[Common errors](./common-errors.md).

---

## Product basics

### What is OpenAgent?

An open-source agent that runs in your terminal. You describe a task; it uses
tools (files, shell, web, MCP) with the model you choose — Ollama, free cloud
tiers, or paid frontier APIs.

### Do I need a Google account?

**No.** Local models need no account. Cloud providers each use their own API
key. Google/Gemini is optional (via `GEMINI_API_KEY` or optional Google flows).

### Is my code sent to the cloud?

- **Local (Ollama / LM Studio):** stays on your machine.
- **Cloud providers:** prompts and tool context are sent to that provider under
  their terms. Use local models for private work.

### How is this different from a single-vendor CLI?

OpenAgent is multi-provider by design: one registry (`configs/models.toml`),
`--free` fallback, and local-last-resort routing. See
[Providers](../get-started/providers.md).

---

## Models & free tier

### How do I run with zero paid APIs?

1. Install Ollama and pull a model, **or**
2. Use `--free` with free-tier keys (OpenRouter, Groq, Gemini, Cerebras, …).

Guides: [Local models](../get-started/local-models.md) ·
[Free models](../get-started/free-models.md).

### Why did I get a 413 / TPM rate limit on Groq?

Free tiers cap **tokens per minute**. Large history + tool schemas exceed the
cap. Start a new session, pick a smaller model, or use local. Details:
[Common errors](./common-errors.md#groq--free-tier-request-too-large-tpm).

### Why can’t the agent read my `.docx`?

Office documents are binary. Convert to text first, then `@` the `.txt`. See
[Common errors](./common-errors.md).

### How do I add my own model?

Edit `configs/models.toml` — add a `[models."name"]` entry (and optional
`api_base`). Restart and select with `-m name`.

---

## Usage

### How do I switch models mid-session?

```text
/models
/models set ollama/llama3.1:8b
```

### How do I save an API key without editing files?

```bash
openagent --byok
# or in-session:
/byok groq gsk_...
```

### Can I use OpenAgent in CI?

Yes — headless mode:

```bash
openagent -p "run the unit tests and summarize failures"
# from a clone:
npm start -- --free -p "…"
```

See [Headless mode](../cli/headless.md) and
[Automation](../cli/tutorials/automation.md).

### Why did the shell tool reject empty parameters?

The model called `run_shell_command` without a `command`. Prefer a stronger
model for tool-heavy work. See [Common errors](./common-errors.md).

---

## Technical

### Why am I getting an `ERR_REQUIRE_ESM` error when running `npm run start`?

Usually a CommonJS / ESM mismatch. Ensure:

1. `package.json` has `"type": "module"`.
2. TypeScript `module` is `NodeNext` (or compatible).

Then:

```bash
rm -rf node_modules package-lock.json   # or Windows equivalent
npm install
npm run build
```

### Why don't I see cached token counts in `/stats`?

Cached-token stats depend on the active provider and whether that backend
reports cache hits. Not all free/local endpoints expose cache metrics.

### Command not found: `gemini`

Use **`openagent`** (or `npm start` from a clone). Older docs may mention
`gemini` from upstream naming.

---

## Security

### Can third-party tools piggyback on my OAuth / keys?

Do not share API keys or OAuth tokens with untrusted tools. Prefer
provider-issued keys scoped to your account and rotate if leaked. See
[Terms and privacy](./tos-privacy.md).

### Should I use `--yolo`?

Only in isolated, trusted workspaces. Prefer default approval or
`--approval-mode=plan` when exploring.

---

## Where next?

| Topic           | Link                                                                           |
| --------------- | ------------------------------------------------------------------------------ |
| Quickstart      | [Get started](../get-started/index.md)                                         |
| Providers       | [Provider catalog](../get-started/providers.md)                                |
| Errors          | [Common errors](./common-errors.md)                                            |
| Troubleshooting | [Troubleshooting](./troubleshooting.md)                                        |
| GitHub issues   | [haseeb-heaven/open-agent](https://github.com/haseeb-heaven/open-agent/issues) |
