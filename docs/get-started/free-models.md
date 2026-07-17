# Free models (`--free`)

OpenAgent ships a curated **free / cheap model catalog** so you can work without
a paid subscription. Use `--free` for automatic preference and fallback, or pick
entries explicitly with `-m` / `/models`.

---

## Quick start

```bash
# Prefer free catalog (falls through on rate limits)
npm start -- --free "analyze package.json and suggest cleanup"

# See everything, grouped by provider (availability marked)
npm start -- --models

# Pin a free-oriented entry
npm start -- -m openrouter-free
npm start -- -m groq-llama-3.1-8b
npm start -- -m cerebras-gpt-oss-120b
```

In-session:

```text
/models
/models set groq-llama-3.1-8b
```

---

## How `--free` behaves

1. Reads `[[free_catalog]]` from
   [`configs/models.toml`](../../configs/models.toml).
2. Tries entries in order when the current model is rate-limited or fails in a
   classifiable way.
3. **Local models (Ollama / LM Studio) are the final fallback** — if Ollama is
   up, a free-cloud outage should not kill the task.

```text
free cloud A  ──rate limit──▶  free cloud B  ──fail──▶  …  ──▶  local Ollama
```

---

## Popular free-oriented entries

Exact ids can evolve — run `--models` for the live list. Typical catalog
families:

| Family                   | Examples (registry keys)                            | Notes                                   |
| ------------------------ | --------------------------------------------------- | --------------------------------------- |
| **OpenRouter `:free`**   | `openrouter-free`, `openrouter-gpt-oss-20b-free`, … | Needs `OPENROUTER_API_KEY`; pool varies |
| **Groq free tier**       | `groq-llama-3.1-8b`, `groq-gpt-oss-20b`             | Very fast; **strict TPM** on free tier  |
| **Cerebras free public** | `cerebras-gpt-oss-120b`, `cerebras-gemma-4-31b`     | High tokens/s; rate-limited             |
| **Gemini free tier**     | `gemini-2.5-flash`, `gemini-2.5-flash-lite`         | `GEMINI_API_KEY` from AI Studio         |
| **Hugging Face**         | `hf-meta-llama-3`, …                                | `HF_TOKEN`; often slower / limited      |
| **Local**                | `ollama/…`, `local-model`                           | Always free; final fallback             |

---

## Rate limits & TPM (important)

Free endpoints often enforce **tokens per minute (TPM)** or requests per minute
(RPM). A large chat history + tool schemas can exceed the limit even for a short
question.

### Example: Groq free tier

```text
Request too large for model `openai/gpt-oss-120b`
Limit 8000 TPM, Requested 33502
```

**What it means:** the free org tier allows ~8k tokens/minute; the request
payload (system + tools + history + user) was ~33k.

**What to do:**

1. Start a **fresh session** (`/quit` and relaunch, or `--resume` a lighter
   one).
2. Prefer a higher-limit free model (or local).
3. Avoid `@` attaching huge trees or binary files that expand context.
4. Upgrade the provider tier if you need sustained large context.
5. Try Cerebras / OpenRouter free / Ollama as alternatives.

More cases: [Common errors](../resources/common-errors.md).

---

## Tips for reliable free usage

| Tip                                         | Why                                       |
| ------------------------------------------- | ----------------------------------------- |
| Keep Ollama running                         | Guarantees a free offline fallback        |
| Prefer smaller models for tool-heavy agents | Less TPM pressure; often better tool JSON |
| Use `-p` for one-shot tasks                 | Smaller context than long REPL history    |
| Don’t paste secrets into free cloud prompts | Free hosts still send data off-machine    |
| Re-run `--models` after adding keys         | Availability badges update with keys      |

---

## Related

- [Providers](./providers.md)
- [Local models](./local-models.md)
- [Model routing](../cli/model-routing.md)
- [Models.MD](../../Models.MD)
