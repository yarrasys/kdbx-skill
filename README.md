# kdbx — KeePassXC credentials skill

A Claude Code skill that reads/writes KeePassXC `.kdbx` vaults to manage
**per-project, per-env credentials** — replacing ad-hoc `.env` files as the
source of truth for secrets, API keys, and tokens, and getting them into your
tools **without ever printing them into the transcript, logs, or shell history**.

> ⚠️ **Status: design phase (work in progress).** The validated design lives in
> [`docs/superpowers/specs/2026-06-27-kdbx-skill-design.md`](docs/superpowers/specs/2026-06-27-kdbx-skill-design.md).
> The implementation is not built yet. Do not use for real secrets until the
> test suite (§13/§16 of the spec) is green.

## What it does (planned)

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

## License

The skill's own source is **MIT** (see [`LICENSE`](LICENSE)). The default engine
`pykeepass` is **GPL-3.0**, fetched at runtime and never bundled here — see
[`NOTICE`](NOTICE) for what that means if you plan to redistribute a bundled,
closed-source product. *(Not legal advice.)*
