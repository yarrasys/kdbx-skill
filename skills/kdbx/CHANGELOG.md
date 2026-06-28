# Changelog — kdbx

All notable changes to the **kdbx** skill (+ plugin). The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [SemVer](https://semver.org/spec/v2.0.0.html).
Releases are tagged `kdbx/v<version>`.

## [Unreleased]

## [0.2.1] - 2026-06-28

### Fixed

- `install-launcher` shim now resolves the **highest-versioned** kdbx across *all* install
  channels (the Skills-CLI install and every plugin-cache copy) instead of unconditionally
  preferring the standalone — so an update from either channel takes effect and a stale copy can
  never silently shadow it (#14).

## [0.2.0] - 2026-06-28

### Added

- **Claude Code plugin** wrapping the skill ([`plugins/kdbx`](plugins/kdbx)), distributed via this
  repo as a plugin **marketplace** (`.claude-plugin/marketplace.json`). The skill stays the
  portable source of truth; the plugin shares it by symlink (no duplication) and adds an
  **enforced** `PreToolUse` guard hook, a **safe MCP server** (`list`/`envs`/`check`/`get`-masked/
  `run` — no value-crossing tools), and `/kdbx:*` slash commands (#6).
- `install-launcher` operation — an opt-in, self-resolving `kdbx` PATH shim (#10).
- A reproducible terminal demo (VHS) embedded in the skill README (#3).
- Windows CI verified and promoted to a required, blocking status check (#1).

### Changed

- **BREAKING — replaced the prod/`--yes` confirmation gate with a role-based agent/human boundary**
  (#9). Agents read/use secrets (`run`/`get`/`list`/`check`/`envs`/`init`); writes and value
  exposure are a human role — the plugin's `PreToolUse` hook enforces it, the bare skill states it
  as a contract. The real prod boundary is **key-file possession**, not a name match.
- Exit code `4` now means "destructive op not confirmed" — an interactive `y/N` guards the two
  irreversible ops (`delete --purge`, `rekey`).

### Removed

- The `env == "prod"` / inherited-`$KDBX_ENV` write gate and the global `--yes` flag (superseded by
  the role boundary + interactive confirm).

## [0.1.0] - 2026-06-27

Initial release.

### Added

- Per-project, per-env credential management in key-file-only KeePassXC KDBX4 + Argon2 vaults.
- 12 operations: `init`, `set`, `get`, `list`, `delete`, `mv`, `run`, `export`, `import`,
  `check`, `envs`, `rekey`.
- `run -- <cmd>` injects mapped secrets into a child process without printing them;
  `export` materializes a 0600 dotenv only when a tool requires a file.
- Committed `.keepassxc.json` pointer with a git-reviewable `vars` map (env var → entry path).
- Single PEP-723 entry script run via `uv` (no global installs); pinned, locked dependencies.
- Engine-agnostic `vault.py` boundary (pykeepass today; permissive engine swappable later).
- Secret-safety: values never on argv/stdout, scrubbed errors, masked `get` by default,
  prod / inherited-`$KDBX_ENV` write gate.
- Ships as a Claude Code skill (`SKILL.md` + `references/`); 46-test suite.

[Unreleased]: https://github.com/yarrasys/skills/compare/kdbx/v0.2.1...HEAD
[0.2.1]: https://github.com/yarrasys/skills/compare/kdbx/v0.2.0...kdbx/v0.2.1
[0.2.0]: https://github.com/yarrasys/skills/compare/kdbx/v0.1.0...kdbx/v0.2.0
[0.1.0]: https://github.com/yarrasys/skills/releases/tag/kdbx/v0.1.0
