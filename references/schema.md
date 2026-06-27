# `.keepassxc.json` schema + path grammar

A committed, secret-free pointer at the repo root. It declares where each env's vault and
keyfile live and which env vars map to which vault entries. Secrets never live here.

## Schema

```json
{
  "project": "ideas",
  "defaultEnv": "dev",
  "envs": {
    "dev": {
      "vault":   "${KEEPASSXC_DIR}/ideas/dev.kdbx",
      "keyFile": "${KEEPASSXC_DIR}/ideas/dev.keyx",
      "vars": {
        "OPENAI_API_KEY": "api/openai:password",
        "DATABASE_URL":   "db/primary:password"
      }
    },
    "prod": { "vars": { "OPENAI_API_KEY": "api/openai:password" } }
  }
}
```

| Field | Required | Meaning |
|-------|----------|---------|
| `project` | yes | logical project name; used to derive default paths |
| `defaultEnv` | yes | env used when neither `--env` nor `$KDBX_ENV` is given |
| `envs` | yes | map of env name → env config |
| `envs.<env>.vault` | no | path to the vault; **omit to derive** `<keepassxc-dir>/<project>/<env>.kdbx` |
| `envs.<env>.keyFile` | no | path to the keyfile; **omit to derive** `<keepassxc-dir>/<project>/<env>.keyx` |
| `envs.<env>.vars` | no | map of `ENV_VAR → entry path`; only `run`/`export`/`check` need it |

- `${KEEPASSXC_DIR}` expands to the OS-aware base: `$XDG_CONFIG_HOME`/`~/.config/keepassxc`
  (macOS/Linux) or `%LOCALAPPDATA%\keepassxc` (Windows). Prefer the token or omission over
  hardcoded absolute paths so the pointer stays portable.
- Active env precedence: `--env` › `$KDBX_ENV` › `defaultEnv`.

## Entry path grammar

```
group/subgroup/Title:field
```

- The part after the **final** `:` is the field; it defaults to `password` when omitted.
- Fields: `password`, `username`, `url`, `notes`, `title`, or any custom string field name.
- `/` separates group path components from the entry title (last segment).
- **Constraint:** name components may not contain `/` or `:` (rejected at write time) — this
  keeps the grammar unambiguous. A custom field literally named `password` is shadowed by the
  builtin; pick a different custom name.

Examples: `api/openai:password` · `db/primary` (→ `password`) · `svc/thing:token` · `Top` (root entry).
