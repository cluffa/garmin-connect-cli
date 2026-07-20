# CLAUDE.md

## This repo

`garmin-connect-skill` — holds the Claude Code skill (`SKILL.md`) that
teaches Claude how to use the `garmin-connect-cli` tool.

## Source of truth

The CLI implementation lives at `github.com/cluffa/garmin-connect-cli`.
That repo is the authoritative source for all commands, flags, output
formats, and behavior. This skill documents that interface.

## When changing this repo

**When the CLI gains new commands, changes flags, or alters behavior:**
update `SKILL.md` here to match. Keep the command reference, recipes,
and format documentation in sync with the CLI's `README.md` and actual
`--help` output.

## Quick reference

- The skill is a single file: `SKILL.md`
- It uses standard Claude Code skill format (YAML frontmatter + markdown body)
- Trigger phrases are in the `description` frontmatter field
