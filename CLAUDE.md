# CLAUDE.md

## This repo

`garmin-connect-cli` — the agent-first CLI for Garmin Connect.
Source of truth for all commands, flags, output formats, and behavior.

## Versioning

The CLI version is in `pyproject.toml` (`project.version`).
The companion skill at `github.com/cluffa/garmin-connect-skill`
carries a matching `version` in its `SKILL.md` frontmatter.
**These two versions must stay in sync.** When you bump the CLI
version, bump the skill version to match. When the skill changes
to document new CLI behavior, bump both.

## Companion skill

A Claude Code skill lives at `github.com/cluffa/garmin-connect-skill`
(`SKILL.md`). It teaches Claude how to use this CLI — every command,
format option, date spec, exit code, and common recipe.

## When changing this repo

**If you add, remove, or change any command, flag, output format, or
behavior:** also update `SKILL.md` in the `garmin-connect-skill` repo
to match. The skill is the agent's instruction manual for this tool;
stale docs break agent workflows. If the change is significant
(new command, breaking change), bump the version in both repos.

## Quick reference

- Run tests: `uv run pytest -v`
- Run the CLI: `uv run garmin [global options] <command> [args]`
- Bump version: edit `project.version` in `pyproject.toml`
- Lint/format: none configured (standard library only)
