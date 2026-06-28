# AGENTS.md

Guidance for AI coding agents working **in this repository** — an umbrella monorepo of agent skills.

## What this repo is

`yarrasys/skills` — a collection of self-contained agent skills, each under `skills/<name>/` with its
own `SKILL.md` (and an optional Claude Code plugin under `plugins/<name>/`). The repo also serves as a
plugin marketplace (`.claude-plugin/marketplace.json`).

## Working in a skill

Each skill is self-contained — its code, tests, docs, `CHANGELOG`, `NOTICE`, and dev guidance live
under `skills/<name>/` (+ `plugins/<name>/`). **Before working on a skill, read that skill's
`AGENTS.md`** (e.g. [`skills/kdbx/AGENTS.md`](skills/kdbx/AGENTS.md)) — it carries the skill-specific
golden rules, build/test commands, and engine boundaries.

## Repo-wide norms

- **TDD**; keep the suite green. Lint with `uvx ruff check .` / `uvx ruff format .`.
- Run all tests: `uv run --with pytest --with pykeepass --with python-dotenv --with filelock --with platformdirs --with "mcp>=1.0,<2" python -m pytest`.
- Record changes in **the affected skill's** `CHANGELOG.md`; release tags are scoped: `<skill>/v<version>`.
- Never commit a real secret (vaults / key files / `.env` are gitignored).
- See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## Tracking

File bugs and ideas as **GitHub Issues**: https://github.com/yarrasys/skills/issues (each labelled
with the skill it concerns, e.g. `skill: kdbx`).
