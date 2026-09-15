"""Compare what the tool solves on real photographs against what they claim.

Every other test here builds its plate from a Constant and its vanishing points
by projecting through a camera the test chose. That proves the arithmetic is
self consistent and proves nothing about photographs, which is the only question
that matters.

tools/fetch_testplates.py pulls photographs whose EXIF focal length is known,
through shutterdial, and writes a manifest with each one's 35mm equivalent. This
reads a Nuke script in which those plates have been traced and prints solved
against claimed, one row per solve.

    python tools/fetch_testplates.py
    # open the plates in Nuke, trace two guides on each, save the script
    "%ProgramFiles%/Nuke17.0v1/Nuke17.0.exe" -t tests/realplate.py mytraces.nk

The tracing is done by a person on purpose. Two attempts at doing it from here
failed and are worth recording so nobody repeats them. Placing the lines by eye
off a downscaled render put the left face's eave at a quarter of a pixel per
pixel where it really falls at a third, and a vanishing point is the quantity
that error moves most: it read 19 mm for a 34 mm photograph. Snapping those
lines to the nearest strong brightness gradient was worse, 17 mm, and its own
diagnostic said why: five to eight pixels of scatter on the fitted points, which
means it was locking onto window frames and shadows rather than the edge asked
for. An edge detector good enough for this is a real piece of work and not the
thing being tested.
"""
import io
import json
import math
import os
import sys
import nuke

nuke.pluginAddPath(r"C:\Users\dhoch\.nuke\Gizmos\DH_Tools\3D")
import dhPersp

PLATES = os.environ.get("PLATE_DIR", r"C:\temp\perspective_tests\plates")


def manifest():
    """What each plate claims, keyed by file name."""
    path = os.path.join(PLATES, "plates.json")
    if not os.path.isfile(path):
        return {}
    try:
        rows = json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return {}
    return {os.path.basename(r["file"]).lower(): r for r in rows}


def plate_of(node, seen=None):
    """The Read feeding this solve, however many guides are stacked between."""
    seen = seen or set()
    if node is None or node.fullName() in seen:
        return None
    seen.add(node.fullName())
    if node.Class() == "Read":
        return node
    for i in range(node.inputs()):
        got = plate_of(node.input(i), seen)
        if got is not None:
            return got
    return None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("No script given. Plates available to trace:")
        for name, row in sorted(manifest().items()):
            print("  %-26s %6.1f mm equivalent   %s"
                  % (name, row["focal_35mm_equiv"], row["title"][:40]))
        return 1

    nuke.scriptOpen(sys.argv[1])
    claims = manifest()
    solves = [n for n in nuke.allNodes(recurseGroups=False) if dhPersp.is_solve(n)]
    if not solves:
        print("No dhPerspSolve nodes in %s" % sys.argv[1])
        return 1

    print("%-26s %8s %8s %8s   %s"
          % ("plate", "claims", "solved", "error", "notes"))
    errs = []
    for s in solves:
        read = plate_of(s)
        name = os.path.basename(read["file"].value()).lower() if read else "?"
        row = claims.get(name)
        got = s["cam_focal"].value()
        note = []
        if s["_solveok"].value() < 0.5:
            note.append("refused")
        if s["_ill"].value() > 0.5:
            note.append("far vanishing point")
        if s["use_vertical"].value() and s["_v3ok"].value() > 0.5:
            note.append("lens axis solved")
        note.append("pair %d" % int(s["_pair"].value()))
        if row is None:
            print("%-26s %8s %8.2f %8s   %s"
                  % (name[:26], "?", got, "?", ", ".join(note)))
            continue
        want = row["focal_35mm_equiv"]
        err = 100.0 * (got - want) / want
        errs.append(abs(err))
        print("%-26s %8.1f %8.2f %7.1f%%   %s"
              % (name[:26], want, got, err, ", ".join(note)))

    if errs:
        errs.sort()
        print("\n%d plate(s): median error %.1f%%, worst %.1f%%"
              % (len(errs), errs[len(errs) // 2], errs[-1]))
        print("A photograph's EXIF equivalent is itself rounded, and a cropped")
        print("upload keeps the original number while showing a tighter frame,")
        print("so a few per cent is the floor here, not a failure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
