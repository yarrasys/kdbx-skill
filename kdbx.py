# /// script
# requires-python = ">=3.10"
# dependencies = ["pykeepass>=4.1,<5", "python-dotenv", "filelock", "platformdirs"]
# ///
"""kdbx — per-project/per-env KeePassXC credential manager. See SKILL.md."""
import os
import sys

os.umask(0o077)  # restrict any file we create before an explicit chmod


def _preflight() -> None:
    if sys.version_info < (3, 10):
        sys.stderr.write("kdbx: requires Python >=3.10 (run via `uv run`)\n")
        raise SystemExit(7)
    try:
        import pykeepass  # noqa: F401
    except ModuleNotFoundError:
        sys.stderr.write(
            "kdbx: missing deps; run via `uv run --locked kdbx.py` "
            "(deps are declared in the kdbx.py PEP-723 header)\n"
        )
        raise SystemExit(7)


def main(argv=None) -> int:
    _preflight()
    from kdbx_core.ops import dispatch  # imported only after preflight

    return dispatch(argv if argv is not None else sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
