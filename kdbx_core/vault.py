"""pykeepass engine — the SOLE WRITER. Engine-agnostic public interface.

Callers pass/receive plain types (paths, names, str) — never pykeepass objects —
so this module is the single swap point for a future permissive engine.
"""
import hashlib
import os
import pathlib
import secrets

from pykeepass import PyKeePass, create_database

from . import locking, pointer, secretio

_RESERVED = {"title", "username", "password", "url", "notes"}


# ── keyfile + database creation ────────────────────────────────────────────
def generate_keyfile_xml(key: bytes) -> str:
    data = key.hex().upper()
    checksum = hashlib.sha256(key).digest()[:4].hex().upper()
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<KeyFile>\n\t<Meta>\n\t\t<Version>2.0</Version>\n\t</Meta>\n"
        f'\t<Key>\n\t\t<Data Hash="{checksum}">{data}</Data>\n\t</Key>\n</KeyFile>\n'
    )


def mint_keyfile(path) -> None:
    path = pathlib.Path(path)
    if path.exists():
        raise FileExistsError(f"keyfile already exists: {path}")
    secretio.atomic_write_secret(path, generate_keyfile_xml(secrets.token_bytes(32)))


def create_vault(vault, keyfile) -> None:
    vault, keyfile = pathlib.Path(vault), pathlib.Path(keyfile)
    if vault.exists() or keyfile.exists():
        raise FileExistsError("refusing to overwrite an existing vault or keyfile")
    vault.parent.mkdir(parents=True, exist_ok=True)
    mint_keyfile(keyfile)
    kp = create_database(str(vault), keyfile=str(keyfile))  # KDBX4 + Argon2 default
    assert kp.version[0] == 4 and "argon2" in str(kp.kdf_algorithm).lower(), (
        "expected KDBX4 + Argon2"
    )
    secretio.restrict_perms(vault)


def _open(vault, keyfile):
    return PyKeePass(str(vault), keyfile=str(keyfile))


def save(kp, vault) -> None:
    vault = pathlib.Path(vault)
    tmp = vault.with_suffix(vault.suffix + ".tmp")
    bak = vault.with_suffix(vault.suffix + ".bak")
    kp.save(str(tmp))
    secretio.restrict_perms(tmp)
    if vault.exists():
        os.replace(vault, bak)  # crash-safety: keep the prior vault until the new one lands
    os.replace(tmp, vault)
    secretio.restrict_perms(vault)
    if bak.exists():
        os.unlink(bak)  # replace succeeded — drop the redundant 0600 copy of the secrets


# ── recycle-bin awareness ──────────────────────────────────────────────────
def _in_recyclebin(kp, entry) -> bool:
    rb = kp.recyclebin_group
    if rb is None:
        return False
    p = entry.path
    return bool(p) and p[0] == rb.name


def _walk_create(kp, group_path):
    grp = kp.root_group
    for name in group_path:
        found = kp.find_groups(name=name, group=grp, recursive=False, first=True)
        grp = found if found else kp.add_group(grp, name)
    return grp


def _find_entry(kp, group_path, title, *, include_trash=False):
    e = kp.find_entries(path=group_path + [title], first=True)
    if e is not None:
        if include_trash or not _in_recyclebin(kp, e):
            return e
        return None
    if include_trash:
        for cand in kp.find_entries(title=title) or []:
            return cand
    return None


# ── CRUD / resolver ────────────────────────────────────────────────────────
def set_field(vault, keyfile, group_path, title, field, value) -> None:
    with locking.vault_lock(vault):
        captured = locking.capture_state(vault)
        kp = _open(vault, keyfile)
        locking.verify_unchanged(vault, captured)
        grp = _walk_create(kp, group_path)
        e = _find_entry(kp, group_path, title) or kp.add_entry(grp, title, "", "")
        if field.lower() in _RESERVED:
            setattr(e, field.lower(), value)
        else:
            e.set_custom_property(field, value, protect=True)
        save(kp, vault)


def get_field(vault, keyfile, group_path, title, field) -> str:
    kp = _open(vault, keyfile)
    e = _find_entry(kp, group_path, title)
    if e is None:
        err = KeyError(f"entry not found: {'/'.join(group_path + [title])}")
        err.kdbx_code = 2
        raise err
    if field.lower() in _RESERVED:
        val = getattr(e, field.lower())
    else:
        val = e.get_custom_property(field)
    if val is None:
        err = KeyError(f"field not found: {field}")
        err.kdbx_code = 2
        raise err
    return val


def list_entries(vault, keyfile) -> list:
    kp = _open(vault, keyfile)
    out = []
    for e in kp.entries:
        if _in_recyclebin(kp, e):
            continue
        out.append("/".join(e.path))
    return sorted(out)


def trash(vault, keyfile, group_path, title) -> None:
    with locking.vault_lock(vault):
        kp = _open(vault, keyfile)
        e = _find_entry(kp, group_path, title)
        if e is None:
            err = KeyError("entry not found")
            err.kdbx_code = 2
            raise err
        kp.trash_entry(e)
        save(kp, vault)


def purge(vault, keyfile, group_path, title) -> None:
    with locking.vault_lock(vault):
        kp = _open(vault, keyfile)
        e = _find_entry(kp, group_path, title, include_trash=True)
        if e is None:
            err = KeyError("entry not found")
            err.kdbx_code = 2
            raise err
        kp.delete_entry(e)
        save(kp, vault)


def move(vault, keyfile, src: str, dst: str) -> None:
    sg, st, _ = pointer.parse_entry_path(src)
    dg, dt, _ = pointer.parse_entry_path(dst)
    with locking.vault_lock(vault):
        kp = _open(vault, keyfile)
        e = _find_entry(kp, sg, st)
        if e is None:
            err = KeyError("entry not found")
            err.kdbx_code = 2
            raise err
        if dg != sg:
            kp.move_entry(e, _walk_create(kp, dg))
        e.title = dt
        save(kp, vault)


def rekey(vault, keyfile, new_keyfile) -> None:
    mint_keyfile(new_keyfile)
    with locking.vault_lock(vault):
        kp = _open(vault, keyfile)
        kp.keyfile = str(new_keyfile)
        save(kp, vault)
    os.unlink(keyfile)
