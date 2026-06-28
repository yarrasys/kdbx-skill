import pathlib
import sys

import pytest

# tests live under skills/kdbx/tests/ — the skill dir (with kdbx_core) is one up
SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR))


@pytest.fixture
def built_vault(tmp_path):
    from kdbx_core import vault

    vp, kf = tmp_path / "v.kdbx", tmp_path / "v.keyx"
    vault.create_vault(vp, kf)
    return vp, kf
