# CLAUDE.md

## This repo

`garmin-connect-skill` — holds the Claude Code skill (`SKILL.md`) that
teaches Claude how to use the `garmin-connect-cli` tool.

## Versioning

The skill version is in `SKILL.md` frontmatter (`version` field).
The CLI version is in `github.com/cluffa/garmin-connect-cli` at
`pyproject.toml` (`project.version`).
**These two versions must stay in sync.** Bump them together.
Match the CLI's semver — if the CLI goes to `0.2.0`, the skill
goes to `0.2.0` in the same commit wave.

## Source of truth

The CLI implementation lives at `github.com/cluffa/garmin-connect-cli`.
That repo is the authoritative source for all commands, flags, output
formats, and behavior. This skill documents that interface.

## When changing this repo

**When the CLI gains new commands, changes flags, or alters behavior:**
update `SKILL.md` here to match. Keep the command reference, recipes,
and format documentation in sync with the CLI's `README.md` and actual
`--help` output. If the change is significant (new command, breaking
change), bump the version in `SKILL.md` and ensure the CLI's
`pyproject.toml` version matches.

## Quick reference

- The skill is a single file: `SKILL.md`
- It uses standard Claude Code skill format (YAML frontmatter + markdown body)
- Trigger phrases are in the `description` frontmatter field
- Bump version: edit `version` in `SKILL.md` frontmatter
