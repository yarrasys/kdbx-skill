import importlib
import json

import pytest

pointer = importlib.import_module("kdbx_core.pointer")


def _write(p, obj):
    p.write_text(json.dumps(obj))


def test_find_walks_up(tmp_path):
    root = tmp_path / "repo"
    (root / "a" / "b").mkdir(parents=True)
    _write(root / ".keepassxc.json", {"project": "x", "defaultEnv": "dev", "envs": {"dev": {}}})
    assert pointer.find_pointer(root / "a" / "b") == root / ".keepassxc.json"


def test_select_env_precedence(monkeypatch):
    pt = {"defaultEnv": "dev", "envs": {"dev": {}, "prod": {}}}
    monkeypatch.setenv("KDBX_ENV", "prod")
    assert pointer.select_env(pt, "dev") == ("dev", "--env")
    assert pointer.select_env(pt, None) == ("prod", "$KDBX_ENV")
    monkeypatch.delenv("KDBX_ENV")
    assert pointer.select_env(pt, None) == ("dev", "pointer")


def test_resolve_derives_when_omitted(tmp_path, monkeypatch):
    monkeypatch.setenv("KEEPASSXC_DIR", str(tmp_path / "kx"))
    pt = {"project": "ideas", "defaultEnv": "dev", "envs": {"dev": {"vars": {"A": "g/T:password"}}}}
    ep = pointer.resolve_env(pt, "dev", tmp_path / "repo")
    assert ep.vault == (tmp_path / "kx" / "ideas" / "dev.kdbx").resolve()
    assert ep.keyfile == (tmp_path / "kx" / "ideas" / "dev.keyx").resolve()
    assert ep.vars == {"A": "g/T:password"}


def test_parse_entry_path():
    assert pointer.parse_entry_path("api/openai:password") == (["api"], "openai", "password")
    assert pointer.parse_entry_path("db/primary") == (["db"], "primary", "password")
    assert pointer.parse_entry_path("Top") == ([], "Top", "password")


def test_parse_rejects_colon_in_name():
    with pytest.raises(ValueError):
        pointer.parse_entry_path("api/ht:tp:password")


def test_write_pointer_atomic_preserves_order(tmp_path):
    p = tmp_path / ".keepassxc.json"
    pointer.write_pointer(p, {"project": "z", "defaultEnv": "dev", "envs": {}})
    assert list(json.loads(p.read_text()).keys())[0] == "project"
