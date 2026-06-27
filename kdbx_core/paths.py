"""OS-aware resolution of the KeePassXC config dir and pointer paths."""
import os
import platform
import pathlib

_SYNC_ROOTS = ("OneDrive", "Dropbox", "iCloud", "iCloudDrive", "Nextcloud", "Google Drive")


def keepassxc_dir() -> pathlib.Path:
    """Base dir for vaults/keyfiles. $KEEPASSXC_DIR wins; else per-OS default."""
    override = os.environ.get("KEEPASSXC_DIR")
    if override:
        return pathlib.Path(override)
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.path.expandvars(
            r"%USERPROFILE%\AppData\Local"
        )
        return pathlib.Path(base) / "keepassxc"
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(pathlib.Path.home(), ".config")
    return pathlib.Path(base) / "keepassxc"


def expand_path(raw: str) -> pathlib.Path:
    """Expand a pointer path: ${KEEPASSXC_DIR} token, then ~, then absolutize."""
    s = raw.replace("${KEEPASSXC_DIR}", str(keepassxc_dir()))
    return pathlib.Path(os.path.expanduser(s)).resolve()


def under_sync_root(p) -> str | None:
    """Return the name of a cloud-sync root in the path, or None."""
    parts = set(pathlib.Path(p).parts)
    for root in _SYNC_ROOTS:
        if root in parts:
            return root
    if "AppData" in parts and "Roaming" in parts:
        return "AppData/Roaming"
    return None
