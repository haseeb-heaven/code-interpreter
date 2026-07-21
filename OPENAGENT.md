# OpenAgent Project Context

OpenAgent is an open-source AI agent that brings the power of large language
models directly into the terminal, across multiple providers (Gemini, OpenAI,
Anthropic, OpenRouter, Groq, local/Ollama, and more). It is designed to be a
terminal-first, extensible, and powerful tool for developers.

## Project Overview

- **Purpose:** Provide a seamless terminal interface for LLMs, supporting code
  understanding, generation, automation, and integration via MCP (Model Context
  Protocol), routed through a multi-provider model registry.
- **Main Technologies:**
  - **Runtime:** Node.js (>=22.0.0, recommended ~22.x for development)
  - **Language:** TypeScript
  - **UI Framework:** React (using [Ink](https://github.com/vadimdemedes/ink)
    for CLI rendering)
  - **Testing:** Vitest
  - **Bundling:** esbuild
  - **Linting/Formatting:** ESLint, Prettier
- **Architecture:** Monorepo structure using npm workspaces.
  - `packages/cli`: User-facing terminal UI, input processing, and display
    rendering.
  - `packages/core`: Backend logic, multi-provider model orchestration
    (`configs/models.toml` registry), prompt construction, and tool execution.
  - `packages/a2a-server`: Experimental Agent-to-Agent server.
  - `packages/sdk`: Programmatic SDK for embedding OpenAgent capabilities.
  - `packages/devtools`: Integrated developer tools (Network/Console inspector).
  - `packages/test-utils`: Shared test utilities and test rig.
  - `packages/vscode-ide-companion`: VS Code extension pairing with the CLI.

## Building and Running

- **Install Dependencies:** `npm install`
- **Build All:** `npm run build:all` (Builds packages, sandbox, and VS Code
  companion)
- **Build Packages:** `npm run build`
- **Run in Development:** `npm run start`
- **Run in Debug Mode:** `npm run debug` (Enables Node.js inspector)
- **Bundle Project:** `npm run bundle`
- **Clean Artifacts:** `npm run clean`

## Testing and Quality

- **Test Commands:**
  - **Unit (All):** `npm run test`
  - **Integration (E2E):** `npm run test:e2e`
  - > **NOTE**: Please run the memory and perf tests locally **only if** you are
    > implementing changes related to those test areas. Otherwise skip these
    > tests locally and rely on CI to run them on nightly builds.
  - **Memory (Nightly):** `npm run test:memory` (Runs memory regression tests
    against baselines. Excluded from `preflight`, run nightly.)
  - **Performance (Nightly):** `npm run test:perf` (Runs CPU performance
    regression tests against baselines. Excluded from `preflight`, run nightly.)
  - **Workspace-Specific:** `npm test -w <pkg> -- <path>` (Note: `<path>` must
    be relative to the workspace root, e.g.,
    `-w @open-agent/core -- src/routing/modelRouterService.test.ts`)
- **Full Validation:** `npm run preflight` (Heaviest check; runs clean, install,
  build, lint, type check, and tests. Recommended before submitting PRs. Due to
  its long runtime, only run this at the very end of a code implementation task.
  If it fails, use faster, targeted commands (e.g., `npm run test`,
  `npm run lint`, or workspace-specific tests) to iterate on fixes before
  re-running `preflight`. For simple, non-code changes like documentation or
  prompting updates, skip `preflight` at the end of the task and wait for PR
  validation.)
- **Individual Checks:** `npm run lint` / `npm run format` / `npm run typecheck`

## Development Conventions

- **Contributions:** Follow the process outlined in `CONTRIBUTING.md`.
- **Pull Requests:** Keep PRs small, focused, and linked to an existing issue.
  Always activate the `pr-creator` skill for PR generation, even when using the
  `gh` CLI.
- **Commit Messages:** Follow the
  [Conventional Commits](https://www.conventionalcommits.org/) standard.
- **Imports:** Use specific imports and avoid restricted relative imports
  between packages (enforced by ESLint).
- **License Headers:** For all new source code files (`.ts`, `.tsx`, `.js`),
  include the Apache-2.0 license header with the current year.

## Testing Conventions

- **Environment Variables:** When testing code that depends on environment
  variables, use `vi.stubEnv('NAME', 'value')` in `beforeEach` and
  `vi.unstubAllEnvs()` in `afterEach`. Avoid modifying `process.env` directly as
  it can lead to test leakage and is less reliable. To "unset" a variable, use
  an empty string `vi.stubEnv('NAME', '')`.

## Branches

- `main` — stable releases.
- `develop` — active integration branch; most work lands here first.
- `feature` — latest multi-provider work; README's "from source" install
  instructions point here, not `main`. Don't assume `main` is the most current
  branch for this repo's active work.

## Publishing

Published to npm as **`@haseeb_heaven/open-agent`** (scoped) — the unscoped name
`open-agent` collided with an unrelated pre-existing npm package and was
rejected by the registry. `package.json`'s `name` field must stay scoped; do not
revert it. Install: `npm install -g @haseeb_heaven/open-agent`.

`.github/workflows/release-public-packages.yml` is the real public-registry
release pipeline (npm, Docker Hub, GitHub Release binaries), gated behind
`NPM_TOKEN`/`DOCKERHUB_*` secrets. The other `release-*.yml` workflows are
inherited from upstream Gemini CLI and use Google-internal "wombat" tokens this
fork does not have — they cannot publish to the public npm registry.

`packaging/` holds template manifests (Scoop, Homebrew, AUR, Snap, Chocolatey,
winget) for channels not yet published — see `packaging/README.md`.

`bundle/` accumulates a new content-hashed file per build if not cleaned between
manual runs — sanity-check `npm run bundle` output size before packaging for
publish/release, and clean first if it looks bloated.

## Secrets

API keys and the npm publish token live in root `.env` (gitignored, never
commit). See `.env.example` for the expected keys.

## Documentation

- Always use the `docs-writer` skill when you are asked to write, edit, or
  review any documentation.
- Documentation is located in the `docs/` directory.
- Suggest documentation updates when code changes render existing documentation
  obsolete or incomplete.
