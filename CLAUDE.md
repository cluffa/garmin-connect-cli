# CLAUDE.md

## This repo

`garmin-connect-cli` — the agent-first CLI for Garmin Connect.
Source of truth for all commands, flags, output formats, and behavior.

## Companion skill

A Claude Code skill lives at `github.com/cluffa/garmin-connect-skill`
(`SKILL.md`). It teaches Claude how to use this CLI — every command,
format option, date spec, exit code, and common recipe.

## When changing this repo

**If you add, remove, or change any command, flag, output format, or
behavior:** also update `SKILL.md` in the `garmin-connect-skill` repo
to match. The skill is the agent's instruction manual for this tool;
stale docs break agent workflows.

## Quick reference

- Run tests: `uv run pytest -v`
- Run the CLI: `uv run garmin [global options] <command> [args]`
- Lint/format: none configured (standard library only)
