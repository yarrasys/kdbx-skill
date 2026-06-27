import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # repo root on path


@pytest.fixture
def built_vault(tmp_path):
    from kdbx_core import vault

    vp, kf = tmp_path / "v.kdbx", tmp_path / "v.keyx"
    vault.create_vault(vp, kf)
    return vp, kf
