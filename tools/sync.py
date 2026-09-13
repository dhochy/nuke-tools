"""Keep the .nuke install and this repo in step, in either direction.

Every file in this project exists twice: once where Nuke actually loads it from,
and once here under version control. Copying between them by hand is how they
drift, and a drifted gizmo is hard to spot because both copies look fine on their
own.

    python tools/sync.py              what differs, changes nothing
    python tools/sync.py --to-repo    .nuke  ->  repo   (after editing the install)
    python tools/sync.py --install    repo   ->  .nuke  (on a fresh workstation)

The install is normally the source of truth, because that is where the tools get
edited and tested.
"""
import filecmp
import io
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NUKE = os.path.join(os.path.expanduser("~"), ".nuke")

# repo relative path  ->  path inside .nuke
PAIRS = [
    ("gizmos/3D/dhPerspGuide.gizmo", "Gizmos/DH_Tools/3D/dhPerspGuide.gizmo"),
    ("gizmos/3D/dhPerspSolve.gizmo", "Gizmos/DH_Tools/3D/dhPerspSolve.gizmo"),
    ("python/dhPersp.py", "python/dhPersp.py"),
    ("icons/dhPerspGuide.png", "Icons/dhPerspGuide.png"),
    ("icons/dhPerspSolve.png", "Icons/dhPerspSolve.png"),
]


def scan():
    same, differ, missing = [], [], []
    for rel, sub in PAIRS:
        a = os.path.join(REPO, rel)
        b = os.path.join(NUKE, sub)
        if not os.path.isfile(a) or not os.path.isfile(b):
            missing.append((rel, sub, os.path.isfile(a), os.path.isfile(b)))
        elif filecmp.cmp(a, b, shallow=False):
            same.append(rel)
        else:
            differ.append((rel, sub))
    return same, differ, missing


def build_of(path):
    """The build number a gizmo carries, so drift is reported in useful terms."""
    if not path.endswith(".gizmo") or not os.path.isfile(path):
        return None
    for line in open(path, encoding="utf-8", errors="replace"):
        if line.strip().startswith("_build "):
            try:
                return int(line.strip().split()[1])
            except Exception:
                return None
    return None


def check_startup():
    """menu.py and init.py must parse, and the paths must be in init.py.

    A syntax error in either kills everything after it, silently. And Nuke runs
    init.py in every mode but menu.py only in the GUI, so a gizmo path declared
    in menu.py is invisible to a terminal session, which is what the render farm
    is. Both mistakes have already happened once here.
    """
    import ast
    bad = []
    for name in ("menu.py", "init.py"):
        path = os.path.join(NUKE, name)
        if not os.path.isfile(path):
            continue
        try:
            src = io.open(path, encoding="utf-8", errors="replace").read()
            ast.parse(src)
            print("  parses  %s" % name)
        except SyntaxError as e:
            bad.append("%s line %s: %s" % (name, e.lineno, e.msg))
            print("  BROKEN  %s line %s: %s" % (name, e.lineno, e.msg))
            continue
        if name == "menu.py" and "pluginAddPath" in src:
            for line in src.splitlines():
                if "pluginAddPath" in line and not line.strip().startswith("#"):
                    bad.append("plugin path in menu.py, invisible in terminal mode:"
                               " %s" % line.strip())
                    print("  WRONG PLACE  %s" % line.strip())
    return bad


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    same, differ, missing = scan()

    print("repo    %s" % REPO)
    print("install %s\n" % NUKE)

    for rel, sub, has_a, has_b in missing:
        print("  MISSING  %-34s repo:%s install:%s"
              % (rel, "yes" if has_a else "NO", "yes" if has_b else "NO"))
    for rel in same:
        print("  same     %s" % rel)
    for rel, sub in differ:
        ba = build_of(os.path.join(REPO, rel))
        bb = build_of(os.path.join(NUKE, sub))
        extra = ""
        if ba is not None or bb is not None:
            extra = "   build repo %s, install %s" % (ba, bb)
        print("  DIFFERS  %s%s" % (rel, extra))

    if mode == "--check":
        print("")
        print("startup files:")
        bad = check_startup()
        if differ or missing or bad:
            n = len(differ) + len(missing)
            if n:
                print("")
                print("%d file(s) out of step. Run --to-repo or --install." % n)
            for b in bad:
                print("  startup problem: %s" % b)
            return 1
        print("")
        print("In step.")
        return 0

    if mode not in ("--to-repo", "--install"):
        print("\nUnknown option %r. Use --check, --to-repo or --install." % mode)
        return 2

    moved = 0
    for rel, sub in PAIRS:
        a = os.path.join(REPO, rel)
        b = os.path.join(NUKE, sub)
        src, dst = (b, a) if mode == "--to-repo" else (a, b)
        if not os.path.isfile(src):
            print("\n  skip %s, source missing" % rel)
            continue
        if os.path.isfile(dst) and filecmp.cmp(src, dst, shallow=False):
            continue
        d = os.path.dirname(dst)
        if not os.path.isdir(d):
            os.makedirs(d)
        shutil.copy2(src, dst)
        moved += 1
        print("\n  copied %s" % rel)
    print("\n%d file(s) copied %s." % (moved,
          "into the repo" if mode == "--to-repo" else "into .nuke"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
