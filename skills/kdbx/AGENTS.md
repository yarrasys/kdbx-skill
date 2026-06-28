# AGENTS.md — kdbx

Guidance for AI coding agents working **on the kdbx skill** (`skills/kdbx/` + `plugins/kdbx/`).
See [SKILL.md](SKILL.md) for how to *use* kdbx, and the repo-root
[AGENTS.md](../../AGENTS.md) / [CONTRIBUTING.md](../../CONTRIBUTING.md) for monorepo-wide norms.

## What kdbx is

A single PEP-723 Python entry (`kdbx.py`) plus focused modules in `kdbx_core/`, shipped as a Claude
Code skill (with an optional plugin under `plugins/kdbx/`). It manages credentials in key-file-only
KeePassXC KDBX4 vaults.

## Golden rule (security)

**Never author or observe a secret value.** Your job is the entry **path / variable name** only.
- To store a value, instruct the human to pipe it on *their* terminal (`kdbx set api/openai < secret.txt`),
  or use `--from-env VAR` set by an outer orchestrator. Never `echo SECRET | kdbx set …`.
- Prefer `kdbx run -- <cmd>` (inject, never print) over `export` or `get --reveal`.
- Never put a secret value on argv, in a commit, in a test fixture, or in the transcript.
- The plugin's `PreToolUse` hook **enforces** "agent reads, human writes"; the bare skill states it
  as a contract.

## Working in the codebase

- **Tests** (suite lives in `skills/kdbx/tests/` + `plugins/kdbx/tests/`):
  `uv run --with pytest --with pykeepass --with python-dotenv --with filelock --with platformdirs --with "mcp>=1.0,<2" python -m pytest`
- **Lint:** `uvx ruff check .` / `uvx ruff format .`.
- **Smoke the locked entrypoint:** `uv run --locked skills/kdbx/kdbx.py --version`.
- **Engine boundary:** only `kdbx_core/vault.py` may import `pykeepass`. Keep its public interface
  engine-agnostic (plain paths/str in and out) — the single swap point for a permissive engine.
- **TDD:** failing test first; keep the suite green. CI runs on Linux/macOS/Windows.
- **Lockfiles:** changing `kdbx.py` deps → `uv lock --script skills/kdbx/kdbx.py`, commit `kdbx.py.lock`
  (same for `plugins/kdbx/mcp/server.py`).
- **CHANGELOG:** record changes in `skills/kdbx/CHANGELOG.md` under `## [Unreleased]`; release tag =
  `kdbx/v<version>`.
- **Docs of record:** design spec + plan under `docs/superpowers/`.
