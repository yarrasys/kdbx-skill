import importlib

import pytest

vault = importlib.import_module("kdbx_core.vault")


def test_set_get_default_password(built_vault):
    vp, kf = built_vault
    vault.set_field(vp, kf, ["api"], "openai", "password", "sk-xyz")
    assert vault.get_field(vp, kf, ["api"], "openai", "password") == "sk-xyz"


def test_get_missing_field_raises(built_vault):
    vp, kf = built_vault
    vault.set_field(vp, kf, ["api"], "openai", "password", "sk")
    with pytest.raises(KeyError):
        vault.get_field(vp, kf, ["api"], "openai", "username")


def test_trash_is_recoverable_and_hidden(built_vault):
    vp, kf = built_vault
    vault.set_field(vp, kf, ["g"], "t", "password", "v")
    vault.trash(vp, kf, ["g"], "t")
    assert "g/t" not in vault.list_entries(vp, kf)
    with pytest.raises(KeyError):
        vault.get_field(vp, kf, ["g"], "t", "password")
    kp = vault._open(vp, kf)
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


def test_custom_field_roundtrip(built_vault):
    vp, kf = built_vault
    vault.set_field(vp, kf, ["svc"], "thing", "token", "abc123")
    assert vault.get_field(vp, kf, ["svc"], "thing", "token") == "abc123"
