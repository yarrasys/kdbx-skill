import importlib

paths = importlib.import_module("kdbx_core.paths")


def test_keepassxc_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("KEEPASSXC_DIR", str(tmp_path / "x"))
    assert paths.keepassxc_dir() == (tmp_path / "x")


def test_keepassxc_dir_linux(monkeypatch, tmp_path):
    monkeypatch.delenv("KEEPASSXC_DIR", raising=False)
    monkeypatch.setattr(paths.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert paths.keepassxc_dir() == tmp_path / "cfg" / "keepassxc"


def test_keepassxc_dir_windows(monkeypatch, tmp_path):
    monkeypatch.delenv("KEEPASSXC_DIR", raising=False)
    monkeypatch.setattr(paths.platform, "system", lambda: "Windows")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert paths.keepassxc_dir() == tmp_path / "local" / "keepassxc"


def test_expand_token(monkeypatch, tmp_path):
    monkeypatch.setenv("KEEPASSXC_DIR", str(tmp_path))
    assert paths.expand_path("${KEEPASSXC_DIR}/p/dev.kdbx") == tmp_path / "p" / "dev.kdbx"


def test_sync_root_detect(tmp_path):
    p = tmp_path / "OneDrive" / "keepassxc" / "dev.keyx"
    assert paths.under_sync_root(p) == "OneDrive"
