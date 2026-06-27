# Fallback: read-only `keepassxc-cli`

`pykeepass` is the **sole writer**. On a box where uv/pykeepass can't run, you can still
**read** a kdbx-created vault with `keepassxc-cli` (GPL, a separate program). Never use it to
**write** a vault this skill manages — two writers risk format drift.

Vaults are KDBX4 + Argon2 with key-file-only unlock, so every command uses `--no-password -k`:

```bash
# list entries
keepassxc-cli ls   --no-password -k <env>.keyx <env>.kdbx

# show an entry (reveal a protected field with -a / -s)
keepassxc-cli show --no-password -k <env>.keyx -s -a Password <env>.kdbx <group>/<title>

# search
keepassxc-cli search --no-password -k <env>.keyx <env>.kdbx <term>
```

## Per-OS binary locations (installer usually does NOT add it to PATH)

| OS | Path |
|----|------|
| macOS | `/Applications/KeePassXC.app/Contents/MacOS/keepassxc-cli` (or `/opt/homebrew/bin/keepassxc-cli`) |
| Windows | `C:\Program Files\KeePassXC\keepassxc-cli.exe` |
| Linux | `/usr/bin/keepassxc-cli` (distro package `keepassxc`) |

Find it: `command -v keepassxc-cli` (POSIX) / `where keepassxc-cli` (Windows).

> Keyfile interop is verified both directions: a vault+keyfile created by this skill reads
> cleanly under `keepassxc-cli`, and vice-versa. `keepassxc-cli db-create`, however, defaults
> to **KDBX 3.1 / AES-KDF** — do not use it to create vaults for this skill.
