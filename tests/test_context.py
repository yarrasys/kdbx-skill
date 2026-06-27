import importlib
import json

import pytest

ctx = importlib.import_module("kdbx_core.context")


def _ptr(tmp, envs, default="dev"):
    p = tmp / ".keepassxc.json"
    p.write_text(json.dumps({"project": "p", "defaultEnv": default, "envs": envs}))
    return p


def test_prod_requires_yes(tmp_path, monkeypatch):
    monkeypatch.setenv("KEEPASSXC_DIR", str(tmp_path / "kx"))
    monkeypatch.delenv("KDBX_ENV", raising=False)
    _ptr(tmp_path, {"prod": {}})
    with pytest.raises(ctx.ConfirmationRequired):
        ctx.resolve("prod", tmp_path, yes=False, mutating=True)
    ctx.resolve("prod", tmp_path, yes=True, mutating=True)  # ok with --yes


def test_kdbx_env_inherited_gated(tmp_path, monkeypatch):
    monkeypatch.setenv("KEEPASSXC_DIR", str(tmp_path / "kx"))
    monkeypatch.setenv("KDBX_ENV", "dev")
    _ptr(tmp_path, {"dev": {}})
    with pytest.raises(ctx.ConfirmationRequired):
        ctx.resolve(None, tmp_path, yes=False, mutating=True)


def test_echo_to_stderr(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("KEEPASSXC_DIR", str(tmp_path / "kx"))
    monkeypatch.delenv("KDBX_ENV", raising=False)
    _ptr(tmp_path, {"dev": {}})
    ctx.resolve("dev", tmp_path, yes=False, mutating=True)
    assert "ACTIVE ENV: dev" in capsys.readouterr().err


def test_non_mutating_no_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("KEEPASSXC_DIR", str(tmp_path / "kx"))
    monkeypatch.delenv("KDBX_ENV", raising=False)
    _ptr(tmp_path, {"prod": {}})
    # reads on prod are allowed without --yes
    ctx.resolve("prod", tmp_path, yes=False, mutating=False)
