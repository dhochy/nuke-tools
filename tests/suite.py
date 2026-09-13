"""Full test sweep for dhPerspGuide / dhPerspSolve.

Every check prints PASS or FAIL with the measured numbers, so a failure says what
it actually got rather than just that something is wrong.
"""
import traceback
import nuke
from math import hypot

nuke.pluginAddPath(r"C:\Users\dhoch\.nuke\Gizmos\DH_Tools\3D")
import dhPersp

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("  %-4s %-46s %s" % ("PASS" if ok else "FAIL", name, detail))


class IC(object):
    def name(self):
        return "inputChange"


IC = IC()

for w, h, nm in ((1920, 1080, "hd"), (864, 1216, "tall"), (4096, 1716, "wide"),
                 (512, 512, "square")):
    nuke.addFormat("%d %d 0 0 %d %d 1 fmt_%s" % (w, h, w, h, nm))
nuke.root()["format"].setValue("fmt_hd")


def cam_at(focal, rx, ry, rz=0.0, height=9.0):
    c = nuke.nodes.Camera2() if "Camera2" in dir(nuke.nodes) else nuke.nodes.Camera()
    c["focal"].setValue(focal)
    c["rotate"].setValue([rx, ry, rz])
    c["translate"].setValue([0.0, height, 0.0])
    return c


def project(plate, cam, p):
    r = nuke.nodes.Reconcile3D()
    r.setInput(0, plate)
    r.setInput(1, cam)
    a = nuke.nodes.Axis()
    a["translate"].setValue([float(v) for v in p])
    r.setInput(2, a)
    nuke.execute(r, 1, 1)
    o = r["output"].value()
    nuke.delete(a)
    nuke.delete(r)
    return [float(o[0]), float(o[1])]


# ---------------------------------------------------------------- 1. solve accuracy
print("\n=== 1. camera solve accuracy, ground truth round trip ===")
plate = nuke.nodes.Constant(format="fmt_hd")
D = 1.0e9
solve = nuke.createNode("dhPerspSolve", inpanel=False)
solve.setInput(0, plate)
worst_f = worst_rx = worst_ry = worst_swap = 0.0
solve["axis_from"].setValue(1)
for focal in (18.0, 35.0, 50.0, 85.0, 135.0):
    for rx in (0.0, -8.0, -20.0, -35.0):
        for ry in (20.0, 38.0, 55.0):
            cam = cam_at(focal, rx, ry)
            vx = project(plate, cam, [D, 0, 0])
            vz = project(plate, cam, [0, 0, -D])
            solve["vp1"].setValue(vx)
            solve["vp2"].setValue(vz)
            worst_f = max(worst_f, abs(solve["cam_focal"].value() - focal))
            worst_rx = max(worst_rx, abs(solve["cam_rx"].value() - rx))
            worst_ry = max(worst_ry, abs(solve["cam_ry"].value() - ry))
            keep = (solve["cam_focal"].value(), solve["cam_rx"].value(),
                    solve["cam_ry"].value())
            # the same two points handed over the other way round must agree
            solve["vp1"].setValue(vz)
            solve["vp2"].setValue(vx)
            solve["axis_from"].setValue(2)
            for a_, b_ in zip(keep, (solve["cam_focal"].value(),
                                     solve["cam_rx"].value(),
                                     solve["cam_ry"].value())):
                worst_swap = max(worst_swap, abs(a_ - b_))
            solve["axis_from"].setValue(1)
            nuke.delete(cam)
check("focal exact over 60 camera setups", worst_f < 0.02, "worst error %.4f mm" % worst_f)
check("pitch exact over 60 camera setups", worst_rx < 0.02, "worst error %.4f deg" % worst_rx)
check("yaw exact over 60 camera setups", worst_ry < 0.02, "worst error %.4f deg" % worst_ry)
check("vanishing point order does not change the camera", worst_swap < 0.02,
      "worst difference %.4f" % worst_swap)

# ---------------------------------------------------------------- 2. camera reproduces vps
print("\n=== 2. solved camera reproduces the vanishing points it was given ===")
icam = solve.node("cam")
worst = 0.0
for v1, v2 in (([-1800., 700.], [2600., 700.]), ([-600., 640.], [3400., 640.]),
               ([-300., 700.], [5000., 700.]), ([-1500., 560.], [2900., 690.])):
    solve["vp1"].setValue(v1)
    solve["vp2"].setValue(v2)
    solve["axis_from"].setValue(1)
    X = project(plate, icam, [D, 0, 0])
    Z = project(plate, icam, [0, 0, -D])
    worst = max(worst, hypot(X[0] - v1[0], X[1] - v1[1]), hypot(Z[0] - v2[0], Z[1] - v2[1]))
check("camera reproduces fed vanishing points", worst < 2.0, "worst %.2f px" % worst)

# ---------------------------------------------------------------- 3. degenerate inputs
print("\n=== 3. degenerate inputs must not crash or produce NaN ===")
bad = []
for tag, v1, v2 in (("identical", [500., 600.], [500., 600.]),
                    ("both far left", [-9000., 600.], [-8000., 600.]),
                    ("vertical horizon", [900., -4000.], [900., 4000.]),
                    ("on top of centre", [960., 540.], [961., 541.])):
    try:
        solve["vp1"].setValue(v1)
        solve["vp2"].setValue(v2)
        f = solve["cam_focal"].value()
        r = solve["cam_ry"].value()
        if f != f or r != r:
            bad.append(tag + " NaN")
    except Exception as e:
        bad.append("%s raised %s" % (tag, e))
check("no crash or NaN on degenerate vanishing points", not bad, str(bad))

# ---------------------------------------------------------------- 4. known focal
print("\n=== 4. known focal round trip ===")
solve["vp1"].setValue([-1800., 700.])
solve["vp2"].setValue([2600., 700.])
solve["use_known_focal"].setValue(True)
errs = []
for fb in (24.576, 36.0):
    solve["filmback"].setValue(fb)
    for f in (14.0, 35.0, 85.0, 200.0):
        solve["known_focal"].setValue(f)
        errs.append(abs(solve["cam_focal"].value() - f))
check("known focal reported back exactly", max(errs) < 0.01, "worst %.4f mm" % max(errs))
solve["use_known_focal"].setValue(False)

# ---------------------------------------------------------------- 5. floor geometry
print("\n=== 5. floor grid geometry ===")
solve["vp1"].setValue([-2570., 640.])
solve["vp2"].setValue([1900., 640.])
card = solve.node("floorgrid")
solve["griddistance"].setValue(6.0)
centres = []
for sz in (10., 21., 40., 80., 150.):
    solve["gridsize"].setValue(sz)
    centres.append([round(v, 4) for v in card["translate"].value()])
check("grid size is a pure scale, never moves the card",
      all(c == centres[0] for c in centres), str(centres[0]))
solve["gridsize"].setValue(40.0)
moved = []
for d in (2., 6., 20.):
    solve["griddistance"].setValue(d)
    moved.append(round(card["translate"].value()[2], 3))
check("distance moves the card", len(set(moved)) == 3, str(moved))
solve["griddistance"].setValue(6.0)
cells = []
for sz in (20., 40., 80.):
    solve["gridsize"].setValue(sz)
    cells.append(round(sz / card["rows"].value(), 3))
check("cell size held constant as the plane grows",
      max(cells) - min(cells) < 0.01, str(cells))

# The card must lie ON the ground plane, below the camera. Projecting corners is
# NOT a valid test: a corner behind the camera projects mirrored, while the
# renderer clips it. Render measurements confirmed 0 rows above the horizon even
# at size 200 / distance 4, so the invariant to assert is the geometry itself.
solve["gridsize"].setValue(60.0)
t = card["translate"].value()
camy = icam["translate"].value()[1]
check("floor card lies on the ground plane", abs(t[1] - solve["gridoffset"].value()[1]) < 1e-6,
      "card y %.4f" % t[1])
check("camera sits above the floor card", camy > t[1], "camera y %.2f vs card y %.2f" % (camy, t[1]))
ok_orient = card["orientation"].value() == "ZX"
check("card is flat, not standing up", ok_orient, "orientation %s" % card["orientation"].value())

print("\n" + "=" * 74)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 1: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s  %s" % (n, d))
