<!-- Thanks for contributing! Keep PRs focused and test-first. -->

## What & why

<!-- What does this change and why? Which skill does it affect? Link any issue: "Closes #123". -->

## Checklist

- [ ] Tests added/updated and the suite passes (`uv run --with pytest --with pykeepass --with python-dotenv --with filelock --with platformdirs --with "mcp>=1.0,<2" python -m pytest`)
- [ ] `uvx ruff check .` and `uvx ruff format --check .` pass
- [ ] No secret, vault (`*.kdbx`), or key file (`*.keyx`) is committed
- [ ] Updated **the affected skill's** `CHANGELOG.md` under `## [Unreleased]`
- [ ] Followed any skill-specific rules in `skills/<name>/AGENTS.md` (e.g. engine boundary, lockfiles)
