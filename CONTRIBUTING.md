# Contributing to Yarrasys Skills

Thanks for your interest! This is an umbrella monorepo of agent skills — contributions (bug reports,
fixes, docs, new skills) are welcome.

## Ground rules

- **Never commit a real secret.** Vaults (`*.kdbx`), key files (`*.keyx`), and `.env` files are
  gitignored; tests use throwaway fixtures in temp dirs.
- Be kind. See the [Code of Conduct](CODE_OF_CONDUCT.md).

## Layout

Each skill is self-contained under `skills/<name>/` (+ an optional plugin under `plugins/<name>/`),
with its own `SKILL.md`, `tests/`, `CHANGELOG.md`, `NOTICE`, and `AGENTS.md`. Work on a skill from
inside its directory and follow that skill's `AGENTS.md` for skill-specific rules.

## Development

Requires [uv](https://docs.astral.sh/uv/) (the only prerequisite — it provides Python + deps).

```bash
git clone https://github.com/yarrasys/skills && cd skills

# run all tests
uv run --with pytest --with pykeepass --with python-dotenv --with filelock --with platformdirs --with "mcp>=1.0,<2" python -m pytest

# lint + format
uvx ruff check . && uvx ruff format .
```

(A skill may have extra prerequisites — see its `AGENTS.md`.)

## Pull requests

1. Open an [issue](https://github.com/yarrasys/skills/issues) first for anything non-trivial.
2. Work **test-first (TDD)** — add a failing test, then the minimal code to pass it. Keep the suite green.
3. Run `ruff check` / `ruff format` before pushing. CI runs tests on Linux/macOS/Windows + lint.
4. Update **the affected skill's** `CHANGELOG.md` under `## [Unreleased]`.
5. Follow any skill-specific rules in `skills/<name>/AGENTS.md` (e.g. engine boundaries, lockfiles).

## Releases

Each skill versions independently. Tag releases as `<skill>/v<version>` (e.g. `kdbx/v0.2.1`).

## Security

Do not open public issues for vulnerabilities — see [SECURITY.md](SECURITY.md).
