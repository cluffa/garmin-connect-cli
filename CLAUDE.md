# CLAUDE.md

## This repo

`garmin-connect-cli` — the agent-first CLI for Garmin Connect, plus the
Claude Code skill that teaches agents to drive it.

```
src/garmin_cli/            # the tool
tests/                     # pytest suite
skills/garmin-connect/     # SKILL.md wrapping the CLI
```

The skill used to live in a separate repo (`cluffa/garmin-connect-skill`).
It was merged in here because it documents flags, output shapes, and error
modes — rename `--start-date` in one repo and the docs go stale in the
other. Same repo means the same commit fixes both.

## Versioning

The CLI version is in `pyproject.toml` (`project.version`).
The skill carries a matching `version` in the `SKILL.md` frontmatter.
**These two versions must stay in sync** — bump them in the same commit.

## When changing this repo

**If you add, remove, or change any command, flag, output format, or
behavior:** update `skills/garmin-connect/SKILL.md` and `README.md` in the
same commit. The skill is the agent's instruction manual for this tool;
stale docs break agent workflows. If the change is significant (new
command, breaking change), bump the version in `pyproject.toml` and
`SKILL.md` together.

## Related projects

- Coaching logic (periodization, zone models, workout library) belongs in a
  separate `running-coach` skill, not here. It is loosely coupled: the coach
  asks for data, this skill knows how to get it. Different lifecycles, and
  this CLI is independently useful without the coaching layer.
- The CLI shares its token store with the
  [Garmin Workout Pipeline MCP server](https://github.com/cluffa/Garmin-Workout-Pipeline).

## Quick reference

- Run tests: `uv run pytest -v`
- Run the CLI: `uv run garmin [global options] <command> [args]`
- Bump version: `project.version` in `pyproject.toml` **and** `version` in
  `skills/garmin-connect/SKILL.md`
- Lint/format: none configured (standard library only)
