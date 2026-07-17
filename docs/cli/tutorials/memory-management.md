# Manage context and memory

Control what open-agent knows about you and your projects. In this guide, you'll
learn how to define project-wide rules with `OPENAGENT.md`, teach the agent
persistent facts, and inspect the active context.

## Prerequisites

- open-agent installed and authenticated.
- A project directory where you want to enforce specific rules.

## Why manage context?

open-agent is powerful but general. It doesn't know your preferred testing
framework, your indentation style, or your preference against `any` in
TypeScript. Context management solves this by giving the agent persistent
memory.

You'll use these features when you want to:

- **Enforce standards:** Ensure every generated file matches your team's style
  guide.
- **Set a persona:** Tell the agent to act as a "Senior Rust Engineer" or "QA
  Specialist."
- **Remember facts:** Save details like "My database port is 5432" so you don't
  have to repeat them.

## How to define project-wide rules (OPENAGENT.md)

The most powerful way to control the agent's behavior is through `OPENAGENT.md`
files. These are Markdown files containing instructions that are automatically
loaded into every conversation. For backward compatibility, `AGENTS.md` and
`GEMINI.md` are also recognized as fallbacks if `OPENAGENT.md` is absent.

### Scenario: Create a project context file

1.  In the root of your project, create a file named `OPENAGENT.md`.

2.  Add your instructions:

    ```markdown
    # Project Instructions

    - **Framework:** We use React with Vite.
    - **Styling:** Use Tailwind CSS for all styling. Do not write custom CSS.
    - **Testing:** All new components must include a Vitest unit test.
    - **Tone:** Be concise. Don't explain basic React concepts.
    ```

3.  Start a new session. open-agent will now know these rules automatically.

### Scenario: Using the hierarchy

Context is loaded hierarchically. This lets you have general rules for
everything and specific rules for sub-projects.

1.  **Global:** `~/.openagent/OPENAGENT.md` (Rules for _every_ project you work
    on).
2.  **Project Root:** `./OPENAGENT.md` (Rules for the current repository).
3.  **Subdirectory:** `./src/OPENAGENT.md` (Rules specific to the `src` folder).

**Example:** You might set "Always use strict typing" in your global config, but
"Use Python 3.11" only in your backend repository.

## How to teach the agent facts (Memory)

Sometimes you don't want to write a config file. You just want to tell the agent
something once and have it remember forever. You can do this naturally in chat.

### Scenario: Saving a memory

Just tell the agent to remember something.

**Prompt:** `Remember that I prefer using 'const' over 'let' wherever possible.`

The agent will edit the appropriate memory Markdown file, so the fact is loaded
in future sessions.

**Prompt:** `Save the fact that the staging server IP is 10.0.0.5.`

### Scenario: Using memory in conversation

Once a fact is saved, you don't need to invoke it explicitly. The agent "knows"
it.

**Next Prompt:** `Write a script to deploy to staging.`

**Agent Response:** "I'll write a script to deploy to **10.0.0.5**..."

## How to manage and inspect context

As your project grows, you might want to see exactly what instructions the agent
is following.

### Scenario: View active context

To see the full, concatenated set of instructions currently loaded (from all
`OPENAGENT.md` files and saved memories), use the `/memory show` command.

**Command:** `/memory show`

This prints the raw text the model receives at the start of the session. It's
excellent for debugging why the agent might be ignoring a rule.

### Scenario: Refresh context

If you edit an `OPENAGENT.md` file while a session is running, the agent won't
know immediately. Force a reload with:

**Command:** `/memory reload`

## Best practices

- **Keep it focused:** Avoid adding excessive content to `OPENAGENT.md`. Keep
  instructions actionable and relevant to code generation.
- **Use negative constraints:** Explicitly telling the agent what _not_ to do
  (for example, "Do not use class components") is often more effective than
  vague positive instructions.
- **Review often:** Periodically check your `OPENAGENT.md` files to remove
  outdated rules.

## Next steps

- Learn about [Session management](session-management.md) to see how short-term
  history works.
- Explore the [Command reference](../../reference/commands.md) for more
  `/memory` options.
- Read the technical spec for [Project context](../../cli/openagent-md.md).
- Try the experimental [Auto Memory](../auto-memory.md) feature to extract
  memory updates and reusable skills from your past sessions automatically.
