# Agent workflow

This file contains the shared repository workflow rules for coding agents.

## how task prompts should refer to root instruction files

Use a single conditional prompt preamble such as:

```text
If you are Claude Code, read `CLAUDE.md`.
If you are OpenAI Codex, read `AGENTS.md`.

Then read only the task-specific docs explicitly listed in the prompt.
Do not read other docs unless needed.
```

`AGENTS.md` is the shared root instruction file.
`CLAUDE.md` is a short wrapper that imports `AGENTS.md` for Claude Code.

## required workflow

Before making changes:

1. Read the agent-specific root instruction file for your tool.
2. Follow that root file to this shared workflow file.
3. Read only the task-specific docs explicitly named in the prompt.
4. Inspect the relevant existing source files before editing.
5. Use `docs-local/` only if it is available locally and explicitly relevant.

Do not rely on memory from earlier prompts.

Before implementation, print:
- files read
- key constraints extracted
- relevant files/modules identified
- brief implementation plan

## python workflow

- use `uv` for Python environment and dependency management
- do not install Python packages globally
- if the project environment does not exist, create or sync it with `uv`
- use the project-local `.venv`

## completion checklist

Before finishing:
- run `make check`
- run `make format` when formatting is needed
- summarise what changed
- list changed files
- commit with a concise message
