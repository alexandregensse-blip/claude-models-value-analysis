#!/usr/bin/env python3
"""The build as a simple filter (the maintainer, 4 Nov 2026): it reads only files of the repository, never a saved
copy outside it (/work/.salvo14/…, a capture's `file`). This runs data/build.py under an audit hook that refuses every
open, listdir or scandir outside the allowed folders (the repository, the --out folder, Python's own install, and any
folder given with --allow) and lists the refusals. Standard library only.

    python3 data/tests/sealed.py [--allow DIR] -- --fit-models catalog --out /tmp/b   # the build's own arguments

Exit 0 with no refusal; a refusal makes the open fail (PermissionError) and the run exit 3, listing it.
In the tests: `with sealed(allowed) as refused: build.main(argv)`; refused lists the paths the build tried.
"""
import contextlib, os, sys, sysconfig

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.dirname(HERE)
REPO = os.path.dirname(DATA)
EVENTS = {"open", "os.listdir", "os.scandir"}
_state = {"allowed": None, "refused": None}


def _python_dirs():
    out = {sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix}
    out |= {p for p in sysconfig.get_paths().values() if p}
    return out


def _hook(event, args):
    allowed = _state["allowed"]
    if allowed is None or event not in EVENTS or not args:
        return
    p = args[0]
    if isinstance(p, int) or p is None:                 # a file descriptor: already opened
        return
    if isinstance(p, bytes):
        p = os.fsdecode(p)
    p = os.path.realpath(os.path.abspath(str(p)))
    if any(p == a or p.startswith(a + os.sep) for a in allowed) or p.startswith("/dev/"):
        return
    _state["refused"].append(p)
    raise PermissionError(f"sealed build: {event} outside the allowed folders: {p}")


_installed = False


@contextlib.contextmanager
def sealed(allowed=()):
    """Refuse every file access outside REPO, Python's install and `allowed` while the block runs."""
    global _installed
    if not _installed:
        sys.addaudithook(_hook)                          # an audit hook cannot be removed: it is switched off below
        _installed = True
    refused = []
    _state["allowed"] = [os.path.realpath(x) for x in (REPO, *_python_dirs(), *allowed)]
    _state["refused"] = refused
    try:
        yield refused
    finally:
        _state["allowed"] = None


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    allow = []
    while argv and argv[0] == "--allow":
        allow.append(argv[1])
        argv = argv[2:]
    if argv and argv[0] == "--":
        argv = argv[1:]
    out = argv[argv.index("--out") + 1] if "--out" in argv else os.path.join(DATA, "build")
    os.makedirs(out, exist_ok=True)
    sys.path[:0] = [DATA, os.path.join(DATA, "schema")]
    import build                                         # noqa: E402 (imported before sealing: its own code)
    import build_lqm  # noqa: F401,E402
    with sealed([out, *allow]) as refused:
        try:
            code = build.main(argv)
        except PermissionError as e:
            print(e, file=sys.stderr)
            code = 3
    if refused:
        print(f"sealed build: {len(refused)} access(es) refused:", *sorted(set(refused))[:50], sep="\n  ", file=sys.stderr)
        return 3
    print("sealed build: no access outside the repository")
    return code


if __name__ == "__main__":
    sys.exit(main())
