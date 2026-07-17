# Local models (Ollama & LM Studio)

Run OpenAgent entirely on your machine. Prompts and files stay local — ideal for
private codebases and offline work.

---

## Why local?

| Benefit        | Detail                                              |
| -------------- | --------------------------------------------------- |
| **No API key** | Zero cloud cost                                     |
| **Privacy**    | Data never leaves the host                          |
| **Offline**    | Works without internet (after models are pulled)    |
| **Fallback**   | Closes the `--free` rotation chain when cloud fails |

---

## Ollama (default)

OpenAgent treats **Ollama at `http://localhost:11434`** as the default local
provider. Installed tags are discovered via `/api/tags`.

### Setup

```bash
# Install from https://ollama.com then:
ollama serve
ollama pull llama3.1:8b
# optional coding / vision models:
ollama pull codellama:7b
ollama pull llava
```

### Run OpenAgent

```bash
npm start
# or pin explicitly
npm start -- --provider ollama
npm start -- -m ollama/llama3.1:8b
openagent -m ollama/llama3.1:8b
```

If no cloud provider is configured, OpenAgent tries Ollama first.

---

## LM Studio

1. Start the **local server** in LM Studio (OpenAI-compatible API).
2. Load a model in the UI.
3. Point OpenAgent at it:

```bash
npm start -- --provider lmstudio
# or a registry key such as:
npm start -- -m lmstudio-local
```

Default base URL is commonly `http://localhost:1234/v1` (see
`configs/models.toml` for the active `api_base`).

---

## Choosing a local model size

| RAM (approx.) | Comfortable sizes   | Notes                            |
| ------------- | ------------------- | -------------------------------- |
| 8 GB          | 3B–7B quantized     | Snappy chat; weaker tool use     |
| 16 GB         | 7B–14B              | Good general coding              |
| 32 GB+        | 32B+ / larger quant | Stronger agents & longer context |

Tool-calling quality varies by model. If you see empty tool args (`Shell {}`) or
invented tool names, try a stronger local model or a cloud free-tier model with
better schema following — see [Common errors](../resources/common-errors.md).

---

## Vision locally

Use a vision-capable Ollama tag (for example `llava`) for image tasks. Confirm
with the matrix in [Models.MD](../../Models.MD).

```bash
ollama pull llava
npm start -- -m ollama/llava
```

---

## Troubleshooting local

| Symptom                        | Fix                                                                     |
| ------------------------------ | ----------------------------------------------------------------------- |
| Connection refused on `:11434` | Start `ollama serve`                                                    |
| Model not listed               | `ollama pull <name>` then restart OpenAgent                             |
| Very slow replies              | Smaller quant / fewer concurrent apps using GPU                         |
| LM Studio empty list           | Ensure server is started and a model is loaded                          |
| Agent still hits cloud         | Check `-m` / `--provider` and that no higher-priority default overrides |

---

## Related

- [Quickstart](./index.md)
- [Free models](./free-models.md) (local as final fallback)
- [Providers](./providers.md)
- [Authentication](./authentication.mdx)
