"""Part ten: the solve has to refuse the cases it cannot do.

The focal length used to come from sqrt(v1*v2 - oivi^2) with v1 and v2 as plain
distances. That is the right number only while the lens axis falls between the
two vanishing points along the horizon, which is the only arrangement a real
camera produces. Outside it the expression still returns something, and what it
returns near the boundary is a few millimeters. A fifty five millimeter lens
reading four millimeters is that, not a fisheye.

So this asks two things of every configuration: does the camera the node builds
actually match the geometry the grid is drawn from, and when it cannot, does the
node say so instead of printing a number.
"""
import math
import nuke

nuke.pluginAddPath(r"C:\Users\dhoch\.nuke\Gizmos\DH_Tools\3D")
import dhPersp

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("  %-4s %-62s %s" % ("PASS" if ok else "FAIL", name, detail))


W, H = 1920, 1080
nuke.addFormat("%d %d 0 0 %d %d 1 testHD" % (W, H, W, H))
nuke.root()["format"].setValue("testHD")
plate = nuke.nodes.Constant(format="testHD")
s = nuke.createNode("dhPerspSolve", inpanel=False)
s.setInput(0, plate)
cam = s.node("cam")


def frames():
    """The ground frame the grid uses, and the same three axes from the camera."""
    g = lambda k: float(s[k].value())
    mine = {"u1": (g("_u1x"), g("_u1y"), g("_u1z")),
            "u2": (g("_u2x"), g("_u2y"), g("_u2z")),
            "n": (g("_nx"), g("_ny"), g("_nz"))}
    wm = cam["world_matrix"].getValue()
    theirs = [tuple(wm[0:3]), tuple(wm[4:7]), tuple(wm[8:11])]
    return mine, theirs


def agrees(tol=2e-3):
    """Does each world axis of the camera match one of the grid's, either sign."""
    mine, theirs = frames()
    used = []
    for row in theirs:
        hit = None
        for nm, v in mine.items():
            for sgn in (1.0, -1.0):
                if max(abs(a - sgn * b) for a, b in zip(row, v)) < tol:
                    hit = "%s%s" % ("+" if sgn > 0 else "-", nm)
        if hit is None:
            return None
        used.append(hit)
    return used


# ------------------------------------------------------- 36. valid geometry
print("\n=== 36. where a camera exists, the grid and the camera are the same one ===")
GOOD = [("lens axis between the two, level", (-600, 700), (2900, 640)),
        ("guides linked the other way round", (2900, 640), (-600, 700)),
        ("tilted horizon", (-700, 900), (2700, 400)),
        ("low horizon", (-400, 300), (2500, 330)),
        ("wide pair, short lens", (-2600, 620), (4400, 600)),
        ("tight pair, long lens", (-140, 610), (2100, 600))]
for nm, a, b in GOOD:
    s["vp1"].setValue([float(a[0]), float(a[1])])
    s["vp2"].setValue([float(b[0]), float(b[1])])
    used = agrees()
    ok = float(s["_solveok"].value()) > 0.5
    check("%s: solves" % nm, ok, "%.2f mm" % s["cam_focal"].value())
    check("%s: camera and grid are one frame" % nm, used is not None,
          " ".join(used) if used else "they disagree")

# --------------------------------------------------- 37. impossible geometry
print("\n=== 37. where no camera exists, the node has to say so ===")
BAD = [("both vanishing points to the right", (2200, 700), (5200, 690)),
       ("both to the left", (-5200, 690), (-2200, 700)),
       ("the two guides follow the same direction", (2400, 650), (2460, 648)),
       ("both guides untouched, crossing at the center", (960, 540), (960, 540))]
for nm, a, b in BAD:
    s["vp1"].setValue([float(a[0]), float(a[1])])
    s["vp2"].setValue([float(b[0]), float(b[1])])
    ok = float(s["_solveok"].value()) > 0.5
    check("%s: refused" % nm, not ok,
          "_fsq %.4g, focal would read %.2f mm"
          % (s["_fsq"].value(), s["cam_focal"].value()))
    dhPersp.set_verdict(s)
    said = s["verdict"].value()
    check("%s: and says why" % nm, "do not describe a camera" in said,
          said[:70])

print("\n=== 38. the old unsigned formula would have accepted those ===")
for nm, a, b in BAD[:2]:
    s["vp1"].setValue([float(a[0]), float(a[1])])
    s["vp2"].setValue([float(b[0]), float(b[1])])
    v1, v2 = float(s["_v1"].value()), float(s["_v2"].value())
    oivi = float(s["_oivi"].value())
    old = math.sqrt(max(v1 * v2 - oivi * oivi, 1e-6))
    old_mm = old * math.sqrt(s["filmback"].value() ** 2 + s["_va"].value() ** 2) \
        / math.sqrt(W * W + H * H)
    check("%s: the old formula returned a plausible looking lens" % nm,
          old_mm > 1.0, "%.2f mm out of thin air" % old_mm)

# ------------------------------------------- 39. the untouched vertical guide
print("\n=== 39. an unplaced vertical guide must not move the lens axis ===")
s["vp1"].setValue([-600.0, 700.0])
s["vp2"].setValue([2900.0, 640.0])
s["use_vertical"].setValue(False)
base = (s["_px"].value(), s["_py"].value(), s["cam_focal"].value())
check("with no vertical guide the lens axis is the center of frame",
      abs(base[0] - W / 2.0) < 0.5 and abs(base[1] - H / 2.0) < 0.5,
      "(%.1f, %.1f)" % (base[0], base[1]))

s["use_vertical"].setValue(True)
s["vp3"].setValue([float(W) / 2, float(H) / 2])        # an untouched guide
check("an untouched vertical guide is ignored", s["_v3ok"].value() < 0.5, "")
check("so the lens axis does not move",
      abs(s["_px"].value() - base[0]) < 0.5 and abs(s["_py"].value() - base[1]) < 0.5,
      "(%.1f, %.1f)" % (s["_px"].value(), s["_py"].value()))
check("and the focal length does not collapse",
      abs(s["cam_focal"].value() - base[2]) < 0.01,
      "%.2f mm vs %.2f mm" % (s["cam_focal"].value(), base[2]))

s["vp3"].setValue([960.0, 1e9])                        # the default, parallel
check("the default vp3 is ignored on an HD frame", s["_v3ok"].value() < 0.5, "")
big = "6000 4000 0 0 6000 4000 1 testBig"
nuke.addFormat(big)
plate["format"].setValue("testBig")
check("and on a 24 megapixel frame too, which the old limit let through",
      s["_v3ok"].value() < 0.5, "diag %.0f px" % s["_diag"].value())
plate["format"].setValue("testHD")

s["vp3"].setValue([1400.0, 6200.0])                    # verticals really converging
check("a vertical guide that is actually placed is used",
      s["_v3ok"].value() > 0.5, "")
moved = math.hypot(s["_px"].value() - base[0], s["_py"].value() - base[1])
check("and it moves the lens axis off center, which is the point of it",
      moved > 1.0, "%.1f px off center" % moved)
s["use_vertical"].setValue(False)

print("\n" + "=" * 88)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 10: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
