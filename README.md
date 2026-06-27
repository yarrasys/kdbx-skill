# kdbx — KeePassXC credentials skill

A Claude Code skill that reads/writes KeePassXC `.kdbx` vaults to manage
**per-project, per-env credentials** — replacing ad-hoc `.env` files as the
source of truth for secrets, API keys, and tokens, and getting them into your
tools **without ever printing them into the transcript, logs, or shell history**.

> **Status: implemented; test suite green (46 tests, macOS/Linux).** The validated design is in
> [`docs/superpowers/specs/2026-06-27-kdbx-skill-design.md`](docs/superpowers/specs/2026-06-27-kdbx-skill-design.md)
> and the implementation plan in [`docs/superpowers/plans/2026-06-27-kdbx-skill.md`](docs/superpowers/plans/2026-06-27-kdbx-skill.md).
> ⚠️ Windows paths are designed but not yet exercised on real Windows (unit-tested via
> monkeypatch); testers welcome. Audit before trusting it with anything that matters.

## What it does

- **Per project, per env** vaults (`<keepassxc-dir>/<project>/<env>.kdbx`),
  **key-file-only** unlock (no master password), KDBX4 + Argon2.
- A committed [`.keepassxc.json`](docs/superpowers/specs/2026-06-27-kdbx-skill-design.md)
  pointer that declares each env's vault, key file, and a git-reviewable
  `vars` map (`ENV_VAR → entry path`).
- Ops: `init · set · get · list · delete · run · export · import · check · envs · mv · rekey`.
- `kdbx run -- <cmd>` injects mapped secrets as env vars into a child process,
  never printing them; `kdbx export` materializes a gitignored `.env` only when
  a tool demands a file.

## Runtime

Requires [`uv`](https://docs.astral.sh/uv/). The bundled script declares its
dependencies inline (PEP 723) and runs via `uv run` — no global installs.

## Install (as a Claude Code skill)

Clone into your Claude Code skills directory on any machine:

```bash
git clone https://github.com/yarrasys/kdbx-skill ~/.claude/skills/kdbx
```

Claude Code discovers it via `~/.claude/skills/kdbx/SKILL.md`. Update later with
`git -C ~/.claude/skills/kdbx pull`. (Per-project install: clone anywhere and point your
project's skill config at it.) The CLI is then invoked as
`uv run --locked ~/.claude/skills/kdbx/kdbx.py <op>`.

## License

The skill's own source is **MIT** (see [`LICENSE`](LICENSE)). The default engine
`pykeepass` is **GPL-3.0**, fetched at runtime and never bundled here — see
[`NOTICE`](NOTICE) for what that means if you plan to redistribute a bundled,
closed-source product. *(Not legal advice.)*
