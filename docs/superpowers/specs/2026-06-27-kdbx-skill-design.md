# kdbx — KeePassXC credentials skill — Design

- **Date:** 2026-06-27
- **Status:** Design (pre-implementation). Plan-ready once this doc is approved.
- **Topic:** A lazy-loaded Claude Code skill that reads/writes KeePassXC `.kdbx` vaults to manage per-project, per-env credentials, replacing ad-hoc `.env` files as the source of truth.

> This design was hardened by an empirical review that ran `uv` + `pykeepass` 4.1.1.post1 + `keepassxc-cli` 2.7.12 on the target box (uv-managed CPython 3.11.15). Claims marked **(E#)** were verified by experiment. Several initial assumptions were proven wrong and are corrected below.

---

## 1. Goal & non-goals

**Goal.** A self-contained, cross-platform (macOS/Linux/Windows + headless CI) skill that manages secrets/API keys/tokens in per-project, per-env KeePassXC vaults, and gets those secrets into running tools **without ever printing them into the transcript, logs, or shell history**. It replaces `.env`-as-source-of-truth.

**Non-goals / out of scope (future work).**
- Migrating an existing legacy single `~/secrets.kdbx` into per-project/per-env vaults. (The orphan `~/.config/keepassxc/secrets.keyx` on this box is a leftover; ignored.)
- A master-password unlock mode. This skill is **key-file-only** by design.
- A GUI, sync, or multi-user sharing model.

---

## 2. Resolved decisions

1. **Engine:** `pykeepass` (pure Python) is the **primary and sole writer**. `keepassxc-cli` is a **documented read-only fallback** only — the skill never shells out to it to write (avoids two-writer format drift). Vaults are **KDBX4 + Argon2d**, **key-file-only** unlock.
2. **Consumption model:** both (a) **`run`** — inject mapped secrets as env vars into a child process, never printed; and (b) **`export`** — materialize a gitignored `.env` on demand for file-only tools. Plus CRUD.
3. **Env-var mapping:** an explicit per-env **`vars` map** in the committed `.keepassxc.json` (`VAR → "group/Title:field"`). Git-reviewable contract; a `check` op detects drift.
4. **Runtime:** **uv + PEP 723** inline deps, **uv is hard-required** (no venv/pip fallback). The script is invoked `uv run --locked /path/to/kdbx.py …`.
5. **Op set (12):** `init, set, get, list, delete, run, export, import, check, envs, mv, rekey`.
6. **License:** the skill's own source is **MIT**. The default engine `pykeepass` is GPL-3.0 but is fetched at runtime via uv (never bundled/redistributed), so the repo and releases ship zero GPL bytes — the MIT grant is honest. See §19 for the carve-out and NOTICE wording.
7. **Engine boundary (E-lite):** `vault.py` exposes an **engine-agnostic interface** (no pykeepass types leak to callers) and is documented as the single swap point, so a permissive engine (`keepass-rs`) can replace the default later without touching `ops`/tests. This is *not* a runtime plugin system — one engine at a time.
8. **After ship (open item):** optionally update `~/.claude/preferences/credentials.md` to point at this skill (currently documents the `keepassxc-cli` convention as source of truth).

---

## 3. Architecture & package layout

Installs **user-global** to `~/.claude/skills/kdbx/` (it is a cross-project tool):

```
~/.claude/skills/kdbx/
  SKILL.md                # lazy-loaded: when-to-use, invocation template, op table, security do/don'ts, pointers
  kdbx.py                 # PEP-723 header (deps), uv entrypoint, CLI dispatch, top-of-file runtime preflight
  kdbx.py.lock            # `uv lock --script kdbx.py` lockfile (hashed); run with `uv run --locked`
  kdbx_core/
    paths.py     # OS-aware <keepassxc-dir> resolution + ~ / XDG / %LOCALAPPDATA% handling
    pointer.py   # find/parse/write .keepassxc.json (walk up from cwd); env selection; vars map
    vault.py     # pykeepass engine — SOLE WRITER: open(keyfile-only), keyfile minting, save wrapper, trash, mv, rekey, field resolver
    ops.py       # the 12 operations
    secretio.py  # masking sentinel, stdin/getpass input, clipboard backends, dotenv render/parse, error scrubbing
    locking.py   # advisory file lock + open-time integrity capture
  references/
    schema.md    # full .keepassxc.json schema + path grammar
    fallback.md  # keepassxc-cli READ-ONLY command crib (per-OS binary locations)
    security.md  # threat model, trust boundary, rotation/leak runbook
  README.md
  LICENSE        # MIT (the skill's own source)
  NOTICE         # GPL-3.0 engine carve-out (see §19)
  SECURITY.md    # vuln-reporting policy (GitHub convention) — points at references/security.md
  tests/         # pytest suite (see §13)
```

- **Sibling imports (E2):** `uv run <abs path>/kdbx.py` puts the script dir on `sys.path[0]`, so `from kdbx_core import …` resolves from any cwd. No `__init__.py` required (ship one only as hygiene).
- **Engine boundary (E-lite):** `vault.py` is the only module that imports pykeepass and the only writer. Its **public interface is engine-agnostic** — callers pass/receive plain types (paths, field names, `bytes`/`str`), never pykeepass objects — so the GPL engine is isolated behind one swappable seam (the documented insertion point for a future MIT `keepass-rs` engine). This is a clean boundary, **not** a runtime plugin abstraction.

---

## 4. Path resolution & discovery

**`<keepassxc-dir>` (OS-aware, never hardcode `~`):**
- macOS/Linux: `$XDG_CONFIG_HOME/keepassxc` else `~/.config/keepassxc`.
- Windows: `%LOCALAPPDATA%\keepassxc` (**not** `%APPDATA%` — roaming replicates the keyfile off-box). Resolve via `platformdirs` (`roaming=False`) or `FOLDERID_LocalAppData`.
- **Sync-root guard:** warn/confirm if the resolved keyfile path is under a known sync root (OneDrive/Dropbox/iCloud/Nextcloud or `AppData\Roaming`).

**Discovery:** walk up from cwd to the nearest `.keepassxc.json`. Active env = `--env` flag › `$KDBX_ENV` › pointer `defaultEnv`. Resolve `vault`/`keyFile` for that env.

**No-pointer fallback:** `<keepassxc-dir>/<repo-dir-name>/<env>.{kdbx,keyx}`. Writes/`init` on a fallback path are **gated** — see §10 (confirmation wire-protocol).

---

## 5. Data model — `.keepassxc.json`

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
    }
  }
}
```

- **`vault`/`keyFile` are optional.** When omitted, derive from the same OS-aware resolver used for the no-pointer fallback (free portability across OS/XDG). A `${KEEPASSXC_DIR}` token is supported for explicit-but-portable paths. `init` writes the token/omitted form, **never** a resolved macOS-absolute path. Bare `~`/absolute paths are warned (not forbidden).
- **`vars` is optional per env** (only `run`/`export`/`check` need it).
- **Path grammar:** `group/subgroup/Title:field`; `:field` defaults to `password`. **`/` and `:` are rejected in any name component at write time** (`set`/`import`/`mv`) — KeePass legally allows them (verified), so without this rule `https://api` titles and `a/b` groups mis-parse. `run`/`export`/`check` **fail loudly** on an unparseable path, never resolve to a wrong entry.
- **Write-back hygiene:** `set --var`/`import`/`mv` mutate this git-tracked file. Serialize with `json.dump(indent=2, sort_keys=False)` (key order is preserved — verified) via temp + `os.replace`, and print `modified tracked file .keepassxc.json — review and commit`.

---

## 6. Engine contract — `vault.py` (the corrections live here)

**Open:** `PyKeePass(vault, keyfile=keyfile)`, no password.

**Keyfile minting (E3 — load-bearing ordering).** `create_database(keyfile=path)` *reads* the keyfile and never writes it; a missing path raises `FileNotFoundError`. So `init`:
1. Mints the keyfile **first**, in pure Python: a KeePassXC **`.keyx` v2.0 XML** wrapping 32 `os.urandom` bytes (round-trips both engines per E6; preferred over raw bytes, which trip the CLI's "old key file format" warning). Written atomically at 0600.
2. **Then** `create_database(vault, keyfile=keyfile)`.
3. Refuses if **either** vault or keyfile already exists (not just the vault).

**KDF (E4).** Default is KDBX4 + Argon2d / 64 MiB / t=14 / p=2 and is **read-only / non-tunable** via pykeepass. `init` asserts `version[0]==4 and kdf_algorithm=='argon2'` post-create so a future template regression fails loudly. Documented as non-configurable; immaterial under a full-entropy keyfile.

**Delete semantics (E5 — the critical correction).** pykeepass `delete_entry()` == `entry.delete()` == **permanent hard delete** (Recycle Bin never created). Therefore:
- `delete` routes through **`trash_entry()`/`trash_group()`** (auto-creates the Recycle Bin, stays in-engine). `delete_entry()` is forbidden in code (commented).
- `--purge` does true removal (`delete_entry` + `empty_group`).
- **`list`/`get`/`check` exclude the Recycle Bin subtree** — `kp.entries` includes trashed entries, so otherwise a deleted secret reports as live and as "unreferenced."

**Save wrapper (E8 + Windows).** One centralized `save()` in `vault.py`, used by every mutating op:
- Write to a tool-owned sibling temp → `os.replace(tmp, vault)` (atomic on POSIX **and** Windows; avoids pykeepass's `shutil.move` degrading to a truncating in-place copy on Windows).
- `os.chmod(vault, 0o600)` **after every save** (pykeepass resets 0600→0644 on each write — verified).
- `os.umask(0o077)` at process start (closes the temp-file TOCTOU window).
- Keep a `.bak` until `os.replace` succeeds.

**Concurrency (`locking.py`).** Atomic save prevents a torn file but not lost updates; pykeepass takes no lock and ignores KeePassXC's `.kdbx.lock`. Write ops take an advisory `filelock` on a sidecar and capture vault mtime/size/hash at open, re-verified before save → fail "vault changed underneath us, re-run." Docs note the GUI must not hold the vault open during writes.

**Field resolver (one shared impl for run/export/check/get).** Reserved tokens `title|username|password|url|notes` (case-normalized) → `entry.<attr>`; everything else → `get_custom_property` (case-sensitive, do not lowercase custom keys). **Error on a missing field — never inject `None`/empty** (`get_custom_property('password')` returns `None`, `'Password'` raises — both are traps).

**Group creation.** No `find_or_create_group` exists (verified). Walk-and-create with `find_groups_by_path(..., first=True)`, creating a segment only when absent (naive `add_group` makes duplicate siblings).

**`mv` / `rekey`.**
- `mv OLD NEW`: `move_entry`/`move_group` (verified present); move the vault entry first, then rewrite affected `vars` in the pointer; `check` reconciles a crash between (the two files can't commit atomically).
- `rekey`: mint a new keyfile → re-save vault under it → remove the old keyfile (plain `unlink`; secure-erase is ineffective on SSD/APFS — the runbook is the real mitigation). Plus a leak runbook (a prior keyfile+vault leak means secrets are already exposed — rotate at source).

---

## 7. Operations (12)

| Op | Behavior | Secret safety |
|---|---|---|
| `init [--env E] [--confirm-fallback]` | mint keyfile then create KDBX4/Argon2 vault; chmod 0600; refuse if vault **or** keyfile exists; post-create KDF assertion | generates keyfile |
| `set PATH [--var NAME] [--from-env VAR] [--raw]` | upsert field, idempotent group creation; value from **stdin or `--from-env`, never argv**; optionally register the var mapping | value never on argv/stdout |
| `get PATH [--reveal\|--clip]` | masked default → constant sentinel `(set, hidden)` (no length/prefix leak); `--reveal` → stdout (warns re: scrollback/CI logs); `--clip` → clipboard with auto-clear | reveal is opt-in |
| `list [GROUP]` | entry paths + which vars point at them; **excludes Recycle Bin** | values never shown |
| `delete PATH [--purge]` | soft-delete via `trash_entry` (recoverable); `--purge` = permanent | — |
| `mv OLD NEW` | rename/move entry or group; rewrites affected vars | — |
| `run [--env E] [--allow-missing] -- CMD…` | resolve active `vars`, inject as env into child, exec; **propagates child exit code**; missing var fails fast unless `--allow-missing` (skip + non-zero) | only in child env, never printed |
| `export [--out F] [--force\|--merge]` | render resolved vars as dotenv; `os.open(O_CREAT\|O_WRONLY\|O_TRUNC, 0600)` + fchmod; refuse if target has non-managed keys unless `--force`/`--merge`; verify gitignored (auto-append + notice, or refuse) | plaintext-on-disk warning |
| `import FILE` | parse `.env` (minimal grammar §11), write entries + populate vars; post-import checklist (remove/gitignore source, rotate ever-committed secrets); offers (never forces) source deletion | path-only, never echoes |
| `check [--json]` | every var resolves to a real entry/field (Recycle-Bin-excluded); report missing + (info) unreferenced; **non-zero exit on drift** | — |
| `envs` | list configured envs, mark active + its source | — |
| `rekey [--env E]` | rotate the keyfile; re-save vault; unlink old (secure-erase ineffective on SSD — rotate at source) | — |

---

## 8. Secret-handling invariants

- **The agent never authors or observes a secret value.** Its role is the entry PATH / var-name only. New values enter via a channel the model can't read.
- **Input channels:** human pipes to stdin in their own terminal (`kdbx set PATH < secret.txt`), or `--from-env VAR` set by an **outer** orchestrator (the CI contract), or `getpass` (with confirm re-entry) when `stdin.isatty()`. **Forbidden:** `echo SECRET | kdbx set …` and `export SECRET=…; kdbx set --from-env SECRET` from within the agent session (both put plaintext in the transcript).
- **Never on argv.** Enforced for `set` and every op; **a test asserts the value never appears in argv**.
- **stdin newline policy:** trim one trailing `\r\n` by default (`sys.stdin` does not translate newlines — verified); `--raw` for PEM/JSON/binary.
- **Error scrubbing:** top-level handler prints a fixed sanitized one-liner (`kdbx: <op> failed: <ExceptionType>`); raw traceback only under `--debug`/`KDBX_DEBUG`; **never interpolate field values into exceptions** (cite the KEY/path). Test covers stderr too. (`sys.tracebacklimit=0` does **not** suppress the message line — don't rely on it.)
- **`run` trust boundary (doc):** injected secrets are visible to the child and all descendants, and on Linux via `/proc/<pid>/environ` to same-uid code. "Never printed" ≠ "not exposed to same-user code" — but strictly better than the `.env` it replaces.

---

## 9. Environment safety

- Echo `ACTIVE ENV: <e>  vault=<abs path>  (source: --env|$KDBX_ENV|pointer)` to **stderr** before any mutating/export/run op.
- **Gate prod** (and any env **inherited from `$KDBX_ENV`** rather than an explicit `--env`) behind `--yes`. Rationale: a stale `KDBX_ENV=prod` otherwise silently targets prod — and given §6 delete semantics, worst case is unrecoverable prod loss.
- `--env` flag on **all** ops; precedence over `$KDBX_ENV`. CI passes `--env` + `--yes` explicitly.

---

## 10. Cross-platform specifics

- **Perms:** `chmod 0600` is a no-op on Windows. There, apply `icacls <path> /inheritance:r /grant:r "%USERNAME%":F` (or `SetNamedSecurityInfo`) to keyfile/vault/exported `.env`, **re-applied after every save** (atomic rename re-inherits parent ACLs). Docs: the "0600" guarantee is POSIX-scoped; on Windows protection is ACL/location-based. Prioritize the `export` path (often outside the protected profile dir).
- **`run` exec:** POSIX `os.execvp`; Windows `shutil.which`-resolve (honors PATHEXT, finds `npm`/`vite` `.cmd` shims) then `subprocess.run(shell=False)`, wait, `sys.exit(returncode)`, with a CTRL_C relay. Exit-code propagation is part of the `run` contract.
- **dotenv:** round-trip via `python-dotenv` `set_key()`/`dotenv_values()` (not hand-rolled); write `newline='\n'`; strip a single trailing `\r\n` on read. Pin **one** documented dialect and name which consumers it's verified against (docker-compose vs Vite/Next/python-dotenv differ on `$`-interpolation/quoting).
- **Clipboard backends:** macOS `pbcopy`; Windows PowerShell `Set-Clipboard` (over `clip.exe`, which mangles non-ASCII); Linux `wl-copy` if `$WAYLAND_DISPLAY` else `xclip/xsel -selection clipboard` if `$DISPLAY`, else hard-fail "no clipboard backend." Spawn a detached clearer (~10–20s); warn about macOS Universal Clipboard.
- **`.env` import grammar (v1, minimal):** `KEY=VALUE`, `#` comments, optional `export ` prefix, simple quote-strip; no interpolation/multiline.

---

## 11. Runtime & packaging (uv-only)

- **PEP-723** header on `kdbx.py`: `requires-python = ">=3.10"` (a **deliberate** floor for modern stdlib/typing, not an accidental over-spec). Consequence, accepted: on a box whose only interpreter is <3.10 (this one is 3.9.6), uv provisions a managed CPython on first run — see the network wording below. `dependencies = ["pykeepass>=4.1,<5", "python-dotenv", "filelock", "platformdirs"]`. The **`<5` pin is load-bearing** — a 5.x bump could silently break the keyfile/trash/perms/KDF behaviors this design leans on.
- **Lockfile:** commit `uv lock --script kdbx.py` (hashed) and invoke `uv run --locked` (both verified on uv 0.11.21) — supply-chain + version-behavior hardening.
- **uv hard-required, surfaced at the calling layer.** Because the script is *invoked* as `uv run …`, a missing `uv` fails at the shell before Python starts — so SKILL.md owns the uv preflight: probe `uv` on PATH and `~/.local/bin` / `%USERPROFILE%\.local\bin`, and if absent print the install one-liner (`curl -LsSf https://astral.sh/uv/install.sh | sh`) instead of running. Inside `kdbx.py`, a top-of-file guard catches missing-pykeepass / interpreter-too-old (exit 7) with a clean message naming both entrypoints — PEP-723 deps are read only from the **entry script**, so any dep used in a `kdbx_core/` submodule must also be declared in `kdbx.py`.
- **Network wording:** "no network **during operation**; one-time first-run provisioning, cached thereafter." On a fresh box the first run fetches **two** sources (a managed CPython from Astral since system Py is 3.9.6, plus wheels from PyPI). Run **`--offline` by default** so a cold cache fails loudly with a "run provisioning" message; document a CI cache-warm / vendored-wheelhouse path. This is provenance, not secret leakage.

---

## 12. Security model

- **Key-file-only unlock**, no master password. The keyfile is the sole secret; losing it makes the vault unrecoverable (loud warning). Keyfile + vault co-location is an accepted, documented tradeoff (matches `~/.ssh`, `~/.aws`).
- **0600** (POSIX) / restrictive ACL (Windows) on vault + keyfile + exported `.env`, re-applied after every save.
- **No telemetry, no network at run time** (see §11 wording).
- **Soft-delete is recoverable by design** — a compromised secret stays in the Recycle Bin until `--purge`; the leak runbook says rotate at source regardless.
- **Rotation:** `rekey` for the keyfile; the runbook covers a keyfile/vault leak.

---

## 13. Testing plan

- **Round-trip** in a temp dir, KDBX4/Argon2 + keyfile: `init → set(stdin) → get(mask+reveal) → list → check → export → run(child writes injected var to a file) → import → mv → delete → (verify in Recycle Bin) → --purge(verify gone) → rekey`.
- **Perms:** assert 0600 after **every** mutating op (`set`/`delete`/`import`/`mv`/`rekey`), not just `init`; exercise the `os.replace` path.
- **Secret-safety:** assert no value substring **and no leading-char prefix** in stdout/stderr for safe ops; **assert value never in argv**.
- **Field resolver matrix:** default `:password`, reserved fields, custom field, reserved-name collision, missing field errors.
- **Path-parser matrix:** `/`-in-name, `:`-in-name rejection, default field, unparseable → loud fail.
- **dotenv byte-identical:** PEM key + GCP service-account JSON + `$`-containing password through `set → export → import → get`.
- **Path resolution matrix:** monkeypatch `platform.system()` + env for macOS/Linux/Windows; assert Windows resolves under `%LOCALAPPDATA%`; sync-root guard fires.
- **Exit codes:** table below is asserted; `check` non-zero on drift; `run` propagates child code.
- **CLI interop (optional, skipped if `keepassxc-cli` absent):** pykeepass-written vault opens with `--no-password -k <keyfile>`.

---

## 14. Exit-code table (stable contract)

| Code | Meaning |
|---|---|
| 0 | success |
| 2 | entry/field/path not found |
| 3 | vault locked / keyfile missing / open failed |
| 4 | confirmation required (prod/`$KDBX_ENV`-inherited, or fallback-path without `--confirm-fallback`) |
| 5 | drift detected (`check`) / `--allow-missing` skipped something |
| 6 | vault changed underneath us (lost-update guard) |
| 7 | dependency/runtime preflight failed inside Python (pykeepass import / interpreter too old). uv-absence is surfaced earlier by the calling layer, not this code. |
| (run) | on success, the child's exit code; reserved distinct code for pre-exec secret-resolution failure |

---

## 15. SKILL.md contract

- **Lazy-loaded:** only `name` + one-line `description` in context until invoked.
- **Body kept lean:** when-to-use, the `uv run --locked <abs path>/kdbx.py …` invocation template (with `/path/to` clearly a placeholder the agent resolves from the skill dir; Windows form documented), a one-line-per-op table, and security do/don'ts (the §8 invariants). The full schema, CLI crib, and threat model live in `references/` (no verbatim duplication in the always-loaded body).

---

## 16. Acceptance criteria

- Fresh-box `uv run --locked kdbx.py init` produces a KDBX4/Argon2 vault + `.keyx` v2.0 keyfile, both 0600, readable by `keepassxc-cli --no-password -k`.
- `delete` is recoverable from the Recycle Bin; `--purge` is not; `list`/`get`/`check` never surface trashed entries.
- No secret value ever appears in argv, stdout, stderr, or the transcript across the full round-trip (asserted).
- Perms remain 0600 after every mutating op.
- `run` injects mapped vars and propagates the child exit code; `export` writes a 0600 gitignored dotenv; `import` round-trips a multiline PEM byte-identically.
- `check` exits non-zero on drift; prod/`$KDBX_ENV`-inherited ops refuse without `--yes`.
- All tests in §13 pass on macOS/Linux (Windows-specific paths unit-tested via monkeypatch; full Windows run is a follow-up if no Windows CI).

---

## 17. Open item

After ship: update `~/.claude/preferences/credentials.md` to point at this skill and reflect pykeepass-as-writer + the `vars` map (it currently documents the `keepassxc-cli` convention as source of truth and will drift). **User's call** — default yes; requires editing global prefs.

---

## 19. Licensing & distribution

**Decision: MIT for the skill's own source.** Verified (PyPI/GitHub LICENSE + FSF GPL FAQ; *not legal advice*):

- The `uv run` + PEP-723 design conveys **zero GPL bytes** — `pykeepass` (GPL-3.0) is referenced as a pinned coordinate and fetched from PyPI onto the end user's machine. A lockfile reference is not redistribution, so MIT on our code is honest.
- **GPL does not restrict commercial use.** Selling, SaaS, CI, internal/proprietary use, and runtime-install are all permitted. The only case the GPL default forecloses is **bundling the engine into a closed-source redistributable** (installer, vendored deps, an image baked with the engine, a shipped desktop app) — an in-process `import pykeepass` makes the combined work GPL-3.0.
- **No permissive Python KDBX4-writer exists** (verified). The clean permissive engine is `keepass-rs` (Rust, MIT), but its KDBX4 *write* is upstream-"experimental," has no maintained Python binding, and needs cross-platform wheel CI. Deferred (§2.7 seam makes it a cheap future swap); build it only if a real closed-source-bundling consumer appears.
- **`keepassxc-cli` subprocess** = clean "mere aggregation" firewall (separate GPL *program*, not linked) — already our read-only fallback (§2.1); not promoted to writer (would reopen the two-writer risk).

**`NOTICE` / README wording (ship verbatim):**

> The kdbx skill's own source is MIT. Its default writer engine, `pykeepass`, is GPL-3.0 and is fetched at runtime onto your machine — it is never bundled or redistributed by this project. You may use, sell, run as SaaS, run in CI, install at runtime, or shell out to keepassxc-cli freely. If you intend to ship a **closed-source product that bundles the engine**, the combined work inherits GPL-3.0 — in that case comply with GPL-3.0, use the keepassxc-cli read path, or swap in a permissive engine. *(Not legal advice.)*

**Repo hygiene (OSS-clean from commit #1):** standalone repo; `LICENSE` (MIT) + `NOTICE` + `SECURITY.md`; `.gitignore` excludes `*.kdbx`/`*.keyx`/`.env`; all example `.keepassxc.json`/README content uses generic project names and `${KEEPASSXC_DIR}` tokens — no personal paths or real vault references. Publish gate: works + passes its own security tests (§13/§16), then flip public.

## 18. Plan-readiness

With §6–§11 corrections folded in, the design is internally consistent and complete. **Ready for `writing-plans`** once approved. Suggested implementation sequencing (for the plan, not prescriptive): `paths`/`pointer` → `vault` engine (keyfile mint, save wrapper, trash, resolver) → `secretio`/`locking` → ops → `run`/`export`/`import` → SKILL.md + references → tests throughout (TDD).
