# OpenAgent docs

Beautiful, multi-provider documentation for **OpenAgent** — the open-source
terminal agent.

**Start here → [Documentation home](./index.md)**

---

## Map

```text
docs/
├── index.md                 ← Hub / landing page
├── get-started/
│   ├── index.md             ← Quickstart
│   ├── installation.mdx     ← Install on every OS
│   ├── authentication.mdx   ← Keys & multi-provider auth
│   ├── providers.md         ← Full provider catalog
│   ├── free-models.md       ← --free catalog & TPM tips
│   └── local-models.md      ← Ollama & LM Studio
├── cli/                     ← Features, settings, tutorials
├── tools/                   ← Built-in tools & MCP
├── reference/               ← Commands, config, policy
├── resources/
│   ├── common-errors.md     ← TPM, docx, bad tool calls
│   └── …                    ← FAQ, troubleshooting, legal
├── core/ · extensions/ · hooks/ · ide-integration/
└── sidebar.json             ← Site navigation
```

---

## OpenAgent vs generic “Gemini-only” docs

These docs are written for OpenAgent’s real product surface:

| Topic     | OpenAgent                                  |
| --------- | ------------------------------------------ |
| Auth      | Local · free keys · BYOK (not Google-only) |
| Models    | 13 providers via `configs/models.toml`     |
| Free path | `--free` + catalog fallback + Ollama last  |
| Privacy   | Local-first default                        |

Upstream-style Gemini pages may still exist under `cli/` for shared tooling
features (skills, hooks, sandbox). Prefer **Get started** for day-one setup.

---

## Browse on GitHub

| Page          | Link                                                            |
| ------------- | --------------------------------------------------------------- |
| Hub           | [docs/index.md](./index.md)                                     |
| Quickstart    | [docs/get-started/index.md](./get-started/index.md)             |
| Common errors | [docs/resources/common-errors.md](./resources/common-errors.md) |
| Models matrix | [Models.MD](../Models.MD)                                       |
| Root README   | [README.md](../README.md)                                       |

---

## Contributing to docs

- Prefer clear tables, short commands, and copy-pasteable snippets.
- Keep provider env var names in sync with `.env.example` and `README.md`.
- Update `sidebar.json` when adding top-level guides.
- Screenshots live in `docs/assets/` (for example `openagent-main-ui.png`).

**License:** Apache-2.0 (same as the project).
