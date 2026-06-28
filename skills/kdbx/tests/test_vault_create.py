import importlib
import os
import stat

import pytest

vault = importlib.import_module("kdbx_core.vault")


def test_mint_keyfile_then_open(tmp_path):
    vp, kf = tmp_path / "v.kdbx", tmp_path / "v.keyx"
    vault.create_vault(vp, kf)
    assert vp.exists() and kf.exists()
    kp = vault._open(vp, kf)  # keyfile only, no password
    assert kp.version[0] == 4
    assert "argon2" in str(kp.kdf_algorithm).lower()


@pytest.mark.skipif(os.name == "nt", reason="POSIX perms")
def test_perms_0600_on_create(tmp_path):
    vp, kf = tmp_path / "v.kdbx", tmp_path / "v.keyx"
    vault.create_vault(vp, kf)
    assert stat.S_IMODE(vp.stat().st_mode) == 0o600
    assert stat.S_IMODE(kf.stat().st_mode) == 0o600


def test_refuse_existing(tmp_path):
    vp, kf = tmp_path / "v.kdbx", tmp_path / "v.keyx"
    vault.create_vault(vp, kf)
    with pytest.raises(FileExistsError):
        vault.create_vault(vp, kf)


@pytest.mark.skipif(os.name == "nt", reason="POSIX perms")
def test_save_keeps_0600(tmp_path):
    vp, kf = tmp_path / "v.kdbx", tmp_path / "v.keyx"
    vault.create_vault(vp, kf)
    kp = vault._open(vp, kf)
    kp.add_group(kp.root_group, "g")
    vault.save(kp, vp)
    assert stat.S_IMODE(vp.stat().st_mode) == 0o600
