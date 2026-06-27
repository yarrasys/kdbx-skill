"""Environment resolution + safety gate (prod / inherited $KDBX_ENV require --yes)."""
import pathlib
import sys
from dataclasses import dataclass

from . import pointer

EXIT = {
    "ok": 0,
    "not_found": 2,
    "locked": 3,
    "confirm": 4,
    "drift": 5,
    "changed": 6,
    "preflight": 7,
}


class ConfirmationRequired(Exception):
    kdbx_code = 4


@dataclass
class Context:
    env: str
    source: str
    vault: pathlib.Path
    keyfile: pathlib.Path
    vars: dict
    pointer_path: pathlib.Path | None


def resolve(cli_env, start_dir, *, yes: bool, mutating: bool) -> Context:
    pp = pointer.find_pointer(pathlib.Path(start_dir))
    if pp is None:
        err = FileNotFoundError("no .keepassxc.json found (run from inside a configured repo)")
        err.kdbx_code = 2
        raise err
    pt = pointer.load_pointer(pp)
    env, source = pointer.select_env(pt, cli_env)
    ep = pointer.resolve_env(pt, env, pp.parent)
    if mutating:
        sys.stderr.write(f"ACTIVE ENV: {env}  vault={ep.vault}  (source: {source})\n")
        if (env == "prod" or source == "$KDBX_ENV") and not yes:
            raise ConfirmationRequired(f"env '{env}' (source {source}) requires --yes")
    return Context(env, source, ep.vault, ep.keyfile, ep.vars, pp)
