# Troubleshooting guide

This guide covers install, network, and provider issues for **OpenAgent**.

<!-- prettier-ignore -->
> [!TIP]
> Looking for multi-provider failures (Groq TPM, `.docx` read 0 files, empty
> `Shell {}` tool calls, Windows PowerShell quirks)? Start with
> **[Common errors](./common-errors.md)** — it is written for OpenAgent’s free
> and local backends.

Also see:

- [FAQ](./faq.md)
- [Authentication & providers](../get-started/authentication.mdx)
- [Free models](../get-started/free-models.md)

## Authentication or login errors

### Multi-provider keys (recommended path)

- **Symptom:** No models available / every call fails immediately.
- **Checks:**
  1. `npm start -- --models` (or `openagent --models`) — which providers show as
     ready?
  2. `/byok` in-session — missing env vars?
  3. Is Ollama running for a local fallback?
  4. Is `.env` present and loaded from the project root?

Provider env var table:
[Authentication & providers](../get-started/authentication.mdx).

### Google / Gemini Code Assist style errors

The items below apply when you use **Google sign-in or Gemini Code Assist
subscription flows**. They do **not** apply to pure local / Groq / OpenRouter
BYOK usage.

- **Error:
  `You must be a named user on your organization's Gemini Code Assist Standard edition subscription to use this service. Please contact your administrator to request an entitlement to Gemini Code Assist Standard edition.`**

  - **Cause:** This error might occur if OpenAgent CLI detects the
    `GOOGLE_CLOUD_PROJECT` or `GOOGLE_CLOUD_PROJECT_ID` environment variable is
    defined. Setting these variables forces an organization subscription check.
    This might be an issue if you are using an individual Google account not
    linked to an organizational subscription.

  - **Solution:**

    - **Individual Users:** Unset the `GOOGLE_CLOUD_PROJECT` and
      `GOOGLE_CLOUD_PROJECT_ID` environment variables. Check and remove these
      variables from your shell configuration files (for example, `.bashrc`,
      `.zshrc`) and any `.env` files. If this doesn't resolve the issue, try
      using a different Google account.

    - **Organizational Users:** Contact your Google Cloud administrator to be
      added to your organization's Gemini Code Assist subscription.

- **Error:
  `Failed to sign in. Message: Your current account is not eligible... because it is not currently available in your location.`**

  - **Cause:** OpenAgent CLI does not currently support your location. For a
    full list of supported locations, see the following pages:
    - Gemini Code Assist for individuals:
      [Available locations](https://developers.google.com/gemini-code-assist/resources/available-locations#americas)

- **Error: `Failed to sign in. Message: Request contains an invalid argument`**

  - **Cause:** Users with Google Workspace accounts or Google Cloud accounts
    associated with their Gmail accounts may not be able to activate the free
    tier of the Google Code Assist plan.
  - **Solution:** For Google Cloud accounts, you can work around this by setting
    `GOOGLE_CLOUD_PROJECT` to your project ID. Alternatively, you can obtain the
    Gemini API key from
    [Google AI Studio](http://aistudio.google.com/app/apikey), which also
    includes a separate free tier.

- **Error: `UNABLE_TO_GET_ISSUER_CERT_LOCALLY` or
  `unable to get local issuer certificate`**
  - **Cause:** You may be on a corporate network with a firewall that intercepts
    and inspects SSL/TLS traffic. This often requires a custom root CA
    certificate to be trusted by Node.js.
  - **Solution:** First try setting `NODE_USE_SYSTEM_CA`; if that does not
    resolve the issue, set `NODE_EXTRA_CA_CERTS`.
    - Set the `NODE_USE_SYSTEM_CA=1` environment variable to tell Node.js to use
      the operating system's native certificate store (where corporate
      certificates are typically already installed).
      - Example: `export NODE_USE_SYSTEM_CA=1` (Windows PowerShell:
        `$env:NODE_USE_SYSTEM_CA=1`)
    - Set the `NODE_EXTRA_CA_CERTS` environment variable to the absolute path of
      your corporate root CA certificate file.
      - Example: `export NODE_EXTRA_CA_CERTS=/path/to/your/corporate-ca.crt`
        (Windows PowerShell:
        `$env:NODE_EXTRA_CA_CERTS="C:\path\to\your\corporate-ca.crt"`)

## Common error messages and solutions

- **Error: `EADDRINUSE` (Address already in use) when starting an MCP server.**

  - **Cause:** Another process is already using the port that the MCP server is
    trying to bind to.
  - **Solution:** Either stop the other process that is using the port or
    configure the MCP server to use a different port.

- **Error: Command not found (when attempting to run OpenAgent CLI with
  `gemini`).**

  - **Cause:** OpenAgent CLI is not correctly installed or it is not in your
    system's `PATH`.
  - **Solution:** The update depends on how you installed OpenAgent CLI:
    - If you installed `gemini` globally, check that your `npm` global binary
      directory is in your `PATH`. You can update OpenAgent CLI using the
      command `npm install -g open-agent@latest`.
    - If you are running `gemini` from source, ensure you are using the correct
      command to invoke it (for example, `node packages/cli/dist/index.js ...`).
      To update OpenAgent CLI, pull the latest changes from the repository, and
      then rebuild using the command `npm run build`.

- **Error: `MODULE_NOT_FOUND` or import errors.**

  - **Cause:** Dependencies are not installed correctly, or the project hasn't
    been built.
  - **Solution:**
    1.  Run `npm install` to ensure all dependencies are present.
    2.  Run `npm run build` to compile the project.
    3.  Verify that the build completed successfully with `npm run start`.

- **Error: "Operation not permitted", "Permission denied", or similar.**

  - **Cause:** When sandboxing is enabled, OpenAgent CLI may attempt operations
    that are restricted by your sandbox configuration, such as writing outside
    the project directory or system temp directory.
  - **Solution:** Refer to the [Configuration: Sandboxing](../cli/sandbox.md)
    documentation for more information, including how to customize your sandbox
    configuration.

- **OpenAgent CLI is not running in interactive mode in "CI" environments**

  - **Issue:** OpenAgent CLI does not enter interactive mode (no prompt appears)
    if an environment variable starting with `CI_` (for example, `CI_TOKEN`) is
    set. This is because the `is-in-ci` package, used by the underlying UI
    framework, detects these variables and assumes a non-interactive CI
    environment.
  - **Cause:** The `is-in-ci` package checks for the presence of `CI`,
    `CONTINUOUS_INTEGRATION`, or any environment variable with a `CI_` prefix.
    When any of these are found, it signals that the environment is
    non-interactive, which prevents OpenAgent CLI from starting in its
    interactive mode.
  - **Solution:** If the `CI_` prefixed variable is not needed for the CLI to
    function, you can temporarily unset it for the command. For example,
    `env -u CI_TOKEN gemini`

- **DEBUG mode not working from project .env file**

  - **Issue:** Setting `DEBUG=true` in a project's `.env` file doesn't enable
    debug mode for open-agent.
  - **Cause:** The `DEBUG` and `DEBUG_MODE` variables are automatically excluded
    from project `.env` files to prevent interference with open-agent behavior.
  - **Solution:** Use a `.openagent/.env` file instead, or configure the
    `advanced.excludedEnvVars` setting in your `settings.json` to exclude fewer
    variables.

- **Warning: `npm WARN deprecated node-domexception@1.0.0` or
  `npm WARN deprecated glob` during install/update**
  - **Issue:** When installing or updating OpenAgent CLI globally via
    `npm install -g open-agent` or `npm update -g open-agent`, you might see
    deprecation warnings regarding `node-domexception` or old versions of
    `glob`.
  - **Cause:** These warnings occur because some dependencies (or their
    sub-dependencies, like `google-auth-library`) rely on older package
    versions. Since OpenAgent CLI requires Node.js 22 or higher, the platform's
    native features (like the native `DOMException`) are used, making these
    warnings purely informational.
  - **Solution:** These warnings are harmless and can be safely ignored. Your
    installation or update will complete successfully and function properly
    without any action required.

## Exit codes

OpenAgent CLI uses specific exit codes to indicate the reason for termination.
This is especially useful for scripting and automation.

| Exit Code | Error Type                 | Description                                                                                         |
| --------- | -------------------------- | --------------------------------------------------------------------------------------------------- |
| 41        | `FatalAuthenticationError` | An error occurred during the authentication process.                                                |
| 42        | `FatalInputError`          | Invalid or missing input was provided to the CLI. (non-interactive mode only)                       |
| 44        | `FatalSandboxError`        | An error occurred with the sandboxing environment (for example, Docker, Podman, or Seatbelt).       |
| 52        | `FatalConfigError`         | A configuration file (`settings.json`) is invalid or contains errors.                               |
| 53        | `FatalTurnLimitedError`    | The maximum number of conversational turns for the session was reached. (non-interactive mode only) |

## Debugging tips

- **CLI debugging:**

  - Use the `--debug` flag for more detailed output. In interactive mode, press
    F12 to view the debug console.
  - Check the CLI logs, often found in a user-specific configuration or cache
    directory.

- **Core debugging:**

  - Check the server console output for error messages or stack traces.
  - Increase log verbosity if configurable. For example, set the `DEBUG_MODE`
    environment variable to `true` or `1`.
  - Use Node.js debugging tools (for example, `node --inspect`) if you need to
    step through server-side code.

- **Tool issues:**

  - If a specific tool is failing, try to isolate the issue by running the
    simplest possible version of the command or operation the tool performs.
  - For `run_shell_command`, check that the command works directly in your shell
    first.
  - For _file system tools_, verify that paths are correct and check the
    permissions.

- **Pre-flight checks:**
  - Always run `npm run preflight` before committing code. This can catch many
    common issues related to formatting, linting, and type errors.

## Existing GitHub issues similar to yours or creating new issues

If you encounter an issue that was not covered here in this _Troubleshooting
guide_, consider searching OpenAgent CLI
[Issue tracker on GitHub](https://github.com/haseeb-heaven/open-agent/issues).
If you can't find an issue similar to yours, consider creating a new GitHub
Issue with a detailed description. Pull requests are also welcome!

<!-- prettier-ignore -->
> [!NOTE]
> Issues tagged as "🔒Maintainers only" are reserved for project
> maintainers. We will not accept pull requests related to these issues.
