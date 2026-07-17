# Provider catalog

OpenAgent routes every request through a single model registry:
[`configs/models.toml`](../../configs/models.toml). Edit that file to add models
or OpenAI-compatible endpoints — no code changes required.

Human-readable model list and vision matrix: [Models.MD](../../Models.MD).

---

## Built-in providers

| Provider     | ID            | Env key              | Typical use                      |
| ------------ | ------------- | -------------------- | -------------------------------- |
| Ollama       | `ollama`      | —                    | Local default, privacy, offline  |
| LM Studio    | `lmstudio`    | —                    | Local GUI-loaded weights         |
| OpenAI       | `openai`      | `OPENAI_API_KEY`     | GPT / o-series frontier          |
| Anthropic    | `anthropic`   | `ANTHROPIC_API_KEY`  | Claude frontier                  |
| Gemini       | `gemini`      | `GEMINI_API_KEY`     | Google models + free tier        |
| Groq         | `groq`        | `GROQ_API_KEY`       | Ultra-fast inference             |
| DeepSeek     | `deepseek`    | `DEEPSEEK_API_KEY`   | Low-cost reasoning / chat        |
| NVIDIA       | `nvidia`      | `NVIDIA_API_KEY`     | Nemotron & hosted models         |
| Together AI  | `together`    | `TOGETHER_API_KEY`   | Hosted open weights              |
| Hugging Face | `huggingface` | `HF_TOKEN`           | Free inference (rate-limited)    |
| OpenRouter   | `openrouter`  | `OPENROUTER_API_KEY` | Marketplace + many `:free`       |
| Cerebras     | `cerebras`    | `CEREBRAS_API_KEY`   | High tok/s free public endpoints |
| Z.ai         | `z-ai`        | `Z_AI_API_KEY`       | GLM models                       |

---

## How routing works

```text
CLI flag / /models / defaults
        │
        ▼
 configs/models.toml   →  registry key → provider + model id
        │
        ▼
 free_catalog / default_priority  (when --free or no model)
        │
        ▼
 Provider HTTP (or local)  →  stream / tools / finish
        │
        ▼
 On rate-limit / failure  →  next free_catalog entry → local fallback
```

- **`--provider <id>`** — force a backend.
- **`-m` / `--model`** — registry key, free-catalog id, or `provider/model`.
- **`--free`** — walk the curated free/cheap list; local models close the chain.
- **`--models`** — print the full grouped inventory and exit.

---

## Example invocations

```bash
# Local
npm start -- --provider ollama
npm start -- -m ollama/llama3.1:8b
npm start -- --provider lmstudio

# Free-oriented cloud
npm start -- --free "write a pytest for utils.py"
npm start -- -m openrouter-free
npm start -- -m groq-llama-3.1-8b
npm start -- -m cerebras-gpt-oss-120b

# Frontier BYOK
npm start -- -m gpt-4o
npm start -- --provider anthropic -m claude-sonnet-4-6
npm start -- -m gemini-2.5-flash
```

---

## Registry anatomy (`configs/models.toml`)

```toml
[models."groq-llama-3.1-8b"]
model = "groq/llama-3.1-8b-instant"
temperature = 0.1
max_tokens = 4096
tier = "free_tier"
notes = "Groq Llama 3.1 8B Instant (generous free tier)"

[[free_catalog]]
id = "groq-llama-3.1-8b"
model_key = "groq-llama-3.1-8b"
provider = "groq"
```

| Field                  | Meaning                                           |
| ---------------------- | ------------------------------------------------- |
| `model`                | LiteLLM-style `provider/model-id` sent to the API |
| `tier`                 | Informational: `free_tier`, `paid`, `local`, …    |
| `max_tokens`           | Generation cap for that entry                     |
| `[[free_catalog]]`     | Order used by `--free` rotation                   |
| `[[default_priority]]` | Order when nothing is specified                   |

---

## Vision & streaming

Not every provider accepts images. See the matrix in
[Models.MD](../../Models.MD#vision--streaming-support-matrix). As a rule of
thumb:

| Strong multimodal            | Text-focused today                  |
| ---------------------------- | ----------------------------------- |
| OpenAI GPT-4o / 4.1 / 5\*    | Groq                                |
| Gemini 2.5\*                 | DeepSeek                            |
| Claude Sonnet / Opus / Haiku | Many OpenRouter `:free` text models |
| Local LLaVA (Ollama)         | —                                   |

---

## Adding your own endpoint

1. Open `configs/models.toml`.
2. Add a `[models."my-model"]` table with `model = "openai/..."`,
   `api_base = "https://..."`, and any limits you need.
3. Optionally add it to `[[free_catalog]]` or `[[default_priority]]`.
4. Restart OpenAgent and pick it with `-m my-model` or `/models`.

---

## Related

- [Authentication](./authentication.mdx)
- [Free models](./free-models.md)
- [Local models](./local-models.md)
- [Model routing](../cli/model-routing.md)
