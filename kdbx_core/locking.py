"""Advisory write lock + open-time integrity capture to prevent silent lost updates."""
import contextlib
import hashlib
import pathlib

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
