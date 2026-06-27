"""Discovery and parsing of the committed .keepassxc.json pointer file."""
import json
import os
import pathlib
from dataclasses import dataclass

from . import paths

POINTER_NAME = ".keepassxc.json"
_RESERVED_FIELDS = {"title", "username", "password", "url", "notes"}


@dataclass
class EnvPaths:
    vault: pathlib.Path
    keyfile: pathlib.Path
    vars: dict


def find_pointer(start) -> pathlib.Path | None:
    cur = pathlib.Path(start).resolve()
    for d in [cur, *cur.parents]:
        cand = d / POINTER_NAME
        if cand.is_file():
            return cand
    return None


def load_pointer(path) -> dict:
    return json.loads(pathlib.Path(path).read_text())


def select_env(pointer: dict, cli_env: str | None) -> tuple[str, str]:
    """Return (env_name, source). Precedence: --env > $KDBX_ENV > pointer default."""
    if cli_env:
        return cli_env, "--env"
    env = os.environ.get("KDBX_ENV")
    if env:
        return env, "$KDBX_ENV"
    return pointer.get("defaultEnv", "dev"), "pointer"


def resolve_env(pointer: dict, env: str, project_dir) -> EnvPaths:
    envs = pointer.get("envs", {})
    if env not in envs:
        err = KeyError(f"env '{env}' not configured in pointer")
        err.kdbx_code = 2
        raise err
    cfg = envs[env] or {}
    project = pointer.get("project") or pathlib.Path(project_dir).name
    default_dir = paths.keepassxc_dir() / project
    vault = (
        paths.expand_path(cfg["vault"])
        if cfg.get("vault")
        else (default_dir / f"{env}.kdbx").resolve()
    )
    keyfile = (
        paths.expand_path(cfg["keyFile"])
        if cfg.get("keyFile")
        else (default_dir / f"{env}.keyx").resolve()
    )
    return EnvPaths(vault=vault, keyfile=keyfile, vars=dict(cfg.get("vars") or {}))


def parse_entry_path(raw: str) -> tuple[list[str], str, str]:
    """'group/sub/Title:field' -> (group_path, title, field). field defaults to 'password'.

    Rejects ambiguous paths: a name component may not contain ':' (only the
    single field separator is allowed) and components may not be empty.
    """
    field = "password"
    body = raw
    if ":" in raw:
        body, field = raw.rsplit(":", 1)
        if ":" in body:
            raise ValueError(f"ambiguous path (multiple ':'): {raw!r}")
        if not field:
            raise ValueError(f"empty field: {raw!r}")
    segments = body.split("/")
    if any(seg == "" for seg in segments):
        raise ValueError(f"empty path component: {raw!r}")
    *group_path, title = segments
    return group_path, title, field


def write_pointer(path, pointer: dict) -> None:
    path = pathlib.Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(pointer, indent=2, sort_keys=False) + "\n")
    os.replace(tmp, path)
