# MCP Server Example

This is a basic example of an MCP (Model Context Protocol) server used as an
OpenAgent extension. It demonstrates how to expose tools and prompts to
OpenAgent.

## Description

The contents of this directory are a valid MCP server implementation using the
`@modelcontextprotocol/sdk`. It exposes:

- A tool `fetch_posts` that mock-fetches posts.
- A prompt `poem-writer`.

## Structure

- `example.js`: The main server entry point.
- `gemini-extension.json`: The configuration file that tells OpenAgent how to
  use this extension.
- `package.json`: Helper for dependencies.

## How to Use

1.  Navigate to this directory:

    ```bash
    cd packages/cli/src/commands/extensions/examples/mcp-server
    ```

2.  Install dependencies:
    ```bash
    npm install
    ```

This example is typically used by `openagent extensions new`.
