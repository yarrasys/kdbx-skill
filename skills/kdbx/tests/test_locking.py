import importlib

import pytest

locking = importlib.import_module("kdbx_core.locking")


def test_capture_and_verify(tmp_path):
    v = tmp_path / "v.kdbx"
    v.write_bytes(b"abc")
    h = locking.capture_state(v)
    locking.verify_unchanged(v, h)  # no raise
    v.write_bytes(b"xyz")
    with pytest.raises(RuntimeError):
        locking.verify_unchanged(v, h)


def test_lock_acquires(tmp_path):
    v = tmp_path / "v.kdbx"
    with locking.vault_lock(v):
        assert (tmp_path / "v.kdbx.lock").exists()
