import importlib
import io
import os
import stat

import pytest

s = importlib.import_module("kdbx_core.secretio")


def test_mask_has_no_value_info():
    assert s.MASK == "(set, hidden)"


def test_read_secret_from_env(monkeypatch):
    monkeypatch.setenv("SRC", "hunter2")

    class A:
        from_env = "SRC"
        raw = False

    assert s.read_secret(A()) == "hunter2"


def test_read_secret_stdin_strips_one_newline(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("topsecret\n"))

    class A:
        from_env = None
        raw = False

    assert s.read_secret(A()) == "topsecret"


@pytest.mark.skipif(os.name == "nt", reason="POSIX perms")
def test_atomic_write_is_0600(tmp_path):
    p = tmp_path / "out.env"
    s.atomic_write_secret(p, "X=1\n")
    assert stat.S_IMODE(p.stat().st_mode) == 0o600


def test_dotenv_roundtrip_multiline():
    pem = "-----BEGIN-----\nabc\ndef\n-----END-----"
    text = s.render_dotenv({"KEY": pem, "OTHER": "v$1"})
    back = s.parse_dotenv(text)
    assert back["KEY"] == pem and back["OTHER"] == "v$1"


def test_scrub_hides_value(capsys, monkeypatch):
    monkeypatch.delenv("KDBX_DEBUG", raising=False)  # production default: no traceback

    @s.scrub_exceptions("set")
    def boom():
        raise ValueError("secret-literal-12345")

    rc = boom()
    err = capsys.readouterr().err
    assert "secret-literal-12345" not in err
    assert "set failed" in err and rc != 0
