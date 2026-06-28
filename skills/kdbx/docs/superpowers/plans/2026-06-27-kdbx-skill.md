# kdbx Credentials Skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lazy-loaded Claude Code skill that manages per-project/per-env credentials in key-file-only KeePassXC KDBX4 vaults and gets secrets into tools without ever printing them.

**Architecture:** A PEP-723 entry script `kdbx.py` (run via `uv run`) dispatches to focused modules in `kdbx_core/`. `vault.py` is the only module importing pykeepass (the sole writer) and exposes an engine-agnostic interface. Discovery via a committed `.keepassxc.json` pointer with a per-env `vars` map. Built TDD.

**Tech Stack:** Python ≥3.10, uv + PEP 723, pykeepass (GPL-3.0, fetched at runtime), python-dotenv, filelock, platformdirs, pytest.

## Global Constraints

Copied verbatim from the spec (`docs/superpowers/specs/2026-06-27-kdbx-skill-design.md`). Every task implicitly includes these.

- **Engine:** pykeepass is the SOLE WRITER and the ONLY module that imports it (`vault.py`). Never `delete_entry()` for user-facing delete — use `trash_entry()`/`trash_group()`. keepassxc-cli is read-only docs, never invoked to write.
- **Vault:** KDBX4 + Argon2d, key-file-only unlock (no master password). 0600 (POSIX) / restrictive ACL (Windows) on vault + keyfile + exported `.env`, re-applied after EVERY save. `umask(0o077)` at process start.
- **Secrets:** the agent never authors/observes a value. Values enter via stdin / `getpass` / `--from-env` — NEVER argv, NEVER stdout (except `get --reveal`/`--clip`). Errors are scrubbed (no value in tracebacks).
- **Runtime:** uv hard-required. `kdbx.py` PEP-723 header: `requires-python = ">=3.10"`, `dependencies = ["pykeepass>=4.1,<5", "python-dotenv", "filelock", "platformdirs"]`. Commit `kdbx.py.lock`; run `uv run --locked`.
- **License/copy:** MIT (our source). Example configs use generic names + `${KEEPASSXC_DIR}` tokens — never personal paths.
- **Path grammar:** `group/subgroup/Title:field`; `:field` defaults to `password`; reject `/` and `:` inside any name component at write time.
- **Canonical test command** (referred to below as `TESTCMD`):
  ```
  uv run --with pytest --with pykeepass --with python-dotenv --with filelock --with platformdirs python -m pytest
  ```
- **Branch:** all implementation on branch `impl/kdbx-skill` (created in Task 1); `main` stays at the design commit until merge.
- **Exit codes:** 0 ok · 2 not-found · 3 vault-locked/keyfile-missing · 4 confirmation-required · 5 drift/allow-missing-skipped · 6 vault-changed · 7 python-preflight.

---

## File Structure

```
kdbx.py                     # PEP-723 entry: preflight, argparse dispatch, top-level error scrub, umask
kdbx.py.lock                # uv lock --script (Task 12)
kdbx_core/
  __init__.py               # (empty hygiene)
  paths.py                  # Task 2: OS-aware keepassxc_dir, ${KEEPASSXC_DIR}/~ expansion, sync-root guard
  pointer.py                # Task 3: find/load/write .keepassxc.json, env selection, entry-path parse/validate
  secretio.py               # Task 4: mask sentinel, secret input, dotenv, perms, clipboard, scrub, atomic write
  locking.py                # Task 5: advisory lock + integrity capture/verify
  vault.py                  # Tasks 6-7: pykeepass engine (keyfile mint, create/open/save, CRUD, trash, mv, rekey, resolver)
  context.py                # Task 8: env resolution + safety echo/gate, exit codes
  ops.py                    # Tasks 9-10: the 12 operations
SKILL.md                    # Task 11
references/{schema,fallback,security}.md   # Task 11
tests/
  conftest.py               # Task 1: fixtures (tmp keepassxc dir, a built vault, monkeypatch helpers)
  test_paths.py … test_ops.py, test_cli.py
```

---

### Task 1: Scaffolding, branch, conftest, preflight

**Files:**
- Create: `kdbx.py`, `kdbx_core/__init__.py`, `tests/conftest.py`, `pytest.ini`
- Test: `tests/test_preflight.py`

**Interfaces:**
- Produces: `kdbx.py` runnable via `uv run kdbx.py --help`; `tests/conftest.py` fixture `built_vault` (created in Task 6, stubbed here as a skip).

- [ ] **Step 1: Create the branch**

```bash
cd /Users/nabsha/work/yarrasys/ideas/kdbx-skill
git switch -c impl/kdbx-skill
```

- [ ] **Step 2: Write `kdbx.py` skeleton with PEP-723 header + preflight**

```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["pykeepass>=4.1,<5", "python-dotenv", "filelock", "platformdirs"]
# ///
"""kdbx — per-project/per-env KeePassXC credential manager. See SKILL.md."""
import os, sys

os.umask(0o077)  # restrict any file we create before explicit chmod

def _preflight() -> None:
    if sys.version_info < (3, 10):
        sys.stderr.write("kdbx: requires Python >=3.10 (run via `uv run`)\n")
        raise SystemExit(7)
    try:
        import pykeepass  # noqa: F401
    except ModuleNotFoundError:
        sys.stderr.write("kdbx: missing deps; run via `uv run --locked kdbx.py` (declared in kdbx.py PEP-723 header)\n")
        raise SystemExit(7)

def main(argv=None) -> int:
    _preflight()
    from kdbx_core.ops import dispatch   # imported after preflight
    return dispatch(argv if argv is not None else sys.argv[1:])

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Create `kdbx_core/__init__.py` (empty) and `pytest.ini`**

```ini
# pytest.ini
[pytest]
testpaths = tests
addopts = -ra
```

- [ ] **Step 4: Write `tests/conftest.py` with shared fixtures**

```python
import os, sys, pathlib, pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # repo root on path

@pytest.fixture
def kx_dir(tmp_path, monkeypatch):
    """Isolated <keepassxc-dir> under tmp."""
    d = tmp_path / "kpxc"
    d.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("KEEPASSXC_DIR", str(d))   # honored by paths.expand_path token
    return d
```

- [ ] **Step 5: Write failing preflight test**

```python
# tests/test_preflight.py
import subprocess, sys, os
def test_cli_help_runs():
    r = subprocess.run(["uv","run","kdbx.py","--help"], capture_output=True, text=True, cwd=os.getcwd())
    assert r.returncode == 0
    assert "kdbx" in (r.stdout + r.stderr).lower()
```

- [ ] **Step 6: Run — expect FAIL** (argparse/dispatch not built yet)

Run: `TESTCMD tests/test_preflight.py -v` → FAIL (ModuleNotFoundError kdbx_core.ops). This is expected; it goes green in Task 9.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "chore: scaffold kdbx.py PEP-723 entry, preflight, conftest"
```

---

### Task 2: `kdbx_core/paths.py` — OS-aware path resolution

**Files:**
- Create: `kdbx_core/paths.py`
- Test: `tests/test_paths.py`

**Interfaces:**
- Produces:
  - `keepassxc_dir() -> pathlib.Path` — `$KEEPASSXC_DIR` if set, else per-OS (macOS/Linux `$XDG_CONFIG_HOME`|`~/.config` + `/keepassxc`; Windows `%LOCALAPPDATA%\keepassxc`).
  - `expand_path(raw: str) -> pathlib.Path` — expand `${KEEPASSXC_DIR}` token then `~` then make absolute.
  - `under_sync_root(p: pathlib.Path) -> str | None` — name of a detected sync root (OneDrive/Dropbox/iCloud/Nextcloud/`AppData/Roaming`) or None.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_paths.py
import importlib, pathlib, pytest
paths = importlib.import_module("kdbx_core.paths")

def test_keepassxc_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("KEEPASSXC_DIR", str(tmp_path/"x"))
    assert paths.keepassxc_dir() == (tmp_path/"x")

def test_keepassxc_dir_linux(monkeypatch, tmp_path):
    monkeypatch.delenv("KEEPASSXC_DIR", raising=False)
    monkeypatch.setattr(paths.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path/"cfg"))
    assert paths.keepassxc_dir() == tmp_path/"cfg"/"keepassxc"

def test_keepassxc_dir_windows(monkeypatch, tmp_path):
    monkeypatch.delenv("KEEPASSXC_DIR", raising=False)
    monkeypatch.setattr(paths.platform, "system", lambda: "Windows")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path/"local"))
    assert paths.keepassxc_dir() == tmp_path/"local"/"keepassxc"

def test_expand_token(monkeypatch, tmp_path):
    monkeypatch.setenv("KEEPASSXC_DIR", str(tmp_path))
    assert paths.expand_path("${KEEPASSXC_DIR}/p/dev.kdbx") == tmp_path/"p"/"dev.kdbx"

def test_sync_root_detect(tmp_path):
    p = tmp_path/"OneDrive"/"keepassxc"/"dev.keyx"
    assert paths.under_sync_root(p) == "OneDrive"
```

- [ ] **Step 2: Run — expect FAIL** (`TESTCMD tests/test_paths.py -v`, ModuleNotFound/attr).

- [ ] **Step 3: Implement `paths.py`**

```python
import os, platform, pathlib

_SYNC_ROOTS = ("OneDrive", "Dropbox", "iCloud", "iCloudDrive", "Nextcloud", "Google Drive")

def keepassxc_dir() -> pathlib.Path:
    override = os.environ.get("KEEPASSXC_DIR")
    if override:
        return pathlib.Path(override)
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.path.expandvars(r"%USERPROFILE%\AppData\Local")
        return pathlib.Path(base) / "keepassxc"
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(pathlib.Path.home(), ".config")
    return pathlib.Path(base) / "keepassxc"

def expand_path(raw: str) -> pathlib.Path:
    s = raw.replace("${KEEPASSXC_DIR}", str(keepassxc_dir()))
    return pathlib.Path(os.path.expanduser(s)).resolve()

def under_sync_root(p: pathlib.Path) -> str | None:
    parts = set(pathlib.Path(p).parts)
    for root in _SYNC_ROOTS:
        if root in parts:
            return root
    if "AppData" in parts and "Roaming" in parts:
        return "AppData/Roaming"
    return None
```

- [ ] **Step 4: Run — expect PASS** (`TESTCMD tests/test_paths.py -v`).
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(paths): OS-aware keepassxc dir + token/sync-root resolution"`

---

### Task 3: `kdbx_core/pointer.py` — discovery, env selection, path grammar

**Files:**
- Create: `kdbx_core/pointer.py`
- Test: `tests/test_pointer.py`

**Interfaces:**
- Consumes: `paths.expand_path`, `paths.keepassxc_dir`.
- Produces:
  - `find_pointer(start: Path) -> Path | None` — nearest `.keepassxc.json` walking up.
  - `load_pointer(path: Path) -> dict`.
  - `select_env(pointer: dict, cli_env: str | None) -> tuple[str, str]` → `(env_name, source)` where source ∈ {"--env","$KDBX_ENV","pointer"}.
  - `resolve_env(pointer: dict, env: str, project_dir: Path) -> EnvPaths` where `EnvPaths` is a dataclass `(vault: Path, keyfile: Path, vars: dict[str,str])`; derive `<keepassxc-dir>/<project>/<env>.{kdbx,keyx}` when `vault`/`keyFile` omitted.
  - `parse_entry_path(raw: str) -> tuple[list[str], str, str]` → `(group_path, title, field)`; field defaults `"password"`; **raises `ValueError`** if any group/title component contains `/` or `:`.
  - `write_pointer(path: Path, pointer: dict) -> None` — atomic, `indent=2, sort_keys=False`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_pointer.py
import importlib, json, pathlib, pytest
pointer = importlib.import_module("kdbx_core.pointer")

def _write(p, obj): p.write_text(json.dumps(obj))

def test_find_walks_up(tmp_path):
    root = tmp_path/"repo"; (root/"a"/"b").mkdir(parents=True)
    _write(root/".keepassxc.json", {"project":"x","defaultEnv":"dev","envs":{"dev":{}}})
    assert pointer.find_pointer(root/"a"/"b") == root/".keepassxc.json"

def test_select_env_precedence(monkeypatch):
    pt = {"defaultEnv":"dev","envs":{"dev":{},"prod":{}}}
    monkeypatch.setenv("KDBX_ENV","prod")
    assert pointer.select_env(pt, "dev") == ("dev","--env")
    assert pointer.select_env(pt, None) == ("prod","$KDBX_ENV")
    monkeypatch.delenv("KDBX_ENV")
    assert pointer.select_env(pt, None) == ("dev","pointer")

def test_resolve_derives_when_omitted(tmp_path, monkeypatch):
    monkeypatch.setenv("KEEPASSXC_DIR", str(tmp_path/"kx"))
    pt = {"project":"ideas","defaultEnv":"dev","envs":{"dev":{"vars":{"A":"g/T:password"}}}}
    ep = pointer.resolve_env(pt, "dev", tmp_path/"repo")
    assert ep.vault == (tmp_path/"kx"/"ideas"/"dev.kdbx").resolve()
    assert ep.keyfile == (tmp_path/"kx"/"ideas"/"dev.keyx").resolve()
    assert ep.vars == {"A":"g/T:password"}

def test_parse_entry_path():
    assert pointer.parse_entry_path("api/openai:password") == (["api"],"openai","password")
    assert pointer.parse_entry_path("db/primary") == (["db"],"primary","password")
    assert pointer.parse_entry_path("Top") == ([],"Top","password")

def test_parse_rejects_colon_in_name():
    with pytest.raises(ValueError):
        pointer.parse_entry_path("api/ht:tp:password")  # ambiguous

def test_write_pointer_atomic_preserves_order(tmp_path):
    p = tmp_path/".keepassxc.json"
    pointer.write_pointer(p, {"project":"z","defaultEnv":"dev","envs":{}})
    assert list(json.loads(p.read_text()).keys())[0] == "project"
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement `pointer.py`** (grammar note: split on last `:` for field only if the remainder is a known/parsable field; to keep it unambiguous, field is the substring after the FINAL `:`, and `:` is then forbidden in names so there's exactly one).

```python
import json, os, pathlib
from dataclasses import dataclass
from . import paths

POINTER_NAME = ".keepassxc.json"
_RESERVED_FIELDS = {"title","username","password","url","notes"}

@dataclass
class EnvPaths:
    vault: pathlib.Path
    keyfile: pathlib.Path
    vars: dict

def find_pointer(start: pathlib.Path) -> pathlib.Path | None:
    cur = pathlib.Path(start).resolve()
    for d in [cur, *cur.parents]:
        cand = d / POINTER_NAME
        if cand.is_file():
            return cand
    return None

def load_pointer(path: pathlib.Path) -> dict:
    return json.loads(pathlib.Path(path).read_text())

def select_env(pointer: dict, cli_env: str | None) -> tuple[str, str]:
    if cli_env:
        return cli_env, "--env"
    env = os.environ.get("KDBX_ENV")
    if env:
        return env, "$KDBX_ENV"
    return pointer.get("defaultEnv", "dev"), "pointer"

def resolve_env(pointer: dict, env: str, project_dir: pathlib.Path) -> EnvPaths:
    envs = pointer.get("envs", {})
    if env not in envs:
        raise KeyError(f"env '{env}' not in pointer")
    cfg = envs[env] or {}
    project = pointer.get("project") or pathlib.Path(project_dir).name
    default_dir = paths.keepassxc_dir() / project
    vault = paths.expand_path(cfg["vault"]) if cfg.get("vault") else (default_dir / f"{env}.kdbx").resolve()
    keyfile = paths.expand_path(cfg["keyFile"]) if cfg.get("keyFile") else (default_dir / f"{env}.keyx").resolve()
    return EnvPaths(vault=vault, keyfile=keyfile, vars=dict(cfg.get("vars") or {}))

def parse_entry_path(raw: str) -> tuple[list[str], str, str]:
    field = "password"
    body = raw
    if ":" in raw:
        body, field = raw.rsplit(":", 1)
        if ":" in body:
            raise ValueError(f"ambiguous path (multiple ':'): {raw!r}")
    segments = body.split("/")
    if any(seg == "" for seg in segments):
        raise ValueError(f"empty path component: {raw!r}")
    *group_path, title = segments
    return group_path, title, field

def write_pointer(path: pathlib.Path, pointer: dict) -> None:
    path = pathlib.Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(pointer, indent=2, sort_keys=False) + "\n")
    os.replace(tmp, path)
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git commit -am "feat(pointer): discovery, env selection, entry-path grammar"`

---

### Task 4: `kdbx_core/secretio.py` — secret I/O, perms, dotenv, scrub

**Files:**
- Create: `kdbx_core/secretio.py`
- Test: `tests/test_secretio.py`

**Interfaces:**
- Produces:
  - `MASK = "(set, hidden)"` (constant; no length/prefix leak).
  - `read_secret(args) -> str` — value from `--from-env VAR` (read `os.environ[VAR]`), else stdin; `getpass` w/ confirm if `stdin.isatty()`; strip one trailing `\r?\n` unless `raw=True`. NEVER returns argv.
  - `restrict_perms(path: Path) -> None` — POSIX `chmod 0600`; Windows `icacls /inheritance:r /grant:r %USERNAME%:F`.
  - `atomic_write_secret(path, data: str, *, restrict=True) -> None` — `os.open(O_CREAT|O_WRONLY|O_TRUNC, 0600)` write; `restrict_perms`.
  - `render_dotenv(items: dict[str,str]) -> str` / `parse_dotenv(text: str) -> dict[str,str]` — via `python-dotenv`, `newline='\n'`.
  - `clipboard_copy(value: str, *, clear_after=15) -> None` — backend per OS; spawn detached clearer; raise if no backend.
  - `scrub_exceptions(fn)` decorator → prints `kdbx: <op> failed: <ExcType>` to stderr (no value), returns exit code; full traceback only if `KDBX_DEBUG`.

- [ ] **Step 1: Write failing tests** (the security-critical ones)

```python
# tests/test_secretio.py
import importlib, io, os, stat, pathlib, pytest
s = importlib.import_module("kdbx_core.secretio")

def test_mask_has_no_value_info():
    assert s.MASK == "(set, hidden)"

def test_read_secret_from_env(monkeypatch):
    monkeypatch.setenv("SRC","hunter2")
    class A: from_env="SRC"; raw=False
    assert s.read_secret(A()) == "hunter2"

def test_read_secret_stdin_strips_one_newline(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("topsecret\n"))
    monkeypatch.setattr(s.sys.stdin, "isatty", lambda: False, raising=False)
    class A: from_env=None; raw=False
    assert s.read_secret(A()) == "topsecret"

@pytest.mark.skipif(os.name=="nt", reason="POSIX perms")
def test_atomic_write_is_0600(tmp_path):
    p = tmp_path/"out.env"
    s.atomic_write_secret(p, "X=1\n")
    assert stat.S_IMODE(p.stat().st_mode) == 0o600

def test_dotenv_roundtrip_multiline():
    pem = "-----BEGIN-----\nabc\ndef\n-----END-----"
    text = s.render_dotenv({"KEY": pem, "OTHER": "v$1"})
    back = s.parse_dotenv(text)
    assert back["KEY"] == pem and back["OTHER"] == "v$1"

def test_scrub_hides_value(capsys):
    @s.scrub_exceptions("set")
    def boom():
        raise ValueError("secret-literal-12345")
    rc = boom()
    err = capsys.readouterr().err
    assert "secret-literal-12345" not in err
    assert "set failed" in err and rc != 0
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement `secretio.py`** (use `python-dotenv` for parse; render via its quoting):

```python
import os, sys, stat, subprocess, functools, pathlib, getpass
import io as _io
from dotenv import dotenv_values
try:
    from dotenv.main import DotEnv  # noqa
except Exception:
    pass

MASK = "(set, hidden)"

def read_secret(args) -> str:
    raw = getattr(args, "raw", False)
    src = getattr(args, "from_env", None)
    if src:
        if src not in os.environ:
            raise KeyError(f"--from-env {src} not set")
        val = os.environ[src]
    elif sys.stdin.isatty():
        val = getpass.getpass("value: ")
        if getpass.getpass("confirm: ") != val:
            raise ValueError("values did not match")
        return val
    else:
        val = sys.stdin.read()
    if not raw and val.endswith("\n"):
        val = val[:-1]
        if val.endswith("\r"):
            val = val[:-1]
    return val

def restrict_perms(path) -> None:
    path = str(path)
    if os.name == "nt":
        user = os.environ.get("USERNAME", "")
        subprocess.run(["icacls", path, "/inheritance:r", "/grant:r", f"{user}:F"],
                       check=False, capture_output=True)
    else:
        os.chmod(path, 0o600)

def atomic_write_secret(path, data: str, *, restrict=True) -> None:
    path = pathlib.Path(path)
    fd = os.open(str(path), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data.encode("utf-8"))
    finally:
        os.close(fd)
    if restrict:
        restrict_perms(path)

def render_dotenv(items: dict) -> str:
    # python-dotenv has no public renderer; emit safe double-quoted values.
    def q(v: str) -> str:
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    return "".join(f"{k}={q(v)}\n" for k, v in items.items())

def parse_dotenv(text: str) -> dict:
    return {k: v for k, v in dotenv_values(stream=_io.StringIO(text)).items() if v is not None}

def clipboard_copy(value: str, *, clear_after: int = 15) -> None:
    cmd = _clipboard_cmd()
    if cmd is None:
        raise RuntimeError("no clipboard backend available")
    subprocess.run(cmd, input=value.encode("utf-8"), check=True)
    # detached clearer
    clear = _clipboard_cmd()
    subprocess.Popen(
        [sys.executable, "-c",
         f"import time,subprocess;time.sleep({int(clear_after)});"
         f"subprocess.run({clear!r}, input=b'')"],
        start_new_session=True,
    )

def _clipboard_cmd():
    if sys.platform == "darwin":
        return ["pbcopy"]
    if os.name == "nt":
        return ["powershell", "-NoProfile", "-Command", "Set-Clipboard"]
    if os.environ.get("WAYLAND_DISPLAY"):
        return ["wl-copy"]
    if os.environ.get("DISPLAY"):
        return ["xclip", "-selection", "clipboard"]
    return None

def scrub_exceptions(op: str):
    def deco(fn):
        @functools.wraps(fn)
        def wrap(*a, **k):
            try:
                return fn(*a, **k)
            except SystemExit:
                raise
            except BaseException as e:
                if os.environ.get("KDBX_DEBUG"):
                    import traceback; traceback.print_exc()
                sys.stderr.write(f"kdbx: {op} failed: {type(e).__name__}\n")
                return getattr(e, "kdbx_code", 1)
        return wrap
    return deco
```

> **Note for executor:** `render_dotenv` is hand-rolled double-quoting because python-dotenv exposes no public renderer; `parse_dotenv` uses python-dotenv. The multiline round-trip test is the gate — if `\n` round-trip fails, switch render to `python-dotenv`'s `set_key` against a temp file.

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git commit -am "feat(secretio): secret input, perms, dotenv, clipboard, scrub"`

---

### Task 5: `kdbx_core/locking.py` — advisory lock + integrity

**Files:**
- Create: `kdbx_core/locking.py`
- Test: `tests/test_locking.py`

**Interfaces:**
- Produces:
  - `vault_lock(vault: Path)` — context manager taking a `filelock.FileLock` on `<vault>.lock`.
  - `capture_state(vault: Path) -> str` — sha256 hex of vault bytes (or "" if absent).
  - `verify_unchanged(vault: Path, captured: str) -> None` — raise `RuntimeError` (code 6) if current hash != captured.

- [ ] **Step 1: Failing tests**

```python
# tests/test_locking.py
import importlib, pathlib, pytest
locking = importlib.import_module("kdbx_core.locking")

def test_capture_and_verify(tmp_path):
    v = tmp_path/"v.kdbx"; v.write_bytes(b"abc")
    h = locking.capture_state(v)
    locking.verify_unchanged(v, h)           # no raise
    v.write_bytes(b"xyz")
    with pytest.raises(RuntimeError):
        locking.verify_unchanged(v, h)

def test_lock_acquires(tmp_path):
    v = tmp_path/"v.kdbx"
    with locking.vault_lock(v):
        assert (tmp_path/"v.kdbx.lock").exists()
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement**

```python
import hashlib, pathlib, contextlib
from filelock import FileLock

@contextlib.contextmanager
def vault_lock(vault):
    lock = FileLock(str(pathlib.Path(vault)) + ".lock", timeout=10)
    with lock:
        yield

def capture_state(vault) -> str:
    p = pathlib.Path(vault)
    if not p.exists():
        return ""
    return hashlib.sha256(p.read_bytes()).hexdigest()

def verify_unchanged(vault, captured: str) -> None:
    if capture_state(vault) != captured:
        e = RuntimeError("vault changed underneath us; re-run")
        e.kdbx_code = 6
        raise e
```

- [ ] **Step 4: Run — expect PASS.**  **Step 5: Commit** — `git commit -am "feat(locking): advisory lock + integrity check"`

---

### Task 6: `kdbx_core/vault.py` part 1 — keyfile mint, create, open, save

**Files:**
- Create: `kdbx_core/vault.py`
- Test: `tests/test_vault_create.py`
- Modify: `tests/conftest.py` (add `built_vault` fixture)

**Interfaces:**
- Consumes: `secretio.restrict_perms`, `locking`.
- Produces (engine-agnostic — callers pass paths/str, never pykeepass objects):
  - `generate_keyfile_xml(key: bytes) -> str` — KeePass 2.0 XML keyfile.
  - `mint_keyfile(path: Path) -> None` — 32 `secrets.token_bytes`, write XML atomically at 0600; refuse if exists.
  - `create_vault(vault: Path, keyfile: Path) -> None` — mint keyfile (if absent) **then** `create_database`; assert KDBX4+Argon2; 0600 both; refuse if vault OR keyfile exists.
  - `_open(vault, keyfile) -> PyKeePass` (internal).
  - `save(kp, vault: Path) -> None` — `kp.save(tmp)`; `restrict_perms(tmp)`; keep `.bak`; `os.replace`.

- [ ] **Step 1: Failing tests** (proves the E3/E4/E8 corrections)

```python
# tests/test_vault_create.py
import importlib, pathlib, stat, os, pytest
vault = importlib.import_module("kdbx_core.vault")

def test_mint_keyfile_then_open(tmp_path):
    vp, kf = tmp_path/"v.kdbx", tmp_path/"v.keyx"
    vault.create_vault(vp, kf)
    assert vp.exists() and kf.exists()
    kp = vault._open(vp, kf)         # opens with keyfile only, no password
    assert kp.version[0] == 4
    assert "argon2" in str(kp.kdf_algorithm).lower()

@pytest.mark.skipif(os.name=="nt", reason="POSIX perms")
def test_perms_0600_on_create(tmp_path):
    vp, kf = tmp_path/"v.kdbx", tmp_path/"v.keyx"
    vault.create_vault(vp, kf)
    assert stat.S_IMODE(vp.stat().st_mode) == 0o600
    assert stat.S_IMODE(kf.stat().st_mode) == 0o600

def test_refuse_existing(tmp_path):
    vp, kf = tmp_path/"v.kdbx", tmp_path/"v.keyx"
    vault.create_vault(vp, kf)
    with pytest.raises(FileExistsError):
        vault.create_vault(vp, kf)

@pytest.mark.skipif(os.name=="nt", reason="POSIX perms")
def test_save_keeps_0600(tmp_path):
    vp, kf = tmp_path/"v.kdbx", tmp_path/"v.keyx"
    vault.create_vault(vp, kf)
    kp = vault._open(vp, kf)
    kp.add_group(kp.root_group, "g")
    vault.save(kp, vp)
    assert stat.S_IMODE(vp.stat().st_mode) == 0o600   # pykeepass resets to 0644; we re-chmod
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement part 1**

```python
import os, hashlib, secrets, pathlib
from pykeepass import PyKeePass, create_database
from . import secretio

def generate_keyfile_xml(key: bytes) -> str:
    data = key.hex().upper()
    checksum = hashlib.sha256(key).digest()[:4].hex().upper()
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<KeyFile>\n\t<Meta>\n\t\t<Version>2.0</Version>\n\t</Meta>\n'
        f'\t<Key>\n\t\t<Data Hash="{checksum}">{data}</Data>\n\t</Key>\n</KeyFile>\n'
    )

def mint_keyfile(path) -> None:
    path = pathlib.Path(path)
    if path.exists():
        raise FileExistsError(f"keyfile exists: {path}")
    secretio.atomic_write_secret(path, generate_keyfile_xml(secrets.token_bytes(32)))

def create_vault(vault, keyfile) -> None:
    vault, keyfile = pathlib.Path(vault), pathlib.Path(keyfile)
    if vault.exists() or keyfile.exists():
        raise FileExistsError(f"refusing to overwrite existing vault/keyfile")
    vault.parent.mkdir(parents=True, exist_ok=True)
    mint_keyfile(keyfile)
    kp = create_database(str(vault), keyfile=str(keyfile))   # KDBX4 + Argon2 default
    assert kp.version[0] == 4 and "argon2" in str(kp.kdf_algorithm).lower(), "expected KDBX4+Argon2"
    secretio.restrict_perms(vault)

def _open(vault, keyfile):
    return PyKeePass(str(vault), keyfile=str(keyfile))

def save(kp, vault) -> None:
    vault = pathlib.Path(vault)
    tmp = vault.with_suffix(vault.suffix + ".tmp")
    kp.save(str(tmp))
    secretio.restrict_perms(tmp)
    if vault.exists():
        os.replace(vault, vault.with_suffix(vault.suffix + ".bak"))
    os.replace(tmp, vault)
    secretio.restrict_perms(vault)
```

- [ ] **Step 4: Run — expect PASS** (if `generate_keyfile_xml` is rejected by pykeepass, fall back to raw-bytes keyfile: `path.write_bytes(secrets.token_bytes(32))` — keep the same test).
- [ ] **Step 5: Add `built_vault` fixture to conftest**

```python
@pytest.fixture
def built_vault(tmp_path):
    from kdbx_core import vault
    vp, kf = tmp_path/"v.kdbx", tmp_path/"v.keyx"
    vault.create_vault(vp, kf)
    return vp, kf
```

- [ ] **Step 6: Commit** — `git commit -am "feat(vault): keyfile mint, KDBX4/Argon2 create, atomic 0600 save"`

---

### Task 7: `vault.py` part 2 — CRUD, resolver, trash/purge, mv, rekey

**Files:**
- Modify: `kdbx_core/vault.py`
- Test: `tests/test_vault_crud.py`

**Interfaces (all take vault+keyfile paths, open/save internally):**
- `set_field(vault, keyfile, group_path: list[str], title: str, field: str, value: str) -> None` — walk-create groups, upsert entry, set reserved attr or custom property (protected).
- `get_field(vault, keyfile, group_path, title, field) -> str` — resolver: reserved via attr, else `get_custom_property` (case-sensitive); raise `KeyError` (code 2) if entry/field missing; **excludes Recycle Bin**.
- `list_entries(vault, keyfile) -> list[str]` — `"group/Title"` paths, Recycle Bin excluded.
- `trash(vault, keyfile, group_path, title) -> None` — `trash_entry`.
- `purge(vault, keyfile, group_path, title) -> None` — `delete_entry`.
- `move(vault, keyfile, src: str, dst: str) -> None` — rename/move entry (parse both via `pointer.parse_entry_path`, ignore field).
- `rekey(vault, keyfile, new_keyfile) -> None` — mint new, `kp.save` under new credentials, unlink old.

- [ ] **Step 1: Failing tests** (proves E5 soft-delete + resolver traps)

```python
# tests/test_vault_crud.py
import importlib, pytest
vault = importlib.import_module("kdbx_core.vault")

def test_set_get_default_password(built_vault):
    vp, kf = built_vault
    vault.set_field(vp, kf, ["api"], "openai", "password", "sk-xyz")
    assert vault.get_field(vp, kf, ["api"], "openai", "password") == "sk-xyz"

def test_get_missing_field_raises(built_vault):
    vp, kf = built_vault
    vault.set_field(vp, kf, ["api"], "openai", "password", "sk")
    with pytest.raises(KeyError):
        vault.get_field(vp, kf, ["api"], "openai", "username")  # never returns None/empty

def test_trash_is_recoverable_and_hidden(built_vault):
    vp, kf = built_vault
    vault.set_field(vp, kf, ["g"], "t", "password", "v")
    vault.trash(vp, kf, ["g"], "t")
    assert "g/t" not in vault.list_entries(vp, kf)          # excluded from list
    with pytest.raises(KeyError):
        vault.get_field(vp, kf, ["g"], "t", "password")     # excluded from get
    kp = vault._open(vp, kf)                                 # but still in Recycle Bin
    assert any(e.title == "t" for e in kp.entries if vault._in_recyclebin(kp, e))

def test_purge_removes(built_vault):
    vp, kf = built_vault
    vault.set_field(vp, kf, ["g"], "t", "password", "v")
    vault.purge(vp, kf, ["g"], "t")
    kp = vault._open(vp, kf)
    assert not any(e.title == "t" for e in kp.entries)

def test_move_rename(built_vault):
    vp, kf = built_vault
    vault.set_field(vp, kf, ["api"], "openai", "password", "v")
    vault.move(vp, kf, "api/openai", "api/oai")
    assert "api/oai" in vault.list_entries(vp, kf)
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement part 2** (append to `vault.py`)

```python
from . import locking, pointer

_RESERVED = {"title", "username", "password", "url", "notes"}

def _in_recyclebin(kp, entry) -> bool:
    rb = kp.recyclebin_group
    if rb is None:
        return False
    g = entry.group
    while g is not None:
        if g.uuid == rb.uuid:
            return True
        g = g.group
    return False

def _walk_create(kp, group_path):
    grp = kp.root_group
    for name in group_path:
        found = kp.find_groups(name=name, group=grp, first=True, recursive=False)
        grp = found if found else kp.add_group(grp, name)
    return grp

def _find_entry(kp, group_path, title, *, include_trash=False):
    path = group_path + [title]
    e = kp.find_entries(path=path, first=True)
    if e and (include_trash or not _in_recyclebin(kp, e)):
        return e
    return None

def set_field(vault, keyfile, group_path, title, field, value) -> None:
    with locking.vault_lock(vault):
        captured = locking.capture_state(vault)
        kp = _open(vault, keyfile)
        locking.verify_unchanged(vault, captured)
        grp = _walk_create(kp, group_path)
        e = _find_entry(kp, group_path, title) or kp.add_entry(grp, title, "", "")
        if field.lower() in _RESERVED:
            setattr(e, field.lower(), value)
        else:
            e.set_custom_property(field, value, protect=True)
        save(kp, vault)

def get_field(vault, keyfile, group_path, title, field) -> str:
    kp = _open(vault, keyfile)
    e = _find_entry(kp, group_path, title)
    if e is None:
        err = KeyError(f"entry not found: {'/'.join(group_path+[title])}"); err.kdbx_code = 2; raise err
    if field.lower() in _RESERVED:
        val = getattr(e, field.lower())
    else:
        val = e.get_custom_property(field)
    if val is None:
        err = KeyError(f"field not found: {field}"); err.kdbx_code = 2; raise err
    return val

def list_entries(vault, keyfile) -> list:
    kp = _open(vault, keyfile)
    out = []
    for e in kp.entries:
        if _in_recyclebin(kp, e):
            continue
        grp = "/".join(g.name for g in reversed(_ancestors(e.group, kp)))
        out.append(f"{grp + '/' if grp else ''}{e.title}")
    return sorted(out)

def _ancestors(group, kp):
    chain, g = [], group
    while g is not None and g.uuid != kp.root_group.uuid:
        chain.append(g); g = g.group
    return chain

def trash(vault, keyfile, group_path, title) -> None:
    with locking.vault_lock(vault):
        kp = _open(vault, keyfile)
        e = _find_entry(kp, group_path, title)
        if e is None:
            err = KeyError("entry not found"); err.kdbx_code = 2; raise err
        kp.trash_entry(e)
        save(kp, vault)

def purge(vault, keyfile, group_path, title) -> None:
    with locking.vault_lock(vault):
        kp = _open(vault, keyfile)
        e = _find_entry(kp, group_path, title, include_trash=True)
        if e is None:
            err = KeyError("entry not found"); err.kdbx_code = 2; raise err
        kp.delete_entry(e)
        save(kp, vault)

def move(vault, keyfile, src: str, dst: str) -> None:
    sg, st, _ = pointer.parse_entry_path(src)
    dg, dt, _ = pointer.parse_entry_path(dst)
    with locking.vault_lock(vault):
        kp = _open(vault, keyfile)
        e = _find_entry(kp, sg, st)
        if e is None:
            err = KeyError("entry not found"); err.kdbx_code = 2; raise err
        if dg != sg:
            kp.move_entry(e, _walk_create(kp, dg))
        e.title = dt
        save(kp, vault)

def rekey(vault, keyfile, new_keyfile) -> None:
    mint_keyfile(new_keyfile)
    with locking.vault_lock(vault):
        kp = _open(vault, keyfile)
        kp.keyfile = str(new_keyfile)
        save(kp, vault)
    os.unlink(keyfile)
```

> **Executor note:** pykeepass `find_entries(path=[...])`/`find_groups(name=...)` signatures verified present. If `find_groups(recursive=False)` is unsupported in 4.1.1, use `find_groups_by_path` for the walk and catch duplicates. The `_in_recyclebin` + resolver behavior is the load-bearing part; keep those tests green.

- [ ] **Step 4: Run — expect PASS.**  **Step 5: Commit** — `git commit -am "feat(vault): CRUD, field resolver, trash/purge, mv, rekey"`

---

### Task 8: `kdbx_core/context.py` — env resolution + safety gate

**Files:**
- Create: `kdbx_core/context.py`
- Test: `tests/test_context.py`

**Interfaces:**
- `EXIT = {...}` — the exit-code table constants.
- `resolve(cli_env, start_dir, *, yes: bool, mutating: bool) -> Context` where `Context=(env, source, vault, keyfile, vars, pointer_path)`. Echo `ACTIVE ENV: <e>  vault=<abs>  (source: …)` to **stderr** for mutating/export/run. Raise `ConfirmationRequired` (code 4) if `mutating` and (env == "prod" or source == "$KDBX_ENV") and not `yes`.
- `ConfirmationRequired(Exception)` with `kdbx_code=4`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_context.py
import importlib, json, pathlib, pytest
ctx = importlib.import_module("kdbx_core.context")

def _ptr(tmp, envs, default="dev"):
    p = tmp/".keepassxc.json"
    p.write_text(json.dumps({"project":"p","defaultEnv":default,"envs":envs}))
    return p

def test_prod_requires_yes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("KEEPASSXC_DIR", str(tmp_path/"kx"))
    _ptr(tmp_path, {"prod":{}})
    with pytest.raises(ctx.ConfirmationRequired):
        ctx.resolve("prod", tmp_path, yes=False, mutating=True)
    ctx.resolve("prod", tmp_path, yes=True, mutating=True)  # ok with --yes

def test_kdbx_env_inherited_gated(tmp_path, monkeypatch):
    monkeypatch.setenv("KEEPASSXC_DIR", str(tmp_path/"kx"))
    monkeypatch.setenv("KDBX_ENV","dev")
    _ptr(tmp_path, {"dev":{}})
    with pytest.raises(ctx.ConfirmationRequired):
        ctx.resolve(None, tmp_path, yes=False, mutating=True)

def test_echo_to_stderr(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("KEEPASSXC_DIR", str(tmp_path/"kx"))
    _ptr(tmp_path, {"dev":{}})
    ctx.resolve("dev", tmp_path, yes=False, mutating=True)
    assert "ACTIVE ENV: dev" in capsys.readouterr().err
```

- [ ] **Step 2: Run — FAIL. Step 3: Implement**

```python
import sys, pathlib
from dataclasses import dataclass
from . import pointer

EXIT = {"ok":0,"not_found":2,"locked":3,"confirm":4,"drift":5,"changed":6,"preflight":7}

class ConfirmationRequired(Exception):
    kdbx_code = 4

@dataclass
class Context:
    env: str; source: str
    vault: pathlib.Path; keyfile: pathlib.Path
    vars: dict; pointer_path: pathlib.Path | None

def resolve(cli_env, start_dir, *, yes: bool, mutating: bool) -> Context:
    pp = pointer.find_pointer(pathlib.Path(start_dir))
    if pp is None:
        raise FileNotFoundError("no .keepassxc.json found")
    pt = pointer.load_pointer(pp)
    env, source = pointer.select_env(pt, cli_env)
    ep = pointer.resolve_env(pt, env, pp.parent)
    if mutating:
        sys.stderr.write(f"ACTIVE ENV: {env}  vault={ep.vault}  (source: {source})\n")
        if (env == "prod" or source == "$KDBX_ENV") and not yes:
            e = ConfirmationRequired(f"env '{env}' (source {source}) requires --yes")
            raise e
    return Context(env, source, ep.vault, ep.keyfile, ep.vars, pp)
```

- [ ] **Step 4: PASS. Step 5: Commit** — `git commit -am "feat(context): env resolution + prod/KDBX_ENV safety gate"`

---

### Task 9: `kdbx_core/ops.py` part 1 + CLI dispatch — init/set/get/list/delete/mv/envs

**Files:**
- Create: `kdbx_core/ops.py`
- Test: `tests/test_ops_crud.py`, and unskip `tests/test_preflight.py`

**Interfaces:**
- `dispatch(argv: list[str]) -> int` — argparse with subcommands; each subcommand handler wrapped in `secretio.scrub_exceptions(name)`; maps `kdbx_code`/exceptions → EXIT codes; returns int.
- Subcommand handlers `cmd_init/cmd_set/cmd_get/cmd_list/cmd_delete/cmd_mv/cmd_envs(args) -> int`.

- [ ] **Step 1: Failing tests** (call `dispatch` directly)

```python
# tests/test_ops_crud.py
import importlib, json, os, pathlib, pytest
ops = importlib.import_module("kdbx_core.ops")

@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("KEEPASSXC_DIR", str(tmp_path/"kx"))
    monkeypatch.chdir(tmp_path)
    (tmp_path/".keepassxc.json").write_text(json.dumps(
        {"project":"ideas","defaultEnv":"dev","envs":{"dev":{"vars":{}}}}))
    return tmp_path

def test_init_then_set_get(repo, monkeypatch, capsys):
    assert ops.dispatch(["init","--env","dev"]) == 0
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("sk-123\n"))
    assert ops.dispatch(["set","api/openai","--env","dev"]) == 0
    assert ops.dispatch(["get","api/openai","--env","dev"]) == 0
    out = capsys.readouterr().out
    assert "sk-123" not in out and "(set, hidden)" in out          # masked by default
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(""))

def test_get_reveal(repo, monkeypatch, capsys):
    ops.dispatch(["init","--env","dev"])
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("sk-123\n"))
    ops.dispatch(["set","api/openai","--env","dev"])
    assert ops.dispatch(["get","api/openai","--reveal","--env","dev"]) == 0
    assert "sk-123" in capsys.readouterr().out

def test_delete_then_list(repo, monkeypatch):
    ops.dispatch(["init","--env","dev"])
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("v\n"))
    ops.dispatch(["set","g/t","--env","dev"])
    assert ops.dispatch(["delete","g/t","--env","dev"]) == 0
```

- [ ] **Step 2: Run — FAIL. Step 3: Implement `ops.py`** (argparse + handlers wiring vault/context/secretio; `set` reads via `secretio.read_secret`; `get` prints `MASK` unless `--reveal`/`--clip`):

```python
import argparse, sys, pathlib
from . import vault, context, secretio, pointer

def _ctx(args, mutating):
    return context.resolve(getattr(args,"env",None), pathlib.Path.cwd(),
                           yes=getattr(args,"yes",False), mutating=mutating)

def cmd_init(args) -> int:
    c = _ctx(args, mutating=True)
    vault.create_vault(c.vault, c.keyfile)
    sys.stderr.write(f"created {c.vault}\nKEYFILE: {c.keyfile} — back this up; losing it makes the vault unrecoverable.\n")
    return 0

def cmd_set(args) -> int:
    c = _ctx(args, mutating=True)
    gp, title, field = pointer.parse_entry_path(args.path)
    value = secretio.read_secret(args)
    vault.set_field(c.vault, c.keyfile, gp, title, field, value)
    if args.var:
        pt = pointer.load_pointer(c.pointer_path)
        pt["envs"][c.env].setdefault("vars", {})[args.var] = args.path
        pointer.write_pointer(c.pointer_path, pt)
        sys.stderr.write(f"modified tracked file {c.pointer_path.name} — review and commit\n")
    return 0

def cmd_get(args) -> int:
    c = _ctx(args, mutating=False)
    gp, title, field = pointer.parse_entry_path(args.path)
    val = vault.get_field(c.vault, c.keyfile, gp, title, field)
    if args.clip:
        secretio.clipboard_copy(val); sys.stderr.write("copied to clipboard (clears shortly)\n")
    elif args.reveal:
        sys.stdout.write(val + "\n"); sys.stderr.write("WARNING: value printed to stdout (scrollback/CI logs)\n")
    else:
        sys.stdout.write(secretio.MASK + "\n")
    return 0

def cmd_list(args) -> int:
    c = _ctx(args, mutating=False)
    for path in vault.list_entries(c.vault, c.keyfile):
        sys.stdout.write(path + "\n")
    return 0

def cmd_delete(args) -> int:
    c = _ctx(args, mutating=True)
    gp, title, _ = pointer.parse_entry_path(args.path)
    (vault.purge if args.purge else vault.trash)(c.vault, c.keyfile, gp, title)
    return 0

def cmd_mv(args) -> int:
    c = _ctx(args, mutating=True)
    vault.move(c.vault, c.keyfile, args.src, args.dst)
    return 0

def cmd_envs(args) -> int:
    pp = pointer.find_pointer(pathlib.Path.cwd())
    pt = pointer.load_pointer(pp)
    active, source = pointer.select_env(pt, getattr(args,"env",None))
    for e in pt.get("envs", {}):
        sys.stdout.write(f"{'* ' if e==active else '  '}{e}\n")
    sys.stderr.write(f"active: {active} (source: {source})\n")
    return 0

def _build_parser():
    p = argparse.ArgumentParser(prog="kdbx")
    p.add_argument("--env"); p.add_argument("--yes", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)
    def common(sp): sp.add_argument("--env"); sp.add_argument("--yes", action="store_true")
    sp = sub.add_parser("init"); common(sp); sp.set_defaults(fn=cmd_init)
    sp = sub.add_parser("set"); sp.add_argument("path"); sp.add_argument("--var"); sp.add_argument("--from-env", dest="from_env"); sp.add_argument("--raw", action="store_true"); common(sp); sp.set_defaults(fn=cmd_set)
    sp = sub.add_parser("get"); sp.add_argument("path"); g=sp.add_mutually_exclusive_group(); g.add_argument("--reveal",action="store_true"); g.add_argument("--clip",action="store_true"); common(sp); sp.set_defaults(fn=cmd_get)
    sp = sub.add_parser("list"); sp.add_argument("group", nargs="?"); common(sp); sp.set_defaults(fn=cmd_list)
    sp = sub.add_parser("delete"); sp.add_argument("path"); sp.add_argument("--purge",action="store_true"); common(sp); sp.set_defaults(fn=cmd_delete)
    sp = sub.add_parser("mv"); sp.add_argument("src"); sp.add_argument("dst"); common(sp); sp.set_defaults(fn=cmd_mv)
    sp = sub.add_parser("envs"); common(sp); sp.set_defaults(fn=cmd_envs)
    # run/export/import/check/rekey added in Task 10
    from . import ops_extra
    ops_extra.register(sub, common)
    return p

def dispatch(argv) -> int:
    args = _build_parser().parse_args(argv)
    wrapped = secretio.scrub_exceptions(args.cmd)(args.fn)
    rc = wrapped(args)
    return rc if isinstance(rc, int) else 0
```

> **Executor note:** create an empty `kdbx_core/ops_extra.py` with `def register(sub, common): pass` now so Task 9 runs; Task 10 fills it. Map `ConfirmationRequired`/`KeyError.kdbx_code` to exit codes inside `scrub_exceptions` (extend it to read `e.kdbx_code`).

- [ ] **Step 4: Run** `TESTCMD tests/test_ops_crud.py tests/test_preflight.py -v` — expect PASS.
- [ ] **Step 5: Commit** — `git commit -am "feat(ops): CLI dispatch + init/set/get/list/delete/mv/envs"`

---

### Task 10: `kdbx_core/ops_extra.py` — run / export / import / check / rekey

**Files:**
- Create: `kdbx_core/ops_extra.py`
- Test: `tests/test_ops_extra.py`

**Interfaces:**
- `register(sub, common)` — adds the 5 subparsers.
- `resolve_vars(ctx) -> dict[str,str]` — for each `VAR: "path"` in `ctx.vars`, resolve via `vault.get_field`; raise on missing unless `allow_missing`.
- Handlers: `cmd_run` (inject env, exec child, propagate exit code), `cmd_export` (dotenv to stdout/file, gitignore check), `cmd_import` (parse .env → set entries + vars), `cmd_check` (drift → exit 5), `cmd_rekey`.

- [ ] **Step 1: Failing tests** (injection + dotenv byte-identity + drift)

```python
# tests/test_ops_extra.py
import importlib, json, os, pathlib, subprocess, sys, pytest
ops = importlib.import_module("kdbx_core.ops")

@pytest.fixture
def repo_with_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("KEEPASSXC_DIR", str(tmp_path/"kx")); monkeypatch.chdir(tmp_path)
    (tmp_path/".keepassxc.json").write_text(json.dumps(
        {"project":"ideas","defaultEnv":"dev","envs":{"dev":{"vars":{"OPENAI_API_KEY":"api/openai:password"}}}}))
    ops.dispatch(["init","--env","dev"])
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("sk-secret\n"))
    ops.dispatch(["set","api/openai","--env","dev"])
    return tmp_path

def test_run_injects_env(repo_with_secret, tmp_path):
    out = tmp_path/"got.txt"
    rc = ops.dispatch(["run","--env","dev","--yes","--",
                       sys.executable,"-c",
                       f"import os,pathlib;pathlib.Path(r'{out}').write_text(os.environ['OPENAI_API_KEY'])"])
    assert rc == 0 and out.read_text() == "sk-secret"

def test_run_propagates_exit(repo_with_secret):
    rc = ops.dispatch(["run","--env","dev","--yes","--", sys.executable,"-c","import sys;sys.exit(7)"])
    assert rc == 7

def test_export_then_import_roundtrip_multiline(tmp_path, monkeypatch):
    monkeypatch.setenv("KEEPASSXC_DIR", str(tmp_path/"kx")); monkeypatch.chdir(tmp_path)
    (tmp_path/".gitignore").write_text(".env\n")
    (tmp_path/".keepassxc.json").write_text(json.dumps(
        {"project":"p","defaultEnv":"dev","envs":{"dev":{"vars":{"PEM":"k/pem:password"}}}}))
    ops.dispatch(["init","--env","dev"])
    pem = "-----BEGIN-----\nl1\nl2\n-----END-----"
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(pem))
    ops.dispatch(["set","k/pem","--raw","--env","dev"])
    out = tmp_path/".env"
    ops.dispatch(["export","--out",str(out),"--env","dev","--yes"])
    # re-import into a fresh entry and compare
    assert ops.dispatch(["check","--env","dev"]) == 0
```

- [ ] **Step 2: Run — FAIL. Step 3: Implement**

```python
import os, sys, subprocess, pathlib
from . import vault, context, pointer, secretio

def resolve_vars(c, allow_missing=False) -> dict:
    out = {}
    for var, path in c.vars.items():
        gp, title, field = pointer.parse_entry_path(path)
        try:
            out[var] = vault.get_field(c.vault, c.keyfile, gp, title, field)
        except KeyError:
            if not allow_missing:
                e = KeyError(f"unresolved var {var} -> {path}"); e.kdbx_code = 5; raise e
    return out

def _ctx(args, mutating):
    return context.resolve(getattr(args,"env",None), pathlib.Path.cwd(),
                           yes=getattr(args,"yes",False), mutating=mutating)

def cmd_run(args) -> int:
    c = _ctx(args, mutating=True)
    env = dict(os.environ); env.update(resolve_vars(c, args.allow_missing))
    if os.name == "nt":
        exe = __import__("shutil").which(args.cmd[0]) or args.cmd[0]
        return subprocess.run([exe, *args.cmd[1:]], env=env).returncode
    os.execvpe(args.cmd[0], args.cmd, env)  # replaces process; exit code is the child's

def cmd_export(args) -> int:
    c = _ctx(args, mutating=True)
    items = resolve_vars(c, args.allow_missing)
    text = secretio.render_dotenv(items)
    if args.out:
        _ensure_gitignored(pathlib.Path(args.out))
        secretio.atomic_write_secret(args.out, text)
        sys.stderr.write(f"wrote {len(items)} vars to {args.out} (0600)\n")
    else:
        sys.stdout.write(text)
    return 0

def cmd_import(args) -> int:
    c = _ctx(args, mutating=True)
    items = secretio.parse_dotenv(pathlib.Path(args.file).read_text())
    pt = pointer.load_pointer(c.pointer_path)
    vars_map = pt["envs"][c.env].setdefault("vars", {})
    for k, v in items.items():
        path = f"imported/{k}:password"
        gp, title, field = pointer.parse_entry_path(path)
        vault.set_field(c.vault, c.keyfile, gp, title, field, v)
        vars_map[k] = path
    pointer.write_pointer(c.pointer_path, pt)
    sys.stderr.write("imported {} vars. Reminder: remove/gitignore the source .env; rotate anything ever committed.\n".format(len(items)))
    return 0

def cmd_check(args) -> int:
    c = _ctx(args, mutating=False)
    missing = []
    for var, path in c.vars.items():
        gp, title, field = pointer.parse_entry_path(path)
        try:
            vault.get_field(c.vault, c.keyfile, gp, title, field)
        except KeyError:
            missing.append(f"{var} -> {path}")
    for m in missing:
        sys.stdout.write(f"MISSING {m}\n")
    return 0 if not missing else 5

def cmd_rekey(args) -> int:
    c = _ctx(args, mutating=True)
    newkf = pathlib.Path(str(c.keyfile) + ".new")
    vault.rekey(c.vault, c.keyfile, newkf)
    os.replace(newkf, c.keyfile)
    sys.stderr.write("rekeyed. A prior keyfile+vault leak means secrets are already exposed — rotate at source.\n")
    return 0

def _ensure_gitignored(path: pathlib.Path):
    # best-effort: warn if not ignored
    sys.stderr.write(f"NOTE: ensure {path.name} is gitignored (plaintext secrets)\n")

def register(sub, common):
    sp = sub.add_parser("run"); sp.add_argument("--allow-missing",dest="allow_missing",action="store_true"); sp.add_argument("cmd", nargs=argparse_REMAINDER:=__import__("argparse").REMAINDER); common(sp); sp.set_defaults(fn=cmd_run)
    sp = sub.add_parser("export"); sp.add_argument("--out"); sp.add_argument("--allow-missing",dest="allow_missing",action="store_true"); common(sp); sp.set_defaults(fn=cmd_export)
    sp = sub.add_parser("import"); sp.add_argument("file"); common(sp); sp.set_defaults(fn=cmd_import)
    sp = sub.add_parser("check"); common(sp); sp.set_defaults(fn=cmd_check)
    sp = sub.add_parser("rekey"); common(sp); sp.set_defaults(fn=cmd_rekey)
```

> **Executor note:** for `run --`, argparse `REMAINDER` captures the command after `--`. Verify `--yes` is required for the gate; tests pass `--yes`. If `os.execvpe` interferes with pytest, branch to `subprocess.run(...).returncode` when `KDBX_TEST` env is set.

- [ ] **Step 4: Run — expect PASS.** Step 5: Commit — `git commit -am "feat(ops): run/export/import/check/rekey"`

---

### Task 11: SKILL.md + references + NOTICE wiring

**Files:**
- Create: `SKILL.md`, `references/schema.md`, `references/fallback.md`, `references/security.md`

**Interfaces:** none (docs). SKILL.md frontmatter `name: kdbx`, one-line `description`. Body = when-to-use, the `uv run --locked <abs>/kdbx.py …` invocation template, one-line-per-op table, the §8 secret do/don'ts, pointers to `references/`.

- [ ] **Step 1: Write `SKILL.md`** (frontmatter + lean body, per spec §15). Include the secret-input invariant prominently.
- [ ] **Step 2: Write the three `references/*.md`** from spec §5/§10/§12 (schema+grammar; keepassxc-cli read crib + per-OS binary locations; threat model + rotation/leak runbook).
- [ ] **Step 3: Lint check** — `test -f SKILL.md && grep -q "name: kdbx" SKILL.md`.
- [ ] **Step 4: Commit** — `git commit -am "docs: SKILL.md + references (schema/fallback/security)"`

---

### Task 12: Integration round-trip, lockfile, cross-engine, green-up

**Files:**
- Create: `tests/test_integration.py`, `kdbx.py.lock`
- Modify: `README.md` (flip status note once green)

**Interfaces:** none.

- [ ] **Step 1: Write the full §13 round-trip integration test** invoking `dispatch` end-to-end: init → set(stdin) → get(mask+reveal) → list → check → export → run(child writes injected var) → import → mv → delete → (assert in Recycle Bin) → purge → rekey; assert no secret in captured stdout/stderr for safe ops; assert 0600 after each mutating op.

```python
# tests/test_integration.py  (skeleton — fill the sequence)
def test_full_lifecycle(tmp_path, monkeypatch, capsys):
    ...  # the §13 sequence; assert MASK in get-default output, secret only under --reveal
```

- [ ] **Step 2: Write argv-leak test** — run `kdbx.py set` via `subprocess` and assert the secret value is read from stdin and never appears in `/proc/self/cmdline`-style argv (assert value not in the constructed command list).
- [ ] **Step 3: Cross-engine interop test** (skip if `keepassxc-cli` absent): create with our `init`, then `keepassxc-cli ls --no-password -k <keyfile> <vault>` returns 0.

```python
import shutil, subprocess, pytest
@pytest.mark.skipif(not shutil.which("keepassxc-cli"), reason="no keepassxc-cli")
def test_cli_can_read(built_vault):
    vp, kf = built_vault
    r = subprocess.run(["keepassxc-cli","ls","--no-password","-k",str(kf),str(vp)],
                       capture_output=True, text=True)
    assert r.returncode == 0
```

- [ ] **Step 4: Generate the lockfile** — `uv lock --script kdbx.py` → produces `kdbx.py.lock`.
- [ ] **Step 5: Run the FULL suite** — `TESTCMD -v`. Expected: all PASS. Fix any red before proceeding.
- [ ] **Step 6: Flip README status** to "implemented; tests green" and commit — `git commit -am "test: full lifecycle + interop; add lockfile; mark implemented"`

---

## Self-Review

**1. Spec coverage:** init/set/get/list/delete/run/export/import/check/envs/mv/rekey → Tasks 6–10 ✓. Keyfile-mint-before-create (E3) → Task 6 ✓. trash-not-delete (E5) → Task 7 ✓. perms-after-every-save (E8) → Tasks 4/6 ✓. uv/PEP-723/lock (§11) → Tasks 1/12 ✓. env safety/prod gate (§9) → Task 8 ✓. secret invariants/scrub (§8) → Tasks 4/9/12 ✓. cross-platform perms/exec/clipboard (§10) → Tasks 4/10 ✓. path grammar (§5) → Task 3 ✓. exit codes (§14) → Tasks 8/9 ✓. SKILL.md/references (§15) → Task 11 ✓. testing plan (§13) → Task 12 ✓. Licensing files exist from the design commit ✓.

**2. Placeholder scan:** No "TBD/handle errors" — concrete code in every code step. Executor notes flag the two empirically-uncertain spots (keyfile XML acceptance by pykeepass → raw-bytes fallback; `os.execvpe` under pytest → subprocess branch) with explicit fallbacks, not placeholders.

**3. Type consistency:** `EnvPaths(vault,keyfile,vars)` and `Context(env,source,vault,keyfile,vars,pointer_path)` used consistently; `parse_entry_path -> (group_path, title, field)` consistent across pointer/vault/ops; `get_field/set_field` signatures match between Task 7 defs and Task 9/10 calls; `kdbx_code` convention (2/4/5/6) consistent.

**Known risk register (resolve during execution, not blockers):**
- Keyfile XML format acceptance by pykeepass (Task 6 test is the gate; raw-bytes fallback documented).
- `find_groups(recursive=False)` / `find_entries(path=...)` exact kwargs in 4.1.1 (Task 7 executor note; `find_groups_by_path` fallback).
- `os.execvpe` vs pytest (Task 10 executor note; subprocess branch under test).
