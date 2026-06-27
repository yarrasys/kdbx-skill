# Security model, trust boundary, runbooks

## Unlock & permissions

- **Key-file-only**, no master password (fully scriptable). The keyfile is the *sole* secret —
  anyone who can read the keyfile **and** the vault can open it.
- **Losing the keyfile makes the vault unrecoverable.** Back it up out-of-band.
- Vault, keyfile, and any exported `.env` are `0600` on POSIX (re-applied after every save,
  because pykeepass resets perms on write) and inheritance-stripped owner-only ACLs on Windows.
- Keyfile + vault are co-located by default (like `~/.ssh`, `~/.aws`) — an accepted tradeoff.

## Secret-handling invariants

- The agent never authors or observes a value; it handles the **PATH / var-name** only.
- Values enter via stdin / `getpass` / `--from-env` (set by an outer orchestrator) — **never
  argv, never stdout** (except an explicit `get --reveal`/`--clip`).
- Errors are scrubbed: no value appears in tracebacks; full traceback only under `KDBX_DEBUG`.

## `run` trust boundary

`kdbx run -- <cmd>` injects secrets into the child's environment. They are visible to the child
**and all its descendants**, and on Linux via `/proc/<pid>/environ` to same-uid code. "Never
printed" ≠ "not exposed to same-user code" — but this is strictly better than the `.env` it
replaces, and inherent to any injection mechanism.

## Soft-delete is recoverable

`delete` moves an entry to the Recycle Bin (recoverable) rather than destroying it. A *compromised*
secret therefore persists until `delete --purge`. Rotate compromised secrets at the source
regardless — deletion is not containment.

## Runbooks

**Keyfile or vault leaked.** Assume every secret in that vault is exposed. 1) Rotate each secret
at its source (provider dashboards). 2) `kdbx rekey` to mint a new keyfile (protects the vault
file going forward, but does **not** un-expose already-leaked secrets). 3) Audit access.

**Coming off a committed `.env`.** `kdbx import .env`, then remove the `.env`, ensure it's
gitignored, scrub it from git history (`git filter-repo`), and **rotate anything ever committed**
— history and forks may retain it.

> No warranty. Provided "as is" under the MIT License (the engine `pykeepass` is GPL-3.0,
> fetched at runtime — see `NOTICE`). Audit before relying on this for anything that matters.
