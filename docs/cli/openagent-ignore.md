# Ignoring files

This document provides an overview of the OpenAgent Ignore (`.openagentignore`)
feature of open-agent.

open-agent includes the ability to automatically ignore files, similar to
`.gitignore` (used by Git) and `.aiexclude` (used by Gemini Code Assist). Adding
paths to your `.openagentignore` file will exclude them from tools that support
this feature, although they will still be visible to other services (such as
Git).

> **Legacy filename:** For backward compatibility, `.geminiignore` is still read
> as a fallback if `.openagentignore` is not present. New projects should use
> `.openagentignore`.

## How it works

When you add a path to your `.openagentignore` file, tools that respect this
file will exclude matching files and directories from their operations. For
example, when you use the `@` command to share files, any paths in your
`.openagentignore` file will be automatically excluded.

For the most part, `.openagentignore` follows the conventions of `.gitignore`
files:

- Blank lines and lines starting with `#` are ignored.
- Standard glob patterns are supported (such as `*`, `?`, and `[]`).
- Putting a `/` at the end will only match directories.
- Putting a `/` at the beginning anchors the path relative to the
  `.openagentignore` file.
- `!` negates a pattern.

You can update your `.openagentignore` file at any time. To apply the changes,
you must restart your open-agent session.

## How to use `.openagentignore`

To enable `.openagentignore`:

1. Create a file named `.openagentignore` in the root of your project directory.

To add a file or directory to `.openagentignore`:

1. Open your `.openagentignore` file.
2. Add the path or file you want to ignore, for example: `/archive/` or
   `apikeys.txt`.

### `.openagentignore` examples

You can use `.openagentignore` to ignore directories and files:

```
# Exclude your /packages/ directory and all subdirectories
/packages/

# Exclude your apikeys.txt file
apikeys.txt
```

You can use wildcards in your `.openagentignore` file with `*`:

```
# Exclude all .md files
*.md
```

Finally, you can exclude files and directories from exclusion with `!`:

```
# Exclude all .md files except README.md
*.md
!README.md
```

To remove paths from your `.openagentignore` file, delete the relevant lines.
